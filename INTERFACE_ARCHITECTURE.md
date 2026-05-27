# EZGripper DDS Interface Architecture

## Overview

The EZGripper driver provides **3 DDS interfaces** for different use cases:

1. **Dex1 Control Interface** - For Unitree robots (position-only)
2. **EZGripper Control Interface** - For non-Unitree robots (position + force)
3. **Telemetry Interface** - For monitoring and diagnostics (status only)

---

## 1. Dex1 Control Interface (Unitree Robots)

### Purpose
Drop-in compatible with Unitree XR teleoperate and G1 robot control systems.

### Topics
- **Command**: `rt/dex1/{left|right}/cmd`
- **State**: `rt/dex1/{left|right}/state`

### Message Types
- **Command**: `MotorCmds_` (from unitree_sdk2py)
- **State**: `MotorStates_` (from unitree_sdk2py)

### Command Message Structure
```python
MotorCmd_:
    mode: uint8           # Control mode (0 = position control)
    q: float             # Target position in radians (0.0-5.4)
    dq: float            # Target velocity (unused, set to 0.0)
    tau: float           # Target force (IGNORED - managed by GraspManager)
    kp: float            # Position gain (unused, set to 0.0)
    kd: float            # Derivative gain (unused, set to 0.0)
    reserve: uint32      # Reserved
```

### State Message Structure
```python
MotorState_:
    mode: uint8                      # GraspManager state (0=idle, 1=moving, 2=contact, 3=grasping)
    q: float                         # Current position radians (0.0-5.4)
    dq: float                        # Current velocity (0.0)
    ddq: float                       # Current acceleration (0.0)
    tau_est: float                   # Estimated force (0.0-0.1, limited)
    temperature: int16[2]            # Temperature sensors
    vol: float                       # Voltage
    sensor: uint32[2]                # Sensor data
    motorstate: uint32               # Motor state flags
    reserve: uint32[4]               # Reserved
```

### Key Features
- **Position-only control**: `q` field controls position (0.0-5.4 radians)
- **Force is managed automatically**: GraspManager handles force based on config
- **200 Hz state publishing**: High-frequency feedback for smooth teleoperation
- **Compatible with**: Unitree XR teleoperate, G1 robot control

---

## 2. EZGripper Control Interface (Non-Unitree Robots)

### Purpose
General-purpose control interface for non-Unitree robots with **force control**.

### Topics
- **Command**: `rt/ezgripper/{left|right}/cmd`
- **State**: `rt/ezgripper/{left|right}/state`

### Message Types
- **Command**: `MotorCmds_` (same as Dex1)
- **State**: `MotorStates_` (same as Dex1)

### Command Message Structure
```python
MotorCmd_:
    mode: uint8           # Control mode (0 = position control)
    q: float             # Target position in radians (0.0-5.4)
    dq: float            # Target velocity (unused, set to 0.0)
    tau: float           # Target force 0.0-1.0 (USED for force control)
    kp: float            # Position gain (unused, set to 0.0)
    kd: float            # Derivative gain (unused, set to 0.0)
    reserve: uint32      # Reserved
```

### State Message Structure
```python
MotorState_:
    mode: uint8                      # GraspManager state (0=idle, 1=moving, 2=contact, 3=grasping)
    q: float                         # Current position radians (0.0-5.4)
    dq: float                        # Current velocity (0.0)
    ddq: float                       # Current acceleration (0.0)
    tau_est: float                   # Actual force 0.0-1.0
    temperature: int16[2]            # Temperature sensors
    vol: float                       # Voltage
    sensor: uint32[2]                # Sensor data
    motorstate: uint32               # Motor state flags
    reserve: uint32[4]               # Reserved
```

### Key Difference from Dex1
**The `tau` field is actually used for force control:**
- **Dex1**: `tau` field is ignored, force managed by config
- **EZGripper**: `tau` field sets target force (0.0-1.0 = 0-100%)

### Key Features
- **Position + Force control**: Both `q` and `tau` fields are used
- **Same message structure as Dex1**: Easy to switch between interfaces
- **200 Hz state publishing**: Same high-frequency feedback
- **Force range**: 0.0-1.0 normalized (0-100%)

---

## 3. Telemetry Interface (Status/Monitoring)

### Purpose
Read-only monitoring and diagnostics interface.

### Topics
- **Telemetry**: `rt/gripper/{left|right}/telemetry`

### Message Type
- **String_** with JSON payload

### Telemetry Data
```json
{
  "timestamp": 1234567890.123,
  "position": {
    "actual_pct": 50.0,
    "commanded_pct": 50.0
  },
  "effort": {
    "actual_pct": 25.0,
    "commanded_pct": 30.0
  },
  "grasp_manager": {
    "state": "GRASPING",
    "contact_detected": true
  },
  "hardware": {
    "temperature_c": 35.0,
    "current_ma": 1200,
    "voltage_v": 12.0,
    "error": 0
  },
  "calibration": {
    "is_calibrated": true,
    "offset": 1234
  }
}
```

