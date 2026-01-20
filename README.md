# EZGripper DDS Driver for Unitree G1

CycloneDDS driver for EZGripper control on Unitree G1 robots using the Dex1 DDS interface.

## Features

- ✅ **DDS Interface** - Compatible with Unitree Dex1 DDS topics
- ✅ **Calibration Persistence** - Software-based calibration storage
- ✅ **Position Control** - Accurate 0-100% gripper positioning
- ✅ **XR Teleoperate Compatible** - Fixed 50% effort for preliminary compatibility

## Installation on Unitree G1

Clone the repository on the G1:

```bash
git clone https://github.com/SAKErobotics/unitree-dex1-ezgripper-driver.git
cd unitree-dex1-ezgripper-driver
pip install -r requirements.txt
```

## Hardware Setup

1. Connect EZGripper to ethernet adapter
2. Configure adapter as TCP server on port 4000, baud 57600
3. Connect adapter to G1 internal network (192.168.123.x)
4. Note the adapter's IP address

## Usage

### Calibration

Run calibration once to establish zero position:

```bash
python3 run_hardware_calibration.py
```

Calibration is stored in `/tmp/ezgripper_left_calibration.txt` and loaded automatically on driver startup.

### Start the Driver

```bash
python3 ezgripper_dds_driver.py --side left --dev socket://192.168.123.X:4000
```

Replace `192.168.123.X` with your ethernet adapter's IP address on the G1 network.

For the right gripper:

```bash
python3 ezgripper_dds_driver.py --side right --dev socket://192.168.123.X:4000
```

## DDS Topics

- **Left Command**: `rt/dex1/left/cmd` (MotorCmds_)
- **Left State**: `rt/dex1/left/state` (MotorStates_)
- **Right Command**: `rt/dex1/right/cmd` (MotorCmds_)
- **Right State**: `rt/dex1/right/state` (MotorStates_)

## Position Mapping

- `q = 0.0 rad` → 0% (closed)
- `q = π rad` → 50% (neutral)
- `q = 2π rad` → 100% (open)

## Architecture

```
XR Teleoperate → Dex1 DDS Topics → EZGripper DDS Driver → libezgripper → Hardware
```

## License

BSD-3-Clause
