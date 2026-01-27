# EZGripper DDS Driver for Unitree G1

CycloneDDS driver for EZGripper control on Unitree G1 robots using the Dex1 DDS interface.

## Quick Start

Get up and running in 5 minutes:

```bash
# 1. Clone and install
git clone https://github.com/SAKErobotics/unitree-dex1-ezgripper-driver.git
cd unitree-dex1-ezgripper-driver
pip install -r requirements.txt

# 2. Connect grippers to USB ports
# (physically connect EZGrippers to G1 USB ports)

# 3. Start left gripper driver (auto-discovers on first run)
python3 ezgripper_dds_driver.py --side left

# Follow prompts to verify left/right mapping

# 4. Calibrate left gripper
python3 ezgripper_dds_driver.py --side left --calibrate

# 5. Start right gripper driver
python3 ezgripper_dds_driver.py --side right

# 6. Calibrate right gripper
python3 ezgripper_dds_driver.py --side right --calibrate

# 7. Start both drivers for normal operation
# Terminal 1:
python3 ezgripper_dds_driver.py --side left

# Terminal 2:
python3 ezgripper_dds_driver.py --side right
```

**That's it!** The driver auto-discovers devices, guides you through verification, and stores calibration automatically.

## Features

- ✅ **DDS Interface** - Compatible with Unitree Dex1 DDS topics
- Integrated with Unitree https://github.com/unitreerobotics/xr_teleoperate
- Unitree G1 integration kit includes; mount, cabling and software for EZGripper integration

## Installation on Unitree G1

Clone the repository on the G1:

```bash
git clone https://github.com/SAKErobotics/unitree-dex1-ezgripper-driver.git
cd unitree-dex1-ezgripper-driver
pip install -r requirements.txt
```

## Hardware Setup

### Connection Options

The EZGrippers can be connected to the G1 using either:
- **USB Interface** - Direct USB connection (simpler, no additional hardware)
- **Ethernet Adapter** - Elfin-EE11A serial-to-ethernet adapters (network-based, supports remote grippers)

### USB Interface Configuration (Recommended)

For direct USB connection, connect the EZGripper directly to the G1's USB port. This is the simplest setup and requires no additional hardware configuration.

**USB Device Setup:**
1. Connect EZGripper to G1 USB port
2. Identify the USB device (usually `/dev/ttyUSB0`, `/dev/ttyUSB1`, etc.):
   ```bash
   ls /dev/ttyUSB*
   ```
3. Verify user permissions (add to dialout group if needed):
   ```bash
   sudo usermod -a -G dialout $USER
   ```
   Then reboot for changes to take effect.

**Note:** If you have multiple USB devices, device names may change. For more reliable identification, you can use hardware-specific URLs:
- By vendor:device ID: `hwgrep://0403:6001`
- By serial number: `hwgrep://A4012B2G`

To find your device properties:
```bash
python3 -c "import serial.tools.list_ports; print(serial.tools.list_ports.comports())"
```

### Elfin-EE11A Ethernet Adapter Configuration

The EZGrippers can also connect to the G1 via Elfin-EE11A serial-to-ethernet adapters.

**Default Credentials:**
- Username: `admin`
- Password: `admin`

**Configuration for Left Gripper:**
1. Connect EZGripper to Elfin-EE11A adapter
2. Access adapter web interface (default IP: 192.168.1.200)
3. Login with admin/admin
4. Configure the following settings:
   - **Mode**: TCP Server
   - **Port**: 4000
   - **Baud Rate**: 57600
   - **Data Bits**: 8
   - **Stop Bits**: 1
   - **Parity**: None
   - **IP Address**: Set to available address on G1 network (e.g., 192.168.123.10)
   - **Subnet Mask**: 255.255.255.0
   - **Gateway**: 192.168.123.1
5. Save settings and reboot adapter
6. Connect adapter to G1 internal network (192.168.123.x)

**Configuration for Right Gripper:**
1. Repeat above steps with different IP address (e.g., 192.168.123.11)
2. Use same port (4000) and serial settings

**Note:** Ensure each adapter has a unique IP address on the G1 network.

## Usage

### First Run - Auto-Discovery and Verification

On first run, the driver will automatically discover connected EZGripper devices and guide you through verifying the left/right mapping:

```bash
# Start left gripper driver
python3 ezgripper_dds_driver.py --side left

# Start right gripper driver  
python3 ezgripper_dds_driver.py --side right
```

