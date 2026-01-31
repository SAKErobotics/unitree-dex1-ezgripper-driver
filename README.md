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
# - 30 Hz command execution with bulk operations
# - 30 Hz bulk sensor reads (position, current, load, temperature, errors)
```

**That's it!** The driver auto-discovers devices, guides you through verification, and stores calibration automatically.

## Features

- ✅ **Multi-Threaded Architecture** - Separate control (30 Hz) and state (200 Hz) threads for optimal performance
- ✅ **200 Hz State Publishing** - Achieves 195 Hz actual rate (97.5% of target) using predictive position model
- ✅ **Predictive Position Model** - Smooth position feedback at 200 Hz between actual hardware reads (30 Hz)
- ✅ **Protocol 2.0 Bulk Operations** - Atomic sensor reads and writes for improved performance and efficiency
- ✅ **Advanced Monitoring** - Contact detection, error monitoring, and thermal analysis using bulk sensor data
- ✅ **30 Hz Bulk Sensor Reads** - Full state capture (position, current, load, temperature, errors) every control cycle
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
- Bulk sensor reads: 30 Hz (position, current, load, temperature, errors)

## Position Mapping

- `q = 0.0 rad` → 0% (closed)
- `q = 2.7 rad` → 50% (neutral)
- `q = 5.4 rad` → 100% (open)

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
                   Commands          Bulk     Predictive    Publish
                   Execute          Sensor    Position      State
                   (Serial)         Reads     Model         (DDS)
                                   (30 Hz)
```

**Control Thread (30 Hz):**
- Receives DDS commands
- Executes position commands via bulk write (100% effort)
- Reads bulk sensor data every cycle (30 Hz): position, current, load, temperature, errors
- Updates monitoring modules (contact detection, error monitoring, thermal monitoring)
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

### Basic Verification

After installation, verify the gripper is working correctly:

```bash
# Start left gripper driver
python3 ezgripper_dds_driver.py --side left

# In another terminal, monitor the output
# The driver should show:
# - Hardware connection successful
# - Calibration completed
# - State publishing at 200 Hz
# - Bulk sensor reads at 30 Hz
```

### Performance Monitoring

The driver includes built-in performance monitoring that logs every 5 seconds:
- State publishing rate (target: 200 Hz)
- Command execution rate (target: 30 Hz)
- Position tracking accuracy
- CPU usage

### Monitoring Features

The driver automatically monitors:
- **Contact Detection** - Detects when gripper contacts objects
- **Error Monitoring** - Tracks hardware errors and system warnings  
- **Thermal Monitoring** - Monitors temperature trends and predicts overheating

All monitoring data is captured using bulk operations at 30 Hz with minimal performance impact.

## Configuration

See [CONFIGURATION.md](./CONFIGURATION.md) for detailed configuration options including:
- Servo parameters and limits
- Communication settings
- Monitoring thresholds
- Calibration parameters

## Troubleshooting

See [BUG_REPORT.md](./BUG_REPORT.md) for common issues and troubleshooting steps.

## License

This project is part of the SAKErobotics EZGripper ecosystem for Unitree robots.
