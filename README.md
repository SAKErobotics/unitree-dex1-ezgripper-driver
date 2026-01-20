# EZGripper DDS Driver for Unitree G1

CycloneDDS driver for EZGripper control on Unitree G1 robots using the Dex1 DDS interface.

## Features

- ✅ **DDS Interface** - Compatible with Unitree Dex1 DDS topics
- ✅ **Calibration Persistence** - Software-based calibration storage
- ✅ **Position Control** - Accurate 0-100% gripper positioning
- ✅ **XR Teleoperate Compatible** - Fixed 50% effort for preliminary compatibility
- ✅ **TCP Connection** - Network-based gripper communication

## Installation

```bash
git clone https://github.com/SAKErobotics/unitree-dex1-ezgripper-driver.git
cd unitree-dex1-ezgripper-driver
pip install -r requirements.txt
```

### CycloneDDS Setup

The driver requires CycloneDDS 0.10.2. Set the environment variable:

```bash
export CYCLONEDDS_HOME=/opt/cyclonedds-0.10.2
```

Or the driver will set it automatically in the code.

## Usage

### Start the Driver

```bash
python3 ezgripper_dds_driver.py --side left --dev socket://192.168.0.131:4000
```

### Calibration

Run calibration to establish zero position:

```bash
python3 run_hardware_calibration.py
```

Calibration is stored in `/tmp/ezgripper_left_calibration.txt` and loaded automatically on driver startup.

## DDS Topics

- **Command**: `rt/dex1/left/cmd` (MotorCmds_)
- **State**: `rt/dex1/left/state` (MotorStates_)

## Position Mapping

- `q = 0.0 rad` → 0% (closed)
- `q = π rad` → 50% (neutral)
- `q = 2π rad` → 100% (open)

## Hardware Setup

1. Connect EZGripper to ethernet adapter
2. Configure adapter as TCP server on port 4000, baud 57600
3. Connect to network (local: 192.168.0.x, G1: 192.168.123.x)
4. Run calibration once
5. Start driver

## Architecture

```
XR Teleoperate → Dex1 DDS Topics → EZGripper DDS Driver → libezgripper → Hardware
```

## License

BSD-3-Clause
