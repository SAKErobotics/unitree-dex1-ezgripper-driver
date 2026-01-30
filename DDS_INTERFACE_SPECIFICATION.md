# Unitree G1 Dex1 Hand DDS Interface Specification

## Document Purpose

This document describes the DDS (Data Distribution Service) interface used for controlling Unitree G1 Dex1-1 grippers. This interface is used by the EZGripper DDS driver to provide drop-in compatibility with the official Unitree Dex1-1 gripper hardware.

---

## Source References

All interface definitions are derived from the official Unitree SDK2 repository:

**Repository:** https://github.com/unitreerobotics/unitree_sdk2

**Message Definition Files (C++ Headers):**

1. **MotorCmd_.hpp**
   - URL: https://github.com/unitreerobotics/unitree_sdk2/blob/main/include/unitree/idl/hg/MotorCmd_.hpp
   - Defines individual motor command structure

2. **MotorState_.hpp**
   - URL: https://github.com/unitreerobotics/unitree_sdk2/blob/main/include/unitree/idl/hg/MotorState_.hpp
   - Defines individual motor state structure

3. **HandCmd_.hpp**
   - URL: https://github.com/unitreerobotics/unitree_sdk2/blob/main/include/unitree/idl/hg/HandCmd_.hpp
   - Defines hand command container (array of motor commands)

4. **HandState_.hpp**
   - URL: https://github.com/unitreerobotics/unitree_sdk2/blob/main/include/unitree/idl/hg/HandState_.hpp
   - Defines hand state container (array of motor states + sensors)

**Python Bindings:**

- Repository: https://github.com/unitreerobotics/unitree_sdk2_python
- Location: `unitree_sdk2py/idl/default/` (convenience imports)
- Generated from: `unitree_sdk2py/idl/unitree_hg/msg/dds_/`

**Control Rate Reference:**

- Repository: https://github.com/unitreerobotics/xr_teleoperate
- File: `teleop/robot_control/robot_hand_unitree.py`
- Command rate: 200 Hz (5ms period)
- State subscription: 500 Hz (2ms period)

---

## DDS Communication Rates

### G1 XR Teleoperate System

**Command Publishing:**
- Rate: **200 Hz** (every 5ms)
- Loop: `time.sleep(1/fps)` where `fps=200.0`
- Publishes motor commands to gripper

**State Subscription:**
- Rate: **500 Hz** (every 2ms)
- Loop: `time.sleep(0.002)`
- Receives motor state from gripper

**XR Input Processing:**
- Rate: **100 Hz** (every 10ms)
- Hand tracking/controller input rate
- Commands are interpolated to 200 Hz for smooth control

### Dex1-1 Gripper (Official Hardware)

**Command Reception:**
- Listens on DDS topics at 200 Hz
- Executes motor commands immediately

**State Publishing:**
- Publishes state at 200+ Hz
- Provides real-time position/torque feedback

---

## Message Structure Definitions

### Namespace

All messages are in namespace: `unitree_hg::msg::dds_`

**Meaning:**
- `unitree_hg` = Unitree Humanoid G1 robot
- `msg` = Message definitions
- `dds_` = DDS-specific bindings

---

## MotorCmd_ (Motor Command)

**DDS Type:** `"unitree_hg::msg::dds_::MotorCmd_"`

**Purpose:** Command for a single motor (gripper motor)

**Structure:**
```cpp
class MotorCmd_ {
    uint8_t mode;      // Motor control mode
    float q;           // Target position (radians)
    float dq;          // Target velocity (rad/s)
    float tau;         // Target torque (Nm)
    float kp;          // Position gain
    float kd;          // Derivative gain
    uint32_t reserve;  // Reserved field
};
```

**Field Details:**

