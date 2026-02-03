#!/bin/bash
# Test script to verify the get_error_details fix

echo "🔧 Testing get_error_details() fix"
echo "=================================="

# Kill any running driver
pkill -9 -f ezgripper_dds_driver
sleep 2

# Start driver
cd /home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver
python3 ezgripper_dds_driver.py --side left --log-level INFO 2>&1 | tee /tmp/test_fix.log &
DRIVER_PID=$!

echo "Driver started (PID: $DRIVER_PID)"
echo "Waiting 5 seconds for calibration..."
sleep 5

# Send test commands
echo ""
echo "📤 Sending test commands..."
python3 << 'EOF'
import time
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_, MotorStates_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_

ChannelFactoryInitialize(0)
cmd_publisher = ChannelPublisher("rt/dex1/left/cmd", MotorCmds_)
cmd_publisher.Init()
state_subscriber = ChannelSubscriber("rt/dex1/left/state", MotorStates_)
state_subscriber.Init()

def send_and_check(pos_rad, desc):
    print(f"\n{desc} ({pos_rad:.1f} rad)")
    cmd_msg = MotorCmds_()
    cmd_msg.cmds = [unitree_go_msg_dds__MotorCmd_()]
    cmd_msg.cmds[0].q = pos_rad
    cmd_msg.cmds[0].dq = 0.0
    cmd_msg.cmds[0].tau = 0.0
    cmd_msg.cmds[0].kp = 5.00
    cmd_msg.cmds[0].kd = 0.05
    cmd_publisher.Write(cmd_msg)
    time.sleep(2)
    
    state_msg = state_subscriber.Read()
    if state_msg and hasattr(state_msg, 'states') and state_msg.states:
        pos = float(state_msg.states[0].q)
        print(f"  DDS feedback: {pos:.3f} rad ({(pos/5.4)*100:.0f}%)")
        return pos
    return None

# Test sequence
send_and_check(2.16, "40%")
send_and_check(3.24, "60%")
send_and_check(2.70, "50%")
EOF

echo ""
echo "=================================="
echo "📊 Checking logs for errors..."
echo ""

# Check for errors
if grep -q "Communication error.*has_error" /tmp/test_fix.log; then
    echo "❌ FAILED: Still getting 'has_error' exceptions"
    grep "Communication error" /tmp/test_fix.log | tail -5
else
    echo "✅ SUCCESS: No 'has_error' exceptions!"
fi

# Check if position updates are happening
if grep -q "🔄 READ: actual_position_pct" /tmp/test_fix.log; then
    echo "✅ SUCCESS: Position updates are happening!"
    grep "🔄 READ" /tmp/test_fix.log | tail -5
else
    echo "❌ FAILED: Position updates not happening"
fi

# Cleanup
kill -9 $DRIVER_PID 2>/dev/null

echo ""
echo "Full log saved to: /tmp/test_fix.log"
