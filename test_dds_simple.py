#!/usr/bin/env python3
"""
Simple DDS test - send and receive on same topics as GUI/driver
"""

import time
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_, MotorStates_, MotorCmd_

# Initialize DDS
ChannelFactoryInitialize(0)

# Create publisher (like GUI)
cmd_pub = ChannelPublisher("rt/dex1/left/cmd", MotorCmds_)
cmd_pub.Init()

# Create subscriber (like driver)
cmd_sub = ChannelSubscriber("rt/dex1/left/cmd", MotorCmds_)
cmd_sub.Init()

print("Sending test command...")

# Send a command
motor_cmd = MotorCmd_(
    mode=0,
    q=2.7,
    dq=0.0,
    tau=0.3,
    kp=0.0,
    kd=0.0,
    reserve=[0, 0, 0]
)
motor_cmds = MotorCmds_()
motor_cmds.cmds = [motor_cmd]

result = cmd_pub.Write(motor_cmds)
print(f"Write result: {result}")

# Try to read it back
time.sleep(0.1)  # Give DDS time to propagate

for i in range(10):
    msg = cmd_sub.Read()
    if msg:
        print(f"✅ Received message! cmds={len(msg.cmds) if hasattr(msg, 'cmds') and msg.cmds else 0}")
        if msg.cmds:
            print(f"   q={msg.cmds[0].q}, tau={msg.cmds[0].tau}")
        break
    else:
        print(f"Attempt {i+1}: No message")
        time.sleep(0.1)
else:
    print("❌ Never received message - DDS communication issue")
