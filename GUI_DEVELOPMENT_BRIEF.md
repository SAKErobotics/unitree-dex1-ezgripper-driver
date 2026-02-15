# EZGripper Interface Capabilities Reference

**Purpose**: This document describes the available interfaces, capabilities, and technical context for the EZGripper DDS control system. Use this as a reference for understanding what the system can do and how to interact with it.

---

## Project Overview

**EZGripper DDS Driver** is a ROS2-like DDS-based control system for Dynamixel-powered grippers. The system uses:
- **DDS (Data Distribution Service)** for pub/sub communication
- **Dynamixel MX-64 servos** in Extended Position Control Mode (Mode 5)
- **Smart Grasp Algorithm** with automatic contact detection
- **Thermal management** and error handling

---

## Architecture

### DDS Communication

**Publisher (Driver → GUI)**:
- **Topic**: `rt/ezgripper_motor_states`
- **Rate**: 200 Hz
- **Message Type**: Custom motor state message
- **Fields**:
  ```python
  {
      'position': float,      # 0-100% (0=closed, 100=open)
      'velocity': float,      # degrees/sec
      'effort': float,        # 0-100% current limit
      'temperature': int,     # Celsius
      'voltage': float,       # Volts
      'current': float,       # mA (unreliable in Mode 5)
      'error': int,           # Hardware error status
      'is_moving': bool,      # Movement status
      'grasp_state': str      # 'idle', 'moving', 'contact', 'grasping'
  }
  ```

**Subscriber (GUI → Driver)**:
- **Topic**: `rt/ezgripper_motor_commands`
- **Message Type**: Custom motor command message
- **Fields**:
  ```python
  {
      'position': float,      # Target position 0-100%
      'effort': float,        # Force limit 0-100%
      'velocity': float       # Speed limit (optional)
  }
  ```

### Control Flow

```
GUI Command → DDS Topic → Driver → GraspManager → Servo Hardware
                                         ↓
GUI Display ← DDS Topic ← Driver ← Sensor Data
```

---

## Key Components

### 1. DDS Driver (`ezgripper_dds_driver.py`)

**Main class**: `CorrectedEZGripperDriver`

**Key features**:
- Auto-discovery of gripper devices
- Calibration persistence via `/tmp/ezgripper_device_config.json`
- Multi-threaded: 30Hz control loop + 200Hz state publishing
- Integrates `GraspManager` for intelligent force control

**Running the driver**:
```bash
# Left gripper
python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0

# Right gripper
python3 ezgripper_dds_driver.py --side right --dev /dev/ttyUSB1
```

**Log file**: `/tmp/driver_test.log`

### 2. Grasp Manager (`libezgripper/grasp_manager.py`)

**State Machine**:
- **IDLE**: Gripper at rest, minimal force
- **MOVING**: Actively moving to target position
- **CONTACT**: Detected obstacle/object
- **GRASPING**: Holding object with grasping force

**Force Settings** (from config):
- `moving_force_pct`: Force during movement (default: 17%)
- `grasping_force_pct`: Force when holding object (default: 10%)
- `idle_force_pct`: Force at rest (default: 10%)

**Contact Detection**:
- Position stagnation over consecutive samples
- Configurable via `consecutive_samples_required` and `stall_tolerance_pct`

### 3. Configuration (`config_default.json`)

**Key parameters**:
```json
{
  "servo": {
    "force_management": {
      "moving_force_pct": 17,
      "grasping_force_pct": 10,
      "idle_force_pct": 10
    },
    "collision_detection": {
      "consecutive_samples_required": 5,
      "stall_tolerance_pct": 2.0
    },
    "dynamixel_settings": {
      "current_limit": 1600,
      "operating_mode": 5
    }
  },
  "gripper": {
    "grip_max": 2500,
    "grip_value_multiplier": 4
  }
}
```

---

## Power Consumption Characteristics

**From thermal calibration** (`THERMAL_POWER_CALIBRATION_RESULTS.md`):

| Force | Relative Power | Heating Rate |
|-------|----------------|--------------|
| 15%   | 1.00x          | 0.015°C/s    |
| 30%   | 2.19x          | 0.033°C/s    |
| 45%   | 4.34x          | 0.065°C/s    |

**Key finding**: Power scales **non-linearly** with force (~Force^1.5)

**Thermal limits**:
- Operating range: -5°C to 80°C
- Recommended backoff: 70°C
- Typical operating temp: 40-60°C


---

## Available DDS Libraries

### CycloneDDS Python Bindings

