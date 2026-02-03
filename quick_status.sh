#!/bin/bash
# Quick driver status check

echo "🔍 Driver Status Check"
echo "====================="

# Check if driver running
if pgrep -f ezgripper_dds_driver > /dev/null; then
    PID=$(pgrep -f ezgripper_dds_driver)
    echo "✅ Driver running (PID: $PID)"
    
    # Get last 30 lines of output
    echo ""
    echo "📋 Recent logs:"
    tail -30 /proc/$PID/fd/1 2>/dev/null | grep -E "Calibration|Setup|ERROR|CRITICAL|Hardware|overload|Torque|Multi-turn|Operating" || echo "   (no relevant logs)"
else
    echo "❌ Driver not running"
fi

echo ""
echo "🧪 Send test command? (y/n)"
read -t 5 answer
if [ "$answer" = "y" ]; then
    python3 << 'EOF'
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_

ChannelFactoryInitialize(0)
cmd_pub = ChannelPublisher("rt/dex1/left/cmd", MotorCmds_)
cmd_pub.Init()

cmd = MotorCmds_()
cmd.cmds = [unitree_go_msg_dds__MotorCmd_()]
cmd.cmds[0].q = 2.7
cmd.cmds[0].kp = 5.0
cmd.cmds[0].kd = 0.05
cmd_pub.Write(cmd)
print("✅ Sent MIDDLE command (2.7 rad)")
EOF
fi
