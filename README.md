# Unitree Dex1 EZGripper Driver

A drop-in replacement driver that allows SAKE Robotics EZGripper to be connected to Unitree G1 robot and controlled through the standard Dex1 DDS interface.

## Overview

This driver enables seamless integration of EZGripper with Unitree G1 robots by providing full compatibility with the Dex1 DDS API. The EZGripper appears as a standard Dex1 gripper to all G1 control systems including XR teleoperate.

**Key Features:**
- ✅ **Drop-in Dex1 replacement** - Uses identical DDS topics and message types
- ✅ **Motor driver level compatibility** - Only uses `q` (position) and `tau` (torque) fields
- ✅ **Optimized grasping** - Uses EZGripper's close mode for improved grip strength
- ✅ **Position + force control** - Automatic object detection and force limiting
- ✅ **XR teleoperate ready** - Full compatibility with Unitree XR teleoperate system
- ✅ **Minimal complexity** - Direct DDS to libezgripper interface

## Architecture

```
Unitree XR Teleop → Dex1 DDS → Unitree Dex1 Driver → EZGripper DDS → EZGripper Interface → Hardware
                    ← Dex1 DDS ←                    ← EZGripper DDS ←                    ←
```

**DDS-to-DDS Translation Layer:**
- **Hardware abstraction boundary** at DDS level
- **Future-proof** for Dynamixel API 2.0 migration
- **Language-agnostic** development (all languages use same DDS interface)

**DDS Topics (Dex1 Compatible):**
- `rt/dex1/left/cmd` - Command topic for left gripper
- `rt/dex1/left/state` - State topic for left gripper  
- `rt/dex1/right/cmd` - Command topic for right gripper
- `rt/dex1/right/state` - State topic for right gripper

**Message Types:**
- `MotorCmds_` - Dex1 compatible command messages
- `MotorStates_` - Dex1 compatible state messages

## Quick Start

### 1. Hardware Setup

1. **Connect EZGripper(s)** to USB ports using RS485 adapters
2. **Power on the grippers** 
3. **Note the serial port names** (usually `/dev/ttyUSB0`, `/dev/ttyUSB1`)

### 2. Installation

```bash
# Install dependencies
pip install cyclonedds pyserial libezgripper

# Clone this repository
git clone <repository-url>
cd unitree-dex1-ezgripper-driver
```

### 3. Start EZGripper DDS Interface

First, start the ezgripper-dds-driver for hardware communication:

```bash
# Left gripper hardware interface
python3 ezgripper_dds_driver.py --name ezgripper_left --dev /dev/ttyUSB0 --ids 1

# Right gripper hardware interface  
python3 ezgripper_dds_driver.py --name ezgripper_right --dev /dev/ttyUSB1 --ids 2
```

### 4. Start Dex1 Translation Layer

Then start the Dex1 translation drivers:

```bash
# Left gripper Dex1 interface
python3 unitree_dex1_ezgripper_driver.py --side left --gripper-name ezgripper_left

# Right gripper Dex1 interface (in another terminal)
python3 unitree_dex1_ezgripper_driver.py --side right --gripper-name ezgripper_right
```

### 5. Integration with Unitree XR Teleoperate

Now you can use EZGripper with the standard Unitree XR teleoperate system:

```bash
# Start XR teleoperation with Dex1 grippers (EZGripper will work transparently)
python3 teleop_hand_and_arm.py --ee dex1 --input-mode hand

# Or with controller input
python3 teleop_hand_and_arm.py --ee dex1 --input-mode controller
```

## Control Interface

### Motor Driver Level Compatibility

The driver uses only two fields from the Dex1 motor command:

- **`q` (position)**: 0 to 2π radians (0 = closed, 2π = open)
- **`tau` (torque)**: Force/effort value (scaled to EZGripper effort percentage)

### Optimized Grasping Logic

```python
if q <= 0.1:        # Close command (≈ 0 radians)
    gripper.close(effort_pct)     # Use EZGripper's optimized close mode
elif q >= 6.0:      # Open command (≈ 2π radians)  
    gripper.open(effort_pct)      # Use open mode
else:               # Position command
    gripper.goto_position(position_pct, effort_pct)  # Position + force control
```

### Force Control

The operator controls force through hand gesture intensity:
- **Light hand closure** → Low `tau` → Gentle grip (paper cup)
- **Firm hand closure** → High `tau` → Strong grip (solid objects)

The EZGripper uses **position control with force limiting**:
1. Move toward target position
2. Stop when force limit (`tau`) is exceeded (object contact)
3. Maintain grip at force limit

## Configuration Options

```bash
python3 unitree_dex1_ezgripper_driver.py --help
```

**Parameters:**
- `--side`: Gripper side (left/right)
- `--gripper-name`: EZGripper name (matches ezgripper-dds-driver config)
- `--domain`: DDS domain ID (default: 0)
- `--log-level`: Logging verbosity

## Network Configuration

For network-connected grippers, configure the ezgripper-dds-driver with network devices:

```bash
# EZGripper hardware interfaces via network
python3 ezgripper_dds_driver.py --name ezgripper_left --dev socket://192.168.1.100:4000 --ids 1
python3 ezgripper_dds_driver.py --name ezgripper_right --dev socket://192.168.1.101:4000 --ids 2

# Dex1 translation layer (same as before)
python3 unitree_dex1_ezgripper_driver.py --side left --gripper-name ezgripper_left
python3 unitree_dex1_ezgripper_driver.py --side right --gripper-name ezgripper_right
```

## Advantages of DDS-to-DDS Architecture

This driver uses a DDS-to-DDS translation approach:

**Architecture:**
```
XR Teleop → Dex1 DDS → Translation Layer → EZGripper DDS → Hardware Interface → libezgripper → Hardware
```

**Benefits:**
- **Hardware abstraction** - DDS boundary enables future hardware changes
- **Language-agnostic** - All languages use same DDS interface
- **Future-proof** - Easy migration to Dynamixel API 2.0
- **Modular design** - Independent hardware and translation layers
- **Single point of change** - Update EZGripper interface affects all consumers

## Troubleshooting

**Gripper not detected:**
- Check serial connection and power
- Verify serial port permissions: `sudo usermod -a -G dialout $USER`

**DDS communication issues:**
- Check DDS domain ID matches G1 system
- Verify network interface configuration

**Calibration failures:**
- Ensure gripper is manually closed tightly during calibration
- Check motor ID assignment

## Integration with G1 Systems

The driver works with all Unitree G1 configurations:

```bash
# G1 with 29-DOF arms
python3 teleop_hand_and_arm.py --arm G1_29 --ee dex1

# G1 with 23-DOF arms  
python3 teleop_hand_and_arm.py --arm G1_23 --ee dex1
```

## License

BSD-3-Clause License

## Acknowledgments

- Unitree Robotics for Dex1 DDS API specification
- SAKE Robotics for EZGripper hardware and libezgripper
- Cyclone DDS project for reliable DDS implementation