**First Run Process:**
1. Driver auto-discovers EZGripper USB devices
2. Displays discovered devices with serial numbers
3. Prompts you to verify left/right mapping
4. Saves device configuration to `/tmp/ezgripper_device_config.json`

**Interactive Verification Example:**
```
============================================================
EZGripper Device Mapping Verification
============================================================

Discovered devices:
  Left:  /dev/ttyUSB0 (serial: A4012B2G)
  Right: /dev/ttyUSB1 (serial: B5023C3D)

Please verify this mapping is correct.
The 'left' gripper should be on the LEFT side of the robot.
The 'right' gripper should be on the RIGHT side of the robot.

Is this mapping correct? [Y/n]
```

- **Y/Enter**: Mapping confirmed, configuration saved
- **N**: Mapping swapped, configuration saved

**Device Config Structure:**
```json
{
  "left": "/dev/ttyUSB0",
  "right": "/dev/ttyUSB1",
  "left_serial": "A4012B2G",
  "right_serial": "B5023C3D",
  "calibration": {
    "A4012B2G": 12.5,
    "B5023C3D": -8.3
  }
}
```

**Subsequent Runs:**
- Device config loaded automatically
- No verification needed
- Calibration loaded from config

### Calibration

Calibration is now tied to gripper serial numbers and stored in the device config file. Each gripper must be calibrated separately:

**Calibrate Left Gripper:**
```bash
python3 ezgripper_dds_driver.py --side left --calibrate
```

**Calibrate Right Gripper:**
```bash
python3 ezgripper_dds_driver.py --side right --calibrate
```

**Calibration Process:**
1. Driver moves gripper to relaxed position (50%)
2. Performs calibration sequence
3. Saves offset to device config by serial number
4. Calibration persists across reboots

**Note:** Calibration stays with the physical gripper (serial number), not the left/right designation. If you swap the left/right mapping, calibration automatically stays with the correct gripper.

### Start the Driver

After first run and calibration, start both gripper drivers:

```bash
# Terminal 1 - Left gripper
python3 ezgripper_dds_driver.py --side left

# Terminal 2 - Right gripper
python3 ezgripper_dds_driver.py --side right
```

**Manual Device Specification (Optional):**
If you prefer to specify devices manually:

```bash
python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0
python3 ezgripper_dds_driver.py --side right --dev /dev/ttyUSB1
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

## Testing

The `test_gripper.py` script provides automated testing for both grippers. This is useful for:

- Verifying correct left/right mapping
- Testing calibration and basic movements
- Debugging gripper issues

### Usage

```bash
python3 test_gripper.py --right-dev /dev/ttyUSB0 --left-dev /dev/ttyUSB1
```

### Test Sequence

For each gripper (right first, then left):
1. Calibrate
2. Open to 100% - wait 2 seconds
3. Close to 0% - wait 2 seconds
4. Repeat 3 times
5. Move to 50% - stop

### Verifying Mapping

The script tests the right gripper first, then the left gripper. Watch which physical gripper moves during each test:

- If the right side of the robot moves during the "RIGHT Gripper" test, mapping is correct
- If the left side of the robot moves during the "RIGHT Gripper" test, swap the device paths

### Example Output

```
============================================================
Testing RIGHT Gripper
============================================================
Device: /dev/ttyUSB0
...
============================================================
Testing LEFT Gripper
============================================================
Device: /dev/ttyUSB1
...

============================================================
Test Summary
============================================================
Right gripper: ✅ PASS
Left gripper: ✅ PASS

Verify the grippers moved correctly:
- Right gripper should be on the RIGHT side of the robot
- Left gripper should be on the LEFT side of the robot

If mapping is incorrect, swap the device paths and re-run
```

### Custom Iterations

To change the number of open/close cycles:

```bash
python3 test_gripper.py --right-dev /dev/ttyUSB0 --left-dev /dev/ttyUSB1 --iterations 5
```

## DDS Message Structure Reference

### Official Unitree G1 Dex1 Hand Format

This driver uses the official Unitree G1 Dex1 hand DDS message format as defined in the Unitree SDK.

**Source Repository:** [unitreerobotics/dex1_1_service](https://github.com/unitreerobotics/dex1_1_service)

**Official Documentation:** [Unitree G1 Developer Documentation](https://support.unitree.com/home/en/G1_developer/basic_services_interface)

### DDS Topics

```
Left Gripper:
  Command Topic:  rt/dex1/left/cmd
  State Topic:    rt/dex1/left/state
  Motor ID:       1