| Field | Type | Units | Description | Dex1-1 Usage |
|-------|------|-------|-------------|--------------|
| `mode` | uint8 | - | Control mode (0=position, 1=velocity, etc.) | Always 0 (position mode) |
| `q` | float | radians | Target position (0.0 = closed, 6.28 = open) | Primary control input |
| `dq` | float | rad/s | Target velocity | Unused (set to 0.0) |
| `tau` | float | Nm | Target torque | Unused (set to 0.0) |
| `kp` | float | - | Position gain | Unused (set to 0.0) |
| `kd` | float | - | Derivative gain | Unused (set to 0.0) |
| `reserve` | uint32 | - | Reserved for future use | Set to 0 |

**Position Mapping for Dex1-1:**
- `q = 0.0` rad → Gripper fully closed (0%)
- `q = 3.14` rad (π) → Gripper 50% open
- `q = 6.28` rad (2π) → Gripper fully open (100%)

**Motor ID:**
- Motor ID is set as an attribute after construction: `motor_cmd.id = 1` (left) or `2` (right)

---

## HandCmd_ (Hand Command Container)

**DDS Type:** `"unitree_hg::msg::dds_::HandCmd_"`

**Purpose:** Container for one or more motor commands

**Structure:**
```cpp
class HandCmd_ {
    std::vector<MotorCmd_> motor_cmd;  // Array of motor commands
    std::array<uint32_t, 4> reserve;   // Reserved fields
};
```

**Field Details:**

| Field | Type | Description | Dex1-1 Usage |
|-------|------|-------------|--------------|
| `motor_cmd` | vector<MotorCmd_> | Array of motor commands | Contains 1 element (single gripper motor) |
| `reserve` | uint32[4] | Reserved fields | All zeros [0, 0, 0, 0] |

**Dex1-1 Usage:**
- Array contains exactly **1 motor command**
- `motor_cmd[0]` controls the gripper motor
- Motor ID in `motor_cmd[0].id` identifies left (1) or right (2) gripper

---

## MotorState_ (Motor State)

**DDS Type:** `"unitree_hg::msg::dds_::MotorState_"`

**Purpose:** State feedback for a single motor

**Structure:**
```cpp
class MotorState_ {
    uint8_t mode;                    // Current motor mode
    float q;                         // Current position (radians)
    float dq;                        // Current velocity (rad/s)
    float ddq;                       // Current acceleration (rad/s²)
    float tau_est;                   // Estimated torque (Nm)
    std::array<int16_t, 2> temperature;  // Temperature sensors [°C]
    float vol;                       // Motor voltage (V)
    std::array<uint32_t, 2> sensor;  // Additional sensor data
    uint32_t motorstate;             // Motor state flags
    std::array<uint32_t, 4> reserve; // Reserved fields
};
```

**Field Details:**

| Field | Type | Units | Description | Dex1-1 Usage |
|-------|------|-------|-------------|--------------|
| `mode` | uint8 | - | Current control mode | 0 (position mode) |
| `q` | float | radians | Current position (0.0-6.28) | Actual gripper position |
| `dq` | float | rad/s | Current velocity | Set to 0.0 |
| `ddq` | float | rad/s² | Current acceleration | Set to 0.0 |
| `tau_est` | float | Nm | Estimated torque | Grip force / 10.0 |
| `temperature` | int16[2] | °C | Temperature readings | [25, 25] (fixed) |
| `vol` | float | V | Motor voltage | 12.0 (nominal) |
| `sensor` | uint32[2] | - | Sensor data | [0, 0] (unused) |
| `motorstate` | uint32 | - | State flags | 0 (normal) |
| `reserve` | uint32[4] | - | Reserved fields | [0, 0, 0, 0] |

**Motor ID:**
- Motor ID is set as an attribute: `motor_state.id = 1` (left) or `2` (right)

**Position Mapping:**
- Same as MotorCmd_: 0.0 rad = closed, 6.28 rad = open

**Torque Feedback:**
- `tau_est` provides grip force indication
- Non-zero when gripper is gripping an object
- Zero during free movement

---

## HandState_ (Hand State Container)

**DDS Type:** `"unitree_hg::msg::dds_::HandState_"`

