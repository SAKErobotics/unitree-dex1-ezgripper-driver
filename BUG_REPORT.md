# Buffer Overflow in unitree_sdk2_python / CycloneDDS

## Summary
Calling `ChannelPublisher.Write()` with `MotorStates_` message causes a buffer overflow, leading to "*** buffer overflow detected ***: terminated" and confusing "'tuple' object is not callable" errors.

## Environment
- Python 3.12
- unitree_sdk2_python (latest)
- CycloneDDS Python bindings
- Linux

## Minimal Reproducer
```python
#!/usr/bin/env python3
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

# This causes buffer overflow
result = pub.Write(motor_states)

pub.Close()
```

## Expected Behavior
Message should be published successfully without crashing.

## Actual Behavior
```
*** buffer overflow detected ***: terminated
Aborted (core dumped)
```

## Workaround
Catch and ignore the "'tuple' object is not callable" error, but this is not a proper fix as it ignores memory corruption.

## Possible Causes
1. Buffer overflow in CycloneDDS C/C++ layer
2. Memory corruption in Python bindings
3. Issue with message serialization

## Impact
Critical - causes application crash and potential security vulnerability.
