#!/usr/bin/env python3
"""Test serialization without DDS"""

from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorStates_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_
import cyclonedds.idl.types as types

# Create message
motor_state = unitree_go_msg_dds__MotorCmd_()
motor_state.q = 1.0
motor_state.dq = 0.0
motor_state.tau = 0.1
motor_state.kp = 0.0
motor_state.kd = 0.0
motor_state.reserve = [0, 0, 0]

print(f"Created motor_state: {motor_state}")

# Try to serialize
try:
    print("Attempting to serialize motor_state...")
    buffer = motor_state.serialize()
    print(f"  Serialized to {len(buffer)} bytes")
except Exception as e:
    print(f"  Error: {e}")
    import traceback
    traceback.print_exc()

# Try MotorStates_
motor_states = MotorStates_()
motor_states.states = [motor_state]

print(f"\nCreated motor_states: {motor_states}")

try:
    print("Attempting to serialize motor_states...")
    buffer = motor_states.serialize()
    print(f"  Serialized to {len(buffer)} bytes")
except Exception as e:
    print(f"  Error: {e}")
    import traceback
    traceback.print_exc()