**Purpose:** Complete hand state including motors, sensors, and power

**Structure (Full Dex3-1 Hand):**
```cpp
class HandState_ {
    std::vector<MotorState_> motor_state;           // Array of motor states
    std::vector<PressSensorState_> press_sensor_state;  // Pressure sensors
    IMUState_ imu_state;                            // IMU data
    float power_v;                                  // Power voltage (V)
    float power_a;                                  // Power current (A)
    float system_v;                                 // System voltage (V)
    float device_v;                                 // Device voltage (V)
    std::array<uint32_t, 2> error;                  // Error flags
    std::array<uint32_t, 2> reserve;                // Reserved fields
};
```

**Field Details:**

| Field | Type | Description | Dex1-1 Usage |
|-------|------|-------------|--------------|
| `motor_state` | vector<MotorState_> | Array of motor states | Contains 1 element |
| `press_sensor_state` | vector<PressSensorState_> | Pressure sensor data | Empty (no sensors) |
| `imu_state` | IMUState_ | IMU orientation/accel | Default/zero values |
| `power_v` | float | Power supply voltage | 0.0 (not monitored) |
| `power_a` | float | Power supply current | 0.0 (not monitored) |
| `system_v` | float | System voltage | 0.0 (not monitored) |
| `device_v` | float | Device voltage | 0.0 (not monitored) |
| `error` | uint32[2] | Error flags | [0, 0] (no errors) |
| `reserve` | uint32[2] | Reserved fields | [0, 0] |

**Dex1-1 Simplified Usage:**
- Only `motor_state` array is populated
- Contains exactly **1 motor state**
- All other fields set to default/zero values
- Pressure sensors not available on Dex1-1 gripper

---

## DDS Topics (xr_teleoperate Interface)

### Topic Naming Convention

**Format:** `rt/dex1/{side}/{direction}`

Where:
- `rt` = Real-time communication prefix
- `dex1` = Dex1 hand identifier
- `{side}` = `left` or `right`
- `{direction}` = `cmd` (command) or `state` (state)

### Command Topics (Incoming to Gripper)

**Left Gripper:**
- Topic: `rt/dex1/left/cmd`
- Type: `MotorCmds_`
- Direction: G1 XR → Gripper
- Rate: 200 Hz (control loop)
- QoS: Default (ChannelPublisher handles internally)

**Right Gripper:**
- Topic: `rt/dex1/right/cmd`
- Type: `MotorCmds_`
- Direction: G1 XR → Gripper
- Rate: 200 Hz (control loop)
- QoS: Default (ChannelPublisher handles internally)

### State Topics (Outgoing from Gripper)

**Left Gripper:**
- Topic: `rt/dex1/left/state`
- Type: `MotorStates_`
- Direction: Gripper → G1 XR
- Rate: 500 Hz (subscriber polling at 0.002s)
- QoS: Default (ChannelSubscriber handles internally)

**Right Gripper:**
- Topic: `rt/dex1/right/state`
- Type: `MotorStates_`
- Direction: Gripper → G1 XR
- Rate: 500 Hz (subscriber polling at 0.002s)
- QoS: Default (ChannelSubscriber handles internally)

### Message Structure

#### Command Message (MotorCmds_)
```python
# xr_teleoperate creates command like this:
self.left_gripper_msg = MotorCmds_()
self.left_gripper_msg.cmds = [unitree_go_msg_dds__MotorCmd_()]
self.left_gripper_msg.cmds[0].q = position_in_radians  # Main control field
self.left_gripper_msg.cmds[0].dq = 0.0  # Velocity
self.left_gripper_msg.cmds[0].tau = 0.0  # Torque
# kp, kd, mode are set but not used for basic position control
```

#### State Message (MotorStates_)
```python
# xr_teleoperate reads state like this:
left_gripper_msg = self.LeftGripperState_subscriber.Read()
position = left_gripper_msg.states[0].q  # Position in radians
# Other fields available: tau_est, dq, temperature, etc.
```

---

