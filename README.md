# Unitree Dex1 EZGripper Driver

A drop-in replacement driver that allows SAKE Robotics EZGripper to be connected to Unitree G1 robot and controlled through the standard Dex1 DDS interface.

## Overview

This driver enables seamless integration of EZGripper with Unitree G1 robots by providing full compatibility with the Dex1 DDS API. The EZGripper appears as a standard Dex1 gripper to all G1 control systems including XR teleoperate.

**Key Features:**
- ✅ **Drop-in Dex1 replacement** - Uses identical DDS topics and message types
- ✅ **Motor driver level compatibility** - Only uses `q` (position) and `tau` (torque) fields
- ✅ **Optimized grasping** - Uses EZGripper's close mode for improved grip strength
- ✅ **Position + force control** - Automatic object detection and force limiting
```bash
git clone https://github.com/SAKErobotics/unitree-dex1-ezgripper-driver.git
cd unitree-dex1-ezgripper-driver
pip install -e .
```

### 2. Connect Hardware
- Connect EZGripper to USB port
- Note the device path (usually `/dev/ttyUSB0`)

### 3. Run Driver

**USB Connection (Development/Testing):**
```bash
# Left gripper
python3 unitree_dex1_ezgripper_driver.py --side left --dev /dev/ttyUSB0

# Right gripper  
python3 unitree_dex1_ezgripper_driver.py --side right --dev /dev/ttyUSB0
```

**TCP Connection (Unitree Robots):**
```bash
# Left gripper (TCP to EZGripper network adapter)
python3 unitree_dex1_ezgripper_driver.py --side left --dev socket://192.168.123.100:4000

# Right gripper
python3 unitree_dex1_ezgripper_driver.py --side right --dev socket://192.168.123.101:4000
```

That's it! Your G1 robot will now control the EZGripper exactly like a Dex1 gripper.

## 📋 Requirements

- **Python 3.8+**
- **Linux** (Ubuntu 20.04+ recommended)
- **Connection Options:**
  - **USB**: USB port for EZGripper connection
  - **TCP**: Network connection for Unitree robots
- **Hardware**: EZGripper with USB or Ethernet-Serial adapter

## 🔧 Hardware Setup

### USB Connection (Development/Testing)
1. **Connect EZGripper** to USB port
2. **Check device**: `ls /dev/ttyUSB*`
3. **Add user to dialout group** (if needed):
   ```bash
   sudo usermod -a -G dialout $USER
   # Logout and login again
   ```

### TCP Connection (Unitree Robots)
1. **Connect EZGripper** to Ethernet-Serial adapter
2. **Configure adapter** with static IP (e.g., 192.168.123.100)
3. **Test connection**:
   ```bash
   # Test TCP connectivity
   telnet 192.168.123.100 4000
   # Should connect to EZGripper serial port
   ```
4. **Network setup** for Unitree robots:
   - EZGripper connects to robot's internal network
   - Use IPs in 192.168.123.x range
   - Port 4000 is standard for EZGripper TCP

## 🎮 Usage

### Basic Control
```bash
# USB connection (development)
python3 unitree_dex1_ezgripper_driver.py --side left

# TCP connection (Unitree robots)
python3 unitree_dex1_ezgripper_driver.py --side left --dev socket://192.168.123.100:4000
```

### With Custom Device
```bash
# USB device
python3 unitree_dex1_ezgripper_driver.py --side left --dev /dev/ttyACM0

# TCP device
python3 unitree_dex1_ezgripper_driver.py --side left --dev socket://192.168.123.100:4000
```

### Debug Mode
```bash
python3 unitree_dex1_ezgripper_driver.py --side left --log-level DEBUG
```

## 🤖 Integration

### How Unitree Controls Motors with DDS

Unitree robots use **CycloneDDS** for all motor communication:

1. **DDS Topics**: Standard topics for motor commands/states
   - Commands: `rt/dex1/left/cmd`, `rt/dex1/right/cmd`
   - States: `rt/dex1/left/state`, `rt/dex1/right/state`

2. **Message Types**: Standard motor command/state structures
   - `MotorCmd_`: Contains `q` (position) and `tau` (torque)
   - `MotorState_`: Contains current motor state

3. **Network Communication**: DDS handles all networking automatically
   - No need to manage TCP connections manually
   - DDS handles discovery, reliability, and data routing

**Our driver uses the same DDS interface**, making the EZGripper appear exactly like a native Dex1 gripper to the system.

### XR Teleoperate
Works automatically with Unitree XR teleoperate. No setup required.

### Custom Control
The driver subscribes to standard Dex1 DDS topics:
- **Commands**: `rt/dex1/left/cmd`, `rt/dex1/right/cmd`
- **States**: `rt/dex1/left/state`, `rt/dex1/right/state`

Send standard Dex1 motor commands - the driver handles the EZGripper control automatically.

## 🔍 Troubleshooting

### Permission Denied
```bash
sudo usermod -a -G dialout $USER
# Then logout and login again
```

### Device Not Found
```bash
# Check available devices
ls /dev/ttyUSB*
ls /dev/ttyACM*

# Try different device path
python3 unitree_dex1_ezgripper_driver.py --side left --dev /dev/ttyACM0
```

### Driver Won't Start
1. Check device connection
2. Verify device path
3. Check user permissions
4. Try debug mode: `--log-level DEBUG`

## 📞 Support

- **Issues**: https://github.com/SAKErobotics/unitree-dex1-ezgripper-driver/issues
- **Documentation**: https://github.com/SAKErobotics/unitree-dex1-ezgripper-driver/wiki
- **Email**: info@sakerobotics.com

## 📄 License

BSD 3-Clause License - see LICENSE file for details.

---

**SAKE Robotics** - Advanced Gripper Solutions for Robotics
