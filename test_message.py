#!/usr/bin/env python3
"""Test script to check message construction"""

from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorStates_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_

# Create message
motor_state = unitree_go_msg_dds__MotorCmd_()
motor_state.q = 1.0
motor_state.dq = 0.0
motor_state.tau = 0.1
motor_state.kp = 0.0
motor_state.kd = 0.0

print(f"Created motor_state: {motor_state}")
print(f"  q: {motor_state.q}")
print(f"  dq: {motor_state.dq}")
print(f"  tau: {motor_state.tau}")
print(f"  kp: {motor_state.kp}")
print(f"  kd: {motor_state.kd}")

# Try MotorStates_
motor_states = MotorStates_()
print(f"\nCreated MotorStates_: {motor_states}")
print(f"  states field: {hasattr(motor_states, 'states')}")

# Try to set states
try:
    motor_states.states = [motor_state]
    print(f"  Set states successfully: {motor_states.states}")
    print(f"  Length: {len(motor_states.states)}")
except Exception as e:
    print(f"  Error setting states: {e}")
    import traceback
    traceback.print_exc()

# Try MotorCmds_ for comparison
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_
motor_cmds = MotorCmds_()
print(f"\nCreated MotorCmds_: {motor_cmds}")
print(f"  cmds field: {hasattr(motor_cmds, 'cmds')}")

try:
    motor_cmds.cmds = [motor_state]
    print(f"  Set cmds successfully: {motor_cmds.cmds}")
    print(f"  Length: {len(motor_cmds.cmds)}")
except Exception as e:
    print(f"  Error setting cmds: {e}")
    import traceback
    traceback.print_exc()