## Message Flow Example

### Commanding Gripper to 50% Open

**1. G1 XR Publishes Command (200 Hz):**
```python
motor_cmd = MotorCmd_(
    mode=0,
    q=3.14,      # 50% open (π radians)
    dq=0.0,
    tau=0.0,
    kp=0.0,
    kd=0.0,
    reserve=0
)
motor_cmd.id = 1  # Left gripper

hand_cmd = HandCmd_(
    motor_cmd=[motor_cmd],
    reserve=[0, 0, 0, 0]
)

# Publish to rt/dex1/left/cmd
publisher.write(hand_cmd)
```

**2. Gripper Receives and Executes:**
- Reads `motor_cmd[0].q = 3.14` radians
- Converts to 50% position
- Sends command to servo hardware

**3. Gripper Publishes State (200+ Hz):**
```python
motor_state = MotorState_(
    mode=0,
    q=3.14,          # Current position
    dq=0.0,
    ddq=0.0,
    tau_est=0.5,     # Grip force (if gripping)
    temperature=[25, 25],
    vol=12.0,
    sensor=[0, 0],
    motorstate=0,
    reserve=[0, 0, 0, 0]
)
motor_state.id = 1  # Left gripper

hand_state = HandState_(
    motor_state=[motor_state],
    press_sensor_state=[],  # Empty for Dex1-1
    imu_state=IMUState_(),  # Default
    power_v=0.0,
    power_a=0.0,
    system_v=0.0,
    device_v=0.0,
    error=[0, 0],
    reserve=[0, 0]
)

# Publish to rt/dex1/left/state
publisher.write(hand_state)
```

**4. G1 XR Receives State:**
- Reads `motor_state[0].q = 3.14` radians
- Confirms gripper reached target position
- Uses for closed-loop control

---

## Implementation Notes

### EZGripper DDS Driver

**Message Type Imports:**
```python
from unitree_sdk2py.idl.default import HGHandCmd_, HGMotorCmd_, HGHandState_, HGMotorState_
```

**Topic Creation:**
```python
from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.sub import DataReader
from cyclonedds.pub import DataWriter

participant = DomainParticipant(domain_id=0)

cmd_topic = Topic(participant, "rt/dex1/left/cmd", HGHandCmd_)
state_topic = Topic(participant, "rt/dex1/left/state", HGHandState_)

cmd_reader = DataReader(participant, cmd_topic)
state_writer = DataWriter(participant, state_topic)
```

### Position Conversion

**Dex1 Radians → EZGripper Percentage:**
```python
def dex1_to_ezgripper(q_radians: float) -> float:
    if q_radians <= 0.1:
        return 0.0    # Close
    elif q_radians >= 6.0:
        return 100.0  # Open
    else:
        return (q_radians / (2.0 * math.pi)) * 100.0
```

**EZGripper Percentage → Dex1 Radians:**
```python
def ezgripper_to_dex1(position_pct: float) -> float:
    return (position_pct / 100.0) * 2.0 * math.pi
```

### Command Reception

```python
# Take up to 10 samples, keep latest
samples = cmd_reader.take(N=10)

if samples:
    latest = samples[-1]
    if latest and latest.motor_cmd and len(latest.motor_cmd) > 0:
        motor_cmd = latest.motor_cmd[0]
        target_position = dex1_to_ezgripper(motor_cmd.q)
        # Execute command...
```

### State Publishing

```python
# Create motor state
motor_state = HGMotorState_(
    mode=0,
    q=ezgripper_to_dex1(current_position_pct),
    dq=0.0,
    ddq=0.0,
    tau_est=current_effort_pct / 10.0,
    temperature=[25, 25],
    vol=12.0,
    sensor=[0, 0],
    motorstate=0,
    reserve=[0, 0, 0, 0]
)
motor_state.id = 1  # Left gripper

# Wrap in hand state
hand_state = HGHandState_(
    motor_state=[motor_state],
    reserve=[0, 0, 0, 0]
)

# Publish
state_writer.write(hand_state)
```

