# EZGripper DDS Driver for Unitree G1

CycloneDDS driver for EZGripper control on Unitree G1 robots.

⚠️ **IMPORTANT:** MX series servos do NOT have real current sensing. See [MX_CURRENT_SENSING_LIMITATIONS.md](MX_CURRENT_SENSING_LIMITATIONS.md) for critical safety information.

## Quick Start

```bash
# Install
git clone https://github.com/SAKErobotics/unitree-dex1-ezgripper-driver.git
cd unitree-dex1-ezgripper-driver
pip install -r requirements.txt

# Run left gripper
python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0
```

## DDS Interfaces

This driver provides **3 distinct DDS interfaces**:

### 1. Agnostic Direct Control ⭐ (Recommended for Custom Robots)

**Best for:** Custom robots, vision systems, non-Unitree platforms

**Topics:**
- Command: `rt/gripper/{side}/cmd_direct`
- State: `rt/gripper/{side}/state_direct`

**Command Format:**
```json
{
  "position_pct": 0.0,      // 0.0 (closed) to 100.0 (open)
  "force_limit_pct": 25     // 0 to 100% dynamic force
}
```

**Key Feature:** Adjust force on every cycle (soft for eggs, firm for heavy objects)

### 2. Dex1 Humanoid Interface (Unitree G1 Only)

**Best for:** Unitree G1 robots with XR teleoperate

**Topics:**
- Command: `rt/dex1/{side}/cmd`
- State: `rt/dex1/{side}/state`

**Command Format:**
- Position: 0.0 to 5.4 radians
- Force: Fixed from configuration files

**Key Feature:** Compatible with Unitree XR teleoperate framework

### 3. Telemetry Interface (Monitoring)

**Best for:** Monitoring, diagnostics, contact detection

**Topics:**
- State: `rt/gripper/{side}/telemetry` (read-only)

**State Format:**
```json
{
  "hardware": {
    "temperature_c": 42.5,
    "error_code": 0
  },
  "contact": false,
  "pos": "50.0%",
  "state": "moving"
}
```

**Key Feature:** Real-time hardware health and contact detection

## Which Interface Should I Use?

### Use Agnostic Direct Control If:
- You're building a custom robot
- You need dynamic force control
- You're not using Unitree G1
- You want vision-based force adaptation

### Use Dex1 Humanoid Interface If:
- You're using Unitree G1 robot
- You need XR teleoperate compatibility
- You're okay with fixed force settings

### Use Telemetry Interface If:
- You need hardware health monitoring
- You want to detect contact events
- You're tracking grasp states

## Configuration

```bash
python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0 --domain 0
```

- `--side`: Gripper identifier (left, center, right)
- `--dev`: Serial port device
- `--domain`: DDS domain ID (default: 0)

## Troubleshooting

### Permission Denied

```bash
sudo adduser $USER dialout
# Then reboot
```

### Interface Not Found

- Verify domain ID matches
- Check participant is running
- Ensure topic names are correct

## Advanced Documentation

- [Detailed Interface Guide](DDS_INTERFACES.md) - Complete interface documentation
- [Configuration Guide](CONFIGURATION.md) - Advanced configuration options

## License

BSD License - See LICENSE file

## Support

- **GitHub Issues**: https://github.com/SAKErobotics/unitree-dex1-ezgripper-driver/issues
- **SAKE Robotics**: https://sakerobotics.com/
