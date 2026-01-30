#!/usr/bin/env python3
"""Test if DDS commands actually move the servo"""

import time
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_

# Initialize DDS
ChannelFactoryInitialize(0, "shm://")

# Create publisher for left gripper command
pub = ChannelPublisher('rt/dex1/left/cmd', MotorCmds_)
pub.Init()

# Create command message
motor_cmd = unitree_go_msg_dds__MotorCmd_()
motor_cmd.q = 0.0      # Open position
motor_cmd.dq = 0.0
motor_cmd.tau = 0.0
motor_cmd.kp = 5.0
motor_cmd.kd = 0.05

motor_cmds = MotorCmds_()
motor_cmds.cmds = [motor_cmd]

print("Sending open command...")
pub.Write(motor_cmds)
time.sleep(2)

motor_cmd.q = 5.0      # Close position
motor_cmds.cmds = [motor_cmd]

print("Sending close command...")
pub.Write(motor_cmds)
time.sleep(2)

motor_cmd.q = 2.5      # Middle position
motor_cmds.cmds = [motor_cmd]

print("Sending middle command...")
pub.Write(motor_cmds)
time.sleep(2)

pub.Close()
print("Done!")
