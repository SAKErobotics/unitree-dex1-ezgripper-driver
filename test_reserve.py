#!/usr/bin/env python3
"""Test script to check if reserve field causes buffer overflow"""

import time
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorStates_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_
import cyclonedds.idl.types as types

# Initialize DDS
ChannelFactoryInitialize(0, "shm://")

# Create publisher
pub = ChannelPublisher('rt/test/state', MotorStates_)
pub.Init()

# Create message with proper array type
motor_state = unitree_go_msg_dds__MotorCmd_()
motor_state.q = 1.0
motor_state.dq = 0.0
motor_state.tau = 0.1
motor_state.kp = 0.0
motor_state.kd = 0.0

# Try different reserve field values
test_cases = [
    ("Default list", [0, 0, 0]),
    ("Empty list", []),
    ("Proper array", types.array[types.uint32, 3]([0, 0, 0])),
    ("Single value", [0]),
    ("Large values", [0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF]),
]

for name, reserve_value in test_cases:
    try:
        print(f"\nTesting {name}: {reserve_value}")
        motor_state.reserve = reserve_value
        print(f"  Set reserve to: {motor_state.reserve}")
        
        motor_states = MotorStates_()
        motor_states.states = [motor_state]
        
        result = pub.Write(motor_states)
        print(f"  Success: {result}")
        
    except Exception as e:
        print(f"  Error: {e}")
        # Don't break - continue testing other cases

pub.Close()