---

## Compatibility

This DDS interface provides **drop-in compatibility** with:

1. **Unitree G1 XR Teleoperate System**
   - Repository: https://github.com/unitreerobotics/xr_teleoperate
   - Uses same message types and topics
   - Expects 200 Hz command/state rates

2. **Unitree Dex1-1 Service**
   - Repository: https://github.com/unitreerobotics/dex1_1_service
   - Official serial-to-DDS bridge for Dex1-1 hardware
   - Uses identical protocol

3. **Unitree G1 Robot Control Software**
   - Built-in hand control uses this protocol
   - Seamless integration with robot control stack

---

## Version Information

**Document Version:** 1.0
**Date:** 2026-01-29
**Based on:** unitree_sdk2 (main branch, January 2026)
**DDS Implementation:** CycloneDDS 0.10.2+
**Python Bindings:** unitree_sdk2_python (latest)

---

## Software Architecture: Complete Data Flow

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    UNITREE ROBOT SYSTEM (Teleop)                    │
│                                                                     │
│  Publishes: rt/dex1/{left|right}/cmd (HGHandCmd)                  │
│             QoS: RELIABLE, 30-50 Hz                                │
│                                                                     │
│  Subscribes: rt/dex1/{left|right}/state (HGHandState)             │
│              QoS: BEST_EFFORT, expects 200 Hz                      │
└─────────────────────────────────────────────────────────────────────┘
                            ↓ DDS                    ↑ DDS
                            ↓ (CycloneDDS)           ↑ (CycloneDDS)
                            ↓                        ↑
┌─────────────────────────────────────────────────────────────────────┐
│              EZGRIPPER DDS DRIVER (ezgripper_dds_driver.py)        │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ DDS LAYER (Dynamixel Protocol 2.0 @ 1 Mbps)               │  │
│  │                                                             │  │
│  │ cmd_reader (RELIABLE):                                     │  │
│  │   - Reads HGHandCmd.motor_cmd[0].q (radians: 0-6.28)     │  │
│  │   - Reads HGHandCmd.motor_cmd[0].tau (effort: 0-1.0)     │  │
│  │   - Converts q → position_pct (0-100%)                    │  │
│  │   - Stores as GripperCommand                              │  │
│  │                                                             │  │
│  │ state_writer (BEST_EFFORT):                                │  │
│  │   - Publishes HGHandState @ 200 Hz                        │  │
│  │   - motor_state.q (predicted position in radians)         │  │
│  │   - motor_state.tau_est (effort/10.0)                     │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                            ↓                        ↑               │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ CONTROL LAYER (Multi-threaded)                             │  │
│  │                                                             │  │
│  │ Control Thread @ 30 Hz:                                    │  │
│  │   1. receive_command() - Read DDS command                  │  │
│  │   2. execute_command() - Send to hardware                  │  │
│  │   3. read_actual_position() - Read from hardware (5 Hz)   │  │
│  │                                                             │  │
│  │ State Thread @ 200 Hz:                                     │  │
│  │   1. update_predicted_position() - Predict motion         │  │
│  │   2. publish_state() - Send to DDS                        │  │
│  │                                                             │  │
│  │ Shared State (thread-safe with lock):                      │  │
│  │   - commanded_position_pct                                 │  │
│  │   - predicted_position_pct (for 200 Hz publishing)        │  │
│  │   - actual_position_pct (from hardware @ 5 Hz)            │  │
│  │   - current_effort_pct                                     │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                            ↓                        ↑               │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ HARDWARE ABSTRACTION (libezgripper)                        │  │
│  │                                                             │  │
│  │ Gripper class (ezgripper_base.py):                        │  │
│  │   - set_max_effort(effort_pct)                            │  │
│  │   - _goto_position(scaled_position)                       │  │
│  │   - get_position() → position_pct                         │  │
│  │   - calibrate() → sets zero_positions[0]                  │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                            ↓                        ↑               │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ DYNAMIXEL PROTOCOL 2.0 LAYER (lib_robotis.py)             │  │
│  │                                                             │  │
│  │ Robotis_Servo class:                                       │  │
│  │   - write_address(addr, data) → WRITE packet              │  │
│  │   - read_address(addr, len) → READ packet                 │  │
│  │   - write_word(addr, word) → 2-byte write                 │  │
│  │   - read_word(addr) → 2-byte read                         │  │
│  │                                                             │  │
│  │ Packet Format (Protocol 2.0):                              │  │
│  │   [0xFF, 0xFF, 0xFD, 0x00, ID, LEN_L, LEN_H,             │  │
│  │    INST, ADDR_L, ADDR_H, DATA..., CRC_L, CRC_H]          │  │
│  │                                                             │  │
│  │ Key Registers (MX-64 Protocol 2.0):                       │  │
│  │   - 11: Operating Mode (0=Current, 3=Position)            │  │
│  │   - 64: Torque Enable (0=Off, 1=On)                       │  │
│  │   - 70: Hardware Error Status                             │  │
│  │   - 116: Goal Position (4 bytes)                          │  │
│  │   - 126: Present Current (2 bytes)                        │  │
│  │   - 132: Present Position (4 bytes)                       │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                            ↓ Serial                 ↑ Serial
                            ↓ 1 Mbps                 ↑ 1 Mbps
                            ↓ RS-485                 ↑ RS-485