**Installation**: `pip install cyclonedds`

**Capabilities**:
- Pub/sub messaging
- Domain participant management
- Type-safe dataclasses
- Quality of Service (QoS) configuration

### Example Usage: Publishing Commands

```python
from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.pub import DataWriter
from dataclasses import dataclass

@dataclass
class MotorCommand:
    position: float
    effort: float
    velocity: float

# Create participant and topic
participant = DomainParticipant()
topic = Topic(participant, 'rt/ezgripper_motor_commands', MotorCommand)
writer = DataWriter(participant, topic)

# Send command
cmd = MotorCommand(position=50.0, effort=30.0, velocity=0.0)
writer.write(cmd)
```

### Example Usage: Subscribing to State

```python
from cyclonedds.sub import DataReader
from cyclonedds.util import duration

@dataclass
class MotorState:
    position: float
    temperature: int
    grasp_state: str
    # ... other fields

topic = Topic(participant, 'rt/ezgripper_motor_states', MotorState)
reader = DataReader(participant, topic)

# Read latest state
samples = reader.take(N=1)
if samples:
    state = samples[0]
    print(f"Position: {state.position}%, Temp: {state.temperature}°C")
```


---

## System Behavior Characteristics

### State Transitions
- IDLE → MOVING: When position command differs from current position
- MOVING → CONTACT: When position stagnates (5 consecutive samples within 2%)
- CONTACT → GRASPING: Automatically after contact detection
- GRASPING → IDLE: When opening (positive direction change)

### Response Characteristics
- State update rate: 200 Hz
- Control loop rate: 30 Hz
- Typical movement time (0-100%): ~2-3 seconds at default force
- Contact detection latency: ~150ms (5 samples at 30Hz)

### Thermal Behavior
- Heating rate at 15% force: 0.015°C/s
- Heating rate at 30% force: 0.033°C/s
- Heating rate at 45% force: 0.065°C/s
- Passive cooling rate: ~0.02°C/s (varies with ambient)
- Recommended thermal backoff: 70°C

---

## Important Notes

### Error Codes (Hardware Error Status Register)

| Code | Meaning | Action |
|------|---------|--------|
| 0    | No error | Normal operation |
| 1    | Input voltage error | Check power supply |
| 4    | Overheating | Cool down, reduce force |
| 8    | Motor encoder error | Recalibrate |
| 16   | Electrical shock | Check wiring |
| 32   | Overload | Reduce force/load |
| 128  | General hardware error | Power cycle |

### Position Mapping

- **User space**: 0% (closed) to 100% (open)
- **Internal**: -50 (fully closed) to grip_max (2500 default)
- **Calibration offset**: Stored per serial number in device config

### Current Measurement Limitation

In Mode 5 (Extended Position Control), the **Present Current register is unreliable**. The driver uses **Goal Current** for control, which is calculated from the effort percentage.

---

## File References

**Key files to review**:
- `ezgripper_dds_driver.py` - Main DDS driver
- `libezgripper/grasp_manager.py` - State machine logic
- `config_default.json` - Configuration parameters
- `SMART_GRASP_ALGORITHM.md` - Algorithm documentation
- `THERMAL_POWER_CALIBRATION_RESULTS.md` - Power characteristics
- `README.md` - General documentation

**Example test scripts**:
- `simple_power_calibration.py` - Thermal testing with error logging
- `contact_characterization.py` - Contact phase analysis
- `force_optimization_tool.py` - Interactive force tuning

---

## Reference Resources

**Key implementation files**:
- `ezgripper_dds_driver.py` - DDS publisher/subscriber implementation (lines 500-700)
- `libezgripper/ezgripper_base_clean.py` - Hardware interface and sensor reading
- `libezgripper/grasp_manager.py` - State machine implementation
- `config_default.json` - All configurable parameters

**Example test scripts** (demonstrate DDS usage):
- `simple_power_calibration.py` - Thermal testing with error logging
- `contact_characterization.py` - Contact phase analysis
- `force_optimization_tool.py` - Interactive force tuning

**Documentation**:
- `SMART_GRASP_ALGORITHM.md` - State machine behavior details
- `THERMAL_POWER_CALIBRATION_RESULTS.md` - Power consumption data
- `README.md` - System overview and setup

**External documentation**:
- CycloneDDS Python: https://cyclonedds.io/docs/cyclonedds-python/latest/
- Dynamixel MX-64: http://emanual.robotis.com/docs/en/dxl/mx/mx-64-2/

---

**Last Updated**: February 12, 2026
