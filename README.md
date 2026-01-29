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

# 3. Start left gripper driver (auto-calibrates at startup)
python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0

# Driver will automatically:
# - Detect serial number
# - Calibrate using position control (100% effort)
# - Start control thread (30 Hz) and state thread (200 Hz)

# 4. Start right gripper driver
python3 ezgripper_dds_driver.py --side right --dev /dev/ttyUSB1

# 5. Both drivers now running with:
# - Automatic calibration at startup
# - 200 Hz state publishing (predictive model)
# - 30 Hz command execution
# - 3 Hz actual position reads
```

**That's it!** The driver auto-discovers devices, guides you through verification, and stores calibration automatically.

## Features

- ✅ **Multi-Threaded Architecture** - Separate control (30 Hz) and state (200 Hz) threads for optimal performance
- ✅ **200 Hz State Publishing** - Achieves 195 Hz actual rate (97.5% of target) using predictive position model
- ✅ **Predictive Position Model** - Smooth position feedback at 200 Hz between actual hardware reads (3 Hz)
- ✅ **Position Control Only** - Calibration and operation use 100% effort position control (no torque mode)
- ✅ **Automatic Calibration** - Calibrates at startup using position control for consistent force definition
- ✅ **DDS Interface** - Compatible with Unitree Dex1-1 gripper DDS topics (`HGHandCmd_`, `HGHandState_`)
- ✅ **Thread-Safe** - Lock-protected shared state with minimal contention
- ✅ **Load-Resistant** - State publishing isolated from serial I/O blocking
- ✅ **XR Compatible** - Matches Unitree XR teleoperate expectations (200 Hz bidirectional)
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

- **Left Command**: `rt/dex1/left/cmd` (HGHandCmd_)
- **Left State**: `rt/dex1/left/state` (HGHandState_)
- **Right Command**: `rt/dex1/right/cmd` (HGHandCmd_)
- **Right State**: `rt/dex1/right/state` (HGHandState_)

**Message Types:**
- Uses official Unitree Dex1-1 gripper message types from `unitree_sdk2py`
- Command rate: 200 Hz (from XR teleoperate)
- State publishing rate: 200 Hz (195 Hz actual with predictive model)
- Actual position reads: 3 Hz (synced with predicted position)

## Position Mapping

- `q = 0.0 rad` → 0% (closed)
- `q = π rad` → 50% (neutral)
- `q = 2π rad` → 100% (open)

## Architecture

### Multi-Threaded Design

```
XR Teleoperate (200 Hz) → DDS Topics → EZGripper DDS Driver → libezgripper → Hardware
                                              ↓
                                    ┌─────────┴─────────┐
                                    │                   │
                            Control Thread      State Thread
                              (30 Hz)            (200 Hz)
                                    │                   │
                        ┌───────────┴──────┐   ┌────────┴────────┐
                        │                  │   │                 │
                   Commands          Actual   Predictive    Publish
                   Execute          Position  Position      State
                   (Serial)         Read      Model         (DDS)
                                   (3 Hz)
```

**Control Thread (30 Hz):**
- Receives DDS commands
- Executes position commands via serial (100% effort)
- Reads actual position every 10 cycles (3 Hz)
- Syncs predicted position with actual measurements

**State Thread (200 Hz):**
- Runs predictive position estimator
- Updates predicted position using movement model (952.43 %/sec)
- Publishes state to DDS at 200 Hz
- Independent of serial I/O blocking
- Uses absolute time scheduling for precise timing

**Predictive Model:**
- Interpolates position between actual reads
- Constraints: never overshoot, never reverse direction
- Achieves 195 Hz actual publishing rate (97.5% of target)
- Thread-safe with lock-protected shared state

## Testing

### Test Files

**`test_3phase_pattern.py`** - 3-phase gripper test pattern using unified DDS interface:
```bash
python3 test_3phase_pattern.py --side left --rate 200
```
Tests gripper through three phases:
- Phase 0: Calibration (close to 0%)
- Phase 1: Smooth sine wave oscillation (0% → 100% → 0%)
- Phase 2: Random jumps every second
- Phase 3: Instant point-to-point jumps

**`test_movement_timing.py`** - Calibrate gripper movement speed:
```bash
python3 test_movement_timing.py --side left --cycles 3
```
Measures actual gripper movement speed by testing multiple ranges (20-80%, etc.) and calculates parameters for predictive model.

**`test_overhead_characterization.py`** - Characterize system overhead:
```bash
python3 test_overhead_characterization.py --side left --trials 3
```
Separates fixed overhead (DDS latency, command processing) from actual gripper movement speed by testing multiple distance ranges.

**`dex1_hand_interface.py`** - Unified DDS interface abstraction:
- Clean Python API for controlling Dex1-1 grippers
- Methods: `set_position()`, `open()`, `close()`, `get_state()`
- Handles all DDS message creation and topic management
- Used by all test scripts for consistent interface

**`test_gripper.py`** - Legacy automated testing for both grippers:

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