### Key Features
- **Read-only**: No commands, only status
- **30 Hz publishing**: Matches control loop frequency
- **Comprehensive diagnostics**: Temperature, current, errors, grasp state
- **JSON format**: Easy to parse and extend

---

## Interface Comparison

| Feature | Dex1 Interface | EZGripper Interface | Telemetry Interface |
|---------|---------------|---------------------|---------------------|
| **Purpose** | Unitree robots | Non-Unitree robots | Monitoring only |
| **Position Control** | ✅ Yes (0-5.4 rad) | ✅ Yes (0-5.4 rad) | ❌ Read-only |
| **Force Control** | ❌ No (auto-managed) | ✅ Yes (0.0-1.0) | ❌ Read-only |
| **Message Type** | MotorCmds_/States_ | MotorCmds_/States_ | String_ (JSON) |
| **State Rate** | 200 Hz | 200 Hz | 30 Hz |
| **Grasp State** | In `mode` field | In `mode` field | Detailed JSON |
| **Diagnostics** | Limited | Limited | Comprehensive |

---

## Usage Examples

### Dex1 Interface (Unitree Robots)
```python
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import MotorCmds_, MotorCmd_

# Create command publisher
cmd_pub = ChannelPublisher("rt/dex1/left/cmd", MotorCmds_)
cmd_pub.Init()

# Send position command (force is auto-managed)
cmd = MotorCmd_(
    mode=0,
    q=2.7,      # 50% open (2.7 radians)
    dq=0.0,
    tau=0.0,    # IGNORED
    kp=0.0,
    kd=0.0,
    reserve=0
)
cmds = MotorCmds_()
cmds.cmds = [cmd]
cmd_pub.Write(cmds)
```

### EZGripper Interface (Non-Unitree Robots)
```python
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import MotorCmds_, MotorCmd_

# Create command publisher
cmd_pub = ChannelPublisher("rt/ezgripper/left/cmd", MotorCmds_)
cmd_pub.Init()

# Send position + force command
cmd = MotorCmd_(
    mode=0,
    q=2.7,      # 50% open (2.7 radians)
    dq=0.0,
    tau=0.5,    # 50% force (USED)
    kp=0.0,
    kd=0.0,
    reserve=0
)
cmds = MotorCmds_()
cmds.cmds = [cmd]
cmd_pub.Write(cmds)
```

### Telemetry Interface (Monitoring)
```python
from unitree_sdk2py.core.channel import ChannelSubscriber
from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_
import json

# Create telemetry subscriber
telem_sub = ChannelSubscriber("rt/gripper/left/telemetry", String_)
telem_sub.Init()

# Read telemetry
msg = telem_sub.Read()
if msg:
    data = json.loads(msg.data)
    print(f"Position: {data['position']['actual_pct']}%")
    print(f"Temperature: {data['hardware']['temperature_c']}°C")
    print(f"Grasp State: {data['grasp_manager']['state']}")
```

---

## Configuration

All interfaces share the same configuration file (`config_default.json`):

- **Force settings**: Configured per GraspManager state (MOVING, GRASPING, IDLE)
- **Position scaling**: `max_open_percent` setting
- **Collision detection**: Stall tolerance, contact detection thresholds
- **Telemetry**: Enable/disable, rate, topic prefix

**Note**: The EZGripper interface's `tau` field overrides the config force settings.

---

## Thread Architecture

The driver runs 4 threads:

1. **Dex1 Command Thread**: Event-driven, listens on `rt/dex1/{side}/cmd`
2. **EZGripper Command Thread**: Event-driven, listens on `rt/ezgripper/{side}/cmd`
3. **Control Thread**: 30 Hz, executes commands and reads hardware
4. **State Thread**: 200 Hz, publishes to both Dex1 and EZGripper state topics

Both command threads write to the same `latest_command` variable, so only one interface should be used at a time.

---

## Migration Guide

### From Dex1 to EZGripper Interface

**Change topic names:**
```python
# Before (Dex1)
cmd_topic = "rt/dex1/left/cmd"
state_topic = "rt/dex1/left/state"

# After (EZGripper)
cmd_topic = "rt/ezgripper/left/cmd"
state_topic = "rt/ezgripper/left/state"
```

**Add force control:**
```python
# Before (Dex1) - force ignored
cmd.tau = 0.0  # Ignored

# After (EZGripper) - force used
cmd.tau = 0.5  # 50% force
```

**Everything else stays the same** - same message types, same structure.

---

## Summary

- **2 Control Interfaces**: Dex1 (Unitree) and EZGripper (general-purpose)
- **1 Status Interface**: Telemetry (monitoring only)
- **Key Difference**: EZGripper uses `tau` field for force control
- **Same Message Types**: Both control interfaces use `MotorCmds_`/`MotorStates_`
- **Easy Migration**: Just change topic names and add force control