┌─────────────────────────────────────────────────────────────────────┐
│                    DYNAMIXEL MX-64 SERVO                            │
│                                                                     │
│  Dynamixel Protocol 2.0 @ 1 Mbps                                   │
│  Control Table: Position Control Mode                              │
│  Receives: Goal Position, Torque Enable, Operating Mode           │
│  Reports: Present Position, Present Current, Hardware Errors      │
└─────────────────────────────────────────────────────────────────────┘
```

### Command Path (Unitree → EZGripper)

**1. Teleop publishes** `HGHandCmd` on `rt/dex1/left/cmd` (RELIABLE, ~30 Hz)
   - `motor_cmd[0].q`: 0-6.28 radians (0=closed, 6.28=open)
   - `motor_cmd[0].tau`: 0-1.0 (effort, currently ignored)

**2. DDS Layer receives** via `cmd_reader` (RELIABLE subscriber)
   - Converts `q` radians → `position_pct` (0-100%)
   - Formula: `position_pct = (q / 6.28) * 100`

**3. Control Thread** @ 30 Hz:
   - `receive_command()`: Stores as `GripperCommand`
   - `execute_command()`: 
     - Calls `gripper.set_max_effort(effort_pct)` if changed
     - Calls `gripper._goto_position(scaled_pos)`

**4. Hardware Abstraction** (ezgripper_base.py):
   - `_goto_position()`: Scales position to servo units
   - Calls `servo.write_word(116, goal_position)` (Goal Position register)

**5. Protocol 2.0 Layer** (lib_robotis.py):
   - `write_word()` → `write_address(116, [pos_l, pos_h, 0, 0])`
   - Constructs packet: `[0xFF, 0xFF, 0xFD, 0x00, 1, 9, 0, 0x03, 116, 0, pos_bytes..., CRC]`
   - Sends via serial @ 1 Mbps with 1ms delay

**6. Servo receives** and moves to goal position

### State Path (EZGripper → Unitree)

**1. Control Thread** @ 30 Hz (actual reads @ 5 Hz):
   - `read_actual_position()`: Every 6th cycle
   - Calls `gripper.get_position()` → `position_pct`

**2. Hardware Abstraction**:
   - `get_position()`: Calls `servo.read_word(132)` (Present Position)

**3. Protocol 2.0 Layer**:
   - `read_word()` → `read_address(132, 4)`
   - Constructs READ packet: `[0xFF, 0xFF, 0xFD, 0x00, 1, 7, 0, 0x02, 132, 0, 4, 0, CRC]`
   - Waits for response with 0.5s timeout
   - Parses: `[0xFF, 0xFF, 0xFD, 0x00, 1, LEN, INST, ERR, DATA..., CRC]`

**4. State Thread** @ 200 Hz:
   - `update_predicted_position()`: Interpolates between actual and commanded
   - Uses `movement_speed` (50%/sec) to predict smooth motion
   - **Never overshoots** commanded position
   - **Never reverses** direction

**5. DDS Layer publishes** via `state_writer` (BEST_EFFORT):
   - Converts `predicted_position_pct` → `q` radians
   - Formula: `q = (position_pct / 100.0) * 6.28`
   - Publishes `HGHandState` with `motor_state.q` and `motor_state.tau_est`

**6. Teleop receives** state updates @ 200 Hz for smooth visualization

### QoS Policy Configuration

**Command Topic:**
```python
cmd_qos = Qos(
    reliability=Policy.Reliability.Reliable,
    durability=Policy.Durability.Volatile
)
cmd_reader = DataReader(participant, cmd_topic, qos=cmd_qos)
```

**State Topic:**
```python
state_qos = Qos(
    reliability=Policy.Reliability.BestEffort,
    durability=Policy.Durability.Volatile
)
state_writer = DataWriter(participant, state_topic, qos=state_qos)
```

**Rationale:**
- **Commands (RELIABLE)**: Critical control data must not be lost
- **State (BEST_EFFORT)**: High-frequency updates, latest data most important

### Dynamixel Protocol 2.0 Packet Structure

**Packet Header:**
- `[0xFF, 0xFF, 0xFD, 0x00]` - Fixed header (4 bytes)

**Packet Body:**
- `ID` - Servo ID (1 byte)
- `LEN_L, LEN_H` - Packet length (2 bytes, little-endian)
- `INST` - Instruction code (1 byte)
- `ADDR_L, ADDR_H` - Register address (2 bytes, little-endian)
- `DATA...` - Data bytes (variable length)

**Packet Footer:**
- `CRC_L, CRC_H` - CRC-16 checksum (2 bytes, little-endian)

**Key Instructions:**
- `0x02` - READ: Read data from control table
- `0x03` - WRITE: Write data to control table

**Critical Registers (MX-64):**

| Register | Size | Name | Description |
|----------|------|------|-------------|
| 11 | 1 byte | Operating Mode | 0=Current, 3=Position, 4=Extended Position |
| 64 | 1 byte | Torque Enable | 0=Disabled, 1=Enabled |
| 70 | 1 byte | Hardware Error Status | Bitmask of hardware errors |
| 116 | 4 bytes | Goal Position | Target position (0-4095) |
| 126 | 2 bytes | Present Current | Current motor current (signed) |
| 132 | 4 bytes | Present Position | Actual position (0-4095) |

### Timing and Performance

**Communication Rates:**
- **DDS Command Rate**: 30-50 Hz (from teleop)
- **Serial Control Rate**: 30 Hz (limited by serial latency)
- **Actual Position Read**: 5 Hz (every 6th control cycle)
- **DDS State Publish**: 200 Hz (predicted, smooth for teleop)

**Serial Communication:**
- **Baudrate**: 1 Mbps (1,000,000 baud)
- **Timeout**: 0.5 seconds for response
- **Post-send delay**: 1ms for servo processing
- **Port stabilization**: 100ms after open

**Architecture Benefits:**
- Provides **smooth 200 Hz state feedback** to robot
- Works within **30 Hz serial communication constraint**
- Predictive state prevents jitter in teleoperation
- Thread-safe shared state for concurrent access

---

## Related Documentation

- [PREDICTIVE_STATE_ALGORITHM.md](./PREDICTIVE_STATE_ALGORITHM.md) - Predictive state publishing for 200 Hz feedback
- [README.md](./README.md) - EZGripper DDS Driver overview and setup
- Unitree SDK2 Documentation: https://support.unitree.com/home/zh/developer
