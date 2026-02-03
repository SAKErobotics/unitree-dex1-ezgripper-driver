#!/usr/bin/env python3
"""
Test G1 teleoperation flow - sends commands at 200Hz like real G1 stack
"""

import time
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_, MotorCmd_

# Initialize DDS on domain 0 (same as driver and GUI)
ChannelFactoryInitialize(0)

# Create command publisher (simulates G1 teleoperation)
cmd_pub = ChannelPublisher("rt/dex1/left/cmd", MotorCmds_)
cmd_pub.Init()

print("Simulating G1 teleoperation - sending commands at 200Hz")
print("Watch the driver terminal for 📨 and 📥 messages")
print("Press Ctrl+C to stop\n")

# Test sequence: open -> close -> open
positions = [
    (5.4, "OPEN"),   # Fully open
    (2.7, "HALF"),   # Half open  
    (0.0, "CLOSE"),  # Fully closed
]

position_idx = 0
cycle_count = 0
last_change = time.time()

try:
    while True:
        # Change position every 3 seconds
        if time.time() - last_change > 3.0:
            position_idx = (position_idx + 1) % len(positions)
            last_change = time.time()
            q_target, name = positions[position_idx]
            print(f"\n→ Commanding {name} (q={q_target:.1f} rad)")
        
        q_target, name = positions[position_idx]
        
        # Create command message
        motor_cmd = MotorCmd_(
            mode=0,
            q=q_target,
            dq=0.0,
            tau=0.3,
            kp=0.0,
            kd=0.0,
            reserve=[0, 0, 0]
        )
        
        motor_cmds = MotorCmds_()
        motor_cmds.cmds = [motor_cmd]
        
        # Publish at 200Hz
        cmd_pub.Write(motor_cmds)
        
        cycle_count += 1
        if cycle_count % 200 == 0:
            print(f"  Sent {cycle_count} commands ({name})")
        
        # Sleep to maintain 200Hz (5ms period)
        time.sleep(0.005)
        
except KeyboardInterrupt:
    print(f"\n\nStopped after {cycle_count} commands")
