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

### Calibration

Run calibration once to establish zero position:

```bash
python3 run_hardware_calibration.py
```

Calibration is stored in `/tmp/ezgripper_left_calibration.txt` and loaded automatically on driver startup.

### Start the Driver

#### USB Interface

For the left gripper (assuming USB device `/dev/ttyUSB0`):

```bash
python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0 --baudrate 57600
```

For the right gripper (assuming USB device `/dev/ttyUSB1`):

```bash
python3 ezgripper_dds_driver.py --side right --dev /dev/ttyUSB1 --baudrate 57600
```

For more reliable device identification using hardware-specific URLs:

```bash
python3 ezgripper_dds_driver.py --side left --dev hwgrep://0403:6001 --baudrate 57600
```

#### Ethernet Adapter Interface

For the left gripper (assuming adapter IP 192.168.123.10):

```bash
python3 ezgripper_dds_driver.py --side left --dev socket://192.168.123.10:4000
```

For the right gripper (assuming adapter IP 192.168.123.11):

```bash
python3 ezgripper_dds_driver.py --side right --dev socket://192.168.123.11:4000
```

Replace the IP addresses with your actual Elfin-EE11A adapter IP addresses configured in the Hardware Setup section.

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