Right Gripper:
  Command Topic:  rt/dex1/right/cmd
  State Topic:    rt/dex1/right/state
  Motor ID:       2
```

### HandCmd_ Message Structure

**Message Type:** `unitree_hg.msg.dds_.HandCmd_`

**Python Definition:**
```python
from unitree_sdk2py.idl.default import HGHandCmd_, HGMotorCmd_

@dataclass
class HandCmd_:
    motor_cmd: sequence[MotorCmd_]  # Sequence of motor commands
    reserve: array[uint32, 4]       # Reserved fields [0, 0, 0, 0]
```

**MotorCmd_ Fields:**
```python
@dataclass
class MotorCmd_:
    mode: uint8        # Control mode (0 = position control)
    q: float32         # Position in radians (0.0 = closed, 6.28 = open)
    dq: float32        # Velocity (0.0 for position control)
    tau: float32       # Torque (0.0, hardware handles effort)
    kp: float32        # Position gain (0.0, hardware handles control)
    kd: float32        # Damping gain (0.0, hardware handles control)
    reserve: uint32    # Reserved field (0)
```

**Example Command:**
```python
# Create motor command for left gripper (Motor ID 1)
motor_cmd = HGMotorCmd_(
    mode=0,      # Position control
    q=3.14,      # 50% open (π radians)
    dq=0.0,
    tau=0.0,
    kp=0.0,
    kd=0.0,
    reserve=0
)

# Create hand command with single motor
hand_cmd = HGHandCmd_(
    motor_cmd=[motor_cmd],
    reserve=[0, 0, 0, 0]
)
```

### HandState_ Message Structure

**Message Type:** `unitree_hg.msg.dds_.HandState_`

**Python Definition:**
```python
from unitree_sdk2py.idl.default import HGHandState_, HGMotorState_, HGIMUState_

@dataclass
class HandState_:
    motor_state: sequence[MotorState_]              # Motor state data
    press_sensor_state: sequence[PressSensorState_] # Pressure sensor data
    imu_state: IMUState_                            # IMU data
    power_v: float32                                # Power voltage
    power_a: float32                                # Power current
    system_v: float32                               # System voltage
    device_v: float32                               # Device voltage
    error: array[uint32, 2]                         # Error flags
    reserve: array[uint32, 2]                       # Reserved fields
```

**MotorState_ Fields:**
```python
@dataclass
class MotorState_:
    mode: uint8                  # Current control mode
    q: float32                   # Current position (radians)
    dq: float32                  # Current velocity
    ddq: float32                 # Current acceleration
    tau_est: float32             # Estimated torque
    temperature: array[int16, 2] # Temperature readings
    vol: float32                 # Voltage
    sensor: array[uint32, 2]     # Sensor data
    motorstate: uint32           # Motor state flags
    reserve: array[uint32, 4]    # Reserved fields
```

### Position Mapping

The Dex1 hand uses radians for position:

```
q = 0.0 rad  → 0% (fully closed)
q = 3.14 rad → 50% (neutral)
q = 6.28 rad → 100% (fully open)
```

**Conversion Formula:**
```python
# Dex1 to EZGripper percentage
position_pct = (q_radians / 6.28) * 100.0

# EZGripper percentage to Dex1
q_radians = (position_pct / 100.0) * 6.28
```

### Message Flow

```
G1 XR Teleoperate
    ↓
rt/dex1/left/cmd (HandCmd_)
    ↓
EZGripper DDS Driver
    ↓
Hardware Controller → EZGripper
    ↓
rt/dex1/left/state (HandState_)
    ↓
G1 System
```

### SDK References

**Unitree SDK2 Python:**
- Repository: [unitreerobotics/unitree_sdk2_python](https://github.com/unitreerobotics/unitree_sdk2_python)
- IDL Definitions: `unitree_sdk2py/idl/unitree_hg/msg/dds_/`
- HandCmd_: `_HandCmd_.py`
- HandState_: `_HandState_.py`
- MotorCmd_: `_MotorCmd_.py`
- MotorState_: `_MotorState_.py`

**Dex1 Service:**
- Repository: [unitreerobotics/dex1_1_service](https://github.com/unitreerobotics/dex1_1_service)
- Official Dex1-1 gripper serial-to-DDS service
- Defines topic names and message usage patterns

## License

BSD-3-Clause
