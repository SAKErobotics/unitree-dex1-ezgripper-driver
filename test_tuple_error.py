#!/usr/bin/env python3
"""Test script to reproduce the tuple error"""

import time
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorStates_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_

# Initialize DDS
ChannelFactoryInitialize(0, "shm://")

# Create publisher
pub = ChannelPublisher('rt/test/state', MotorStates_)
pub.Init()

# Create message
motor_state = unitree_go_msg_dds__MotorCmd_()
motor_state.q = 1.0
motor_state.dq = 0.0
motor_state.tau = 0.1
motor_state.kp = 0.0
motor_state.kd = 0.0

motor_states = MotorStates_()
motor_states.states = [motor_state]

print(f"Created message: {motor_states}")
print(f"Message states: {motor_states.states}")
print(f"State type: {type(motor_states.states[0])}")

# Try to publish
for i in range(10):
    try:
        print(f"\nAttempt {i+1}:")
        print(f"  Write method type: {type(pub.Write)}")
        print(f"  Write callable: {callable(pub.Write)}")
        
        result = pub.Write(motor_states)
        print(f"  Success: {result}")
        
    except Exception as e:
        print(f"  Error: {e}")
        print(f"  Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        break
    
    time.sleep(0.1)

pub.Close()
