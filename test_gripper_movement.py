#!/usr/bin/env python3
"""
Simple test to verify gripper actually moves in response to DDS commands
Monitors actual position feedback from servo
"""

import time
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_, MotorStates_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_

def test_gripper_movement(side='left'):
    """Test if gripper actually moves"""
    
    # Initialize DDS
    ChannelFactoryInitialize(0)
    
    # Setup publisher and subscriber
    cmd_topic = f"rt/dex1/{side}/cmd"
    state_topic = f"rt/dex1/{side}/state"
    
    cmd_publisher = ChannelPublisher(cmd_topic, MotorCmds_)
    cmd_publisher.Init()
    
    state_subscriber = ChannelSubscriber(state_topic, MotorStates_)
    state_subscriber.Init()
    
    print("🔍 Gripper Movement Diagnostic Test")
    print("=" * 60)
    
    # Read initial position
    print("\n📊 Reading initial position...")
    time.sleep(0.5)
    
    positions = []
    for i in range(10):
        state_msg = state_subscriber.Read()
        if state_msg and hasattr(state_msg, 'states') and state_msg.states:
            pos = float(state_msg.states[0].q)
            positions.append(pos)
        time.sleep(0.1)
    
    if positions:
        initial_pos = sum(positions) / len(positions)
        print(f"   Initial position: {initial_pos:.3f} rad ({(initial_pos/5.4)*100:.1f}%)")
    else:
        print("   ❌ No state messages received!")
        return False
    
    # Send command to close (0.0 rad)
    print("\n📤 Sending CLOSE command (0.0 rad)...")
    cmd_msg = MotorCmds_()
    cmd_msg.cmds = [unitree_go_msg_dds__MotorCmd_()]
    cmd_msg.cmds[0].q = 0.0
    cmd_msg.cmds[0].dq = 0.0
    cmd_msg.cmds[0].tau = 0.0
    cmd_msg.cmds[0].kp = 5.00
    cmd_msg.cmds[0].kd = 0.05
    cmd_publisher.Write(cmd_msg)
    
    # Monitor position for 3 seconds
    print("   Monitoring position for 3 seconds...")
    start_time = time.time()
    close_positions = []
    
    while time.time() - start_time < 3.0:
        state_msg = state_subscriber.Read()
        if state_msg and hasattr(state_msg, 'states') and state_msg.states:
            pos = float(state_msg.states[0].q)
            close_positions.append(pos)
            elapsed = time.time() - start_time
            print(f"   t={elapsed:.1f}s: {pos:.3f} rad ({(pos/5.4)*100:.1f}%)")
        time.sleep(0.2)
    
    if close_positions:
        final_close_pos = close_positions[-1]
        movement_close = abs(final_close_pos - initial_pos)
        print(f"\n   Final position: {final_close_pos:.3f} rad")
        print(f"   Movement: {movement_close:.3f} rad")
        
        if movement_close > 0.1:
            print(f"   ✅ GRIPPER MOVED {movement_close:.3f} rad!")
        else:
            print(f"   ❌ NO MOVEMENT DETECTED (only {movement_close:.3f} rad)")
    
    # Send command to open (5.4 rad)
    print("\n📤 Sending OPEN command (5.4 rad)...")
    cmd_msg.cmds[0].q = 5.4
    cmd_publisher.Write(cmd_msg)
    
    # Monitor position for 3 seconds
    print("   Monitoring position for 3 seconds...")
    start_time = time.time()
    open_positions = []
    
    while time.time() - start_time < 3.0:
        state_msg = state_subscriber.Read()
        if state_msg and hasattr(state_msg, 'states') and state_msg.states:
            pos = float(state_msg.states[0].q)
            open_positions.append(pos)
            elapsed = time.time() - start_time
            print(f"   t={elapsed:.1f}s: {pos:.3f} rad ({(pos/5.4)*100:.1f}%)")
        time.sleep(0.2)
    
    if open_positions:
        final_open_pos = open_positions[-1]
        movement_open = abs(final_open_pos - final_close_pos)
        print(f"\n   Final position: {final_open_pos:.3f} rad")
        print(f"   Movement: {movement_open:.3f} rad")
        
        if movement_open > 0.1:
            print(f"   ✅ GRIPPER MOVED {movement_open:.3f} rad!")
        else:
            print(f"   ❌ NO MOVEMENT DETECTED (only {movement_open:.3f} rad)")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 MOVEMENT SUMMARY")
    print("=" * 60)
    
    total_movement = abs(final_open_pos - initial_pos)
    
    if total_movement > 0.5:
        print(f"✅ GRIPPER IS MOVING CORRECTLY")
        print(f"   Total movement: {total_movement:.3f} rad ({(total_movement/5.4)*100:.1f}% of range)")
        return True
    else:
        print(f"❌ GRIPPER NOT MOVING")
        print(f"   Total movement: {total_movement:.3f} rad (expected > 0.5 rad)")
        print("\n🔧 Possible issues:")
        print("   1. Control loop not calling bulk_write_control_data()")
        print("   2. goto_position() not setting self.target_position")
        print("   3. Servo not responding to position commands")
        print("   4. DDS commands not being received by driver")
        return False

if __name__ == "__main__":
    import sys
    side = sys.argv[1] if len(sys.argv) > 1 else 'left'
    success = test_gripper_movement(side)
    sys.exit(0 if success else 1)
