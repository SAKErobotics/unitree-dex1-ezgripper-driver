# EZGripper DDS Driver for Unitree G1

CycloneDDS driver for EZGripper control on Unitree G1 robots using the Dex1 DDS interface.

⚠️ **IMPORTANT:** MX series servos do NOT have real current sensing. See [MX_CURRENT_SENSING_LIMITATIONS.md](MX_CURRENT_SENSING_LIMITATIONS.md) for critical safety information.

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
- ✅ **30 Hz Bulk Sensor Reads** - Full state capture (position, estimated current, load, temperature, errors) every control cycle
- ✅ **Current-Based Position Control (Mode 5)** - Uses Dynamixel Mode 5 for active current control under constant spring loads
- ✅ **Automatic Calibration** - Calibrates at startup using current-based position control
- ✅ **DDS Interface** - Compatible with Unitree G1 motor DDS topics (`MotorCmds_`, `MotorStates_`)
- ✅ **Active Grasp Management** - State machine maintains grip until explicitly commanded to release
- ✅ **Configurable Force Settings** - Separate force levels for moving, holding, and grasping
- ✅ **Thread-Safe** - Lock-protected shared state with minimal contention
- ✅ **Load-Resistant** - State publishing isolated from serial I/O blocking
- ✅ **XR Compatible** - Matches Unitree XR teleoperate expectations (200 Hz bidirectional)
- Integrated with Unitree https://github.com/unitreerobotics/xr_teleoperate
- Unitree G1 integration kit includes; mount, cabling and software for EZGripper integration

## 📊 DDS Integration for AI Development

### **Real-Time Telemetry**
The DDS interface provides multi-modal sensor data for AI/ML applications:

```yaml
rt/dex1/left/state:  # MotorStates_ @ 200 Hz
  - q: joint_position_radians      # Proprioceptive feedback
  - tau_est: estimated_torque_Nm   # Force feedback
  - temperature: motor_temp_celsius # Real Dynamixel MX-64AR sensor
  - mode: control_mode_status      # Operational context
```

### **Multi-Modal Learning Support**
- **Visual**: Camera feeds + gripper state correspondence for visual-force learning
- **Force**: 35N max force with 0-100% configurable control for force-aware manipulation
- **Proprioceptive**: 0.1% position accuracy for precise motion planning
- **Thermal**: Real Dynamixel motor temperature for workload and health monitoring

### **Dataset Generation Benefits**
- **Grasp Success Labeling**: Torque patterns correlate with successful grasps
- **Object Property Detection**: Force profiles indicate object hardness/compliance
- **Contact Event Detection**: Torque changes reveal surface contact events
- **Humanoid Dynamics**: Spring compliance provides examples of successful grasps despite body movement

### **For VLM/VLA Development**
- **200 Hz State Publishing**: High-frequency feedback for reactive control
- **Predictive Position Model**: Smooth interpolation between hardware reads
- **Multi-Threaded Architecture**: Isolated control and telemetry streams
- **Protocol 2.0 Bulk Operations**: Efficient sensor data collection

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

Calibration is now tied to gripper serial numbers and stored in the device config file. **The driver auto-calibrates at startup by default.**

**Calibrate Left Gripper:**
```bash
python3 ezgripper_dds_driver.py --side left
# Calibrates automatically at startup
```

**Calibrate Right Gripper:**
```bash
python3 ezgripper_dds_driver.py --side right
# Calibrates automatically at startup
```

**Skip Calibration (use saved calibration):**
```bash
python3 ezgripper_dds_driver.py --side left --no-calibrate
```

**Calibration Process:**
1. Closes gripper with 30% current (336mA) until stable contact detected
2. Monitors current and position for 5 consecutive stable readings
3. Records zero position (contact point)
4. Opens to 50% with 40% current for stable hold
5. Waits 1 second for movement to complete
6. Saves offset to device config by serial number
7. Calibration persists across reboots

**Note:** Uses Mode 5 current-based position control for consistent force application and thermal safety.

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

**Message Types:**
- Uses Unitree G1 motor message types from `unitree_sdk2py`
- Single motor per gripper (motor index 0)
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
- Processes commands through GraspManager state machine
- Executes position commands via bulk write (configurable force)
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

## Temperature Monitoring

The driver provides real-time temperature monitoring of the servo motor. **Unlike current sensing on MX series servos, temperature readings are accurate and reliable.**

### Automatic Temperature Logging

Temperature is logged automatically every 0.1 seconds in the telemetry output:

```bash
# Watch temperature in real-time
python3 ezgripper_dds_driver.py --side left | grep "temp="

# Example output:
📡 TELEMETRY: state=idle, pos=50.0% (cmd=50.0%), effort=10%, contact=False, temp=42.5°C, error=0
📡 TELEMETRY: state=moving, pos=45.2% (cmd=40.0%), effort=17%, contact=False, temp=43.1°C, error=0
```

### Temperature Thresholds

Configured in `config_default.json`:

```json
"temperature": {
  "warning": 60,      // Log warning at 60°C
  "advisory": 70,     // Advisory level at 70°C  
  "shutdown": 75,     // Shutdown at 75°C
  "hardware_max": 80  // Hardware maximum (servo protection)
}
```

### DDS Telemetry Access

Temperature is published via DDS at 30Hz on topic `rt/gripper/{side}/telemetry`:

```python
from unitree_sdk2py.core.channel import ChannelSubscriber
from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_
import json

def telemetry_callback(msg):
    data = json.loads(msg.data)
    temp = data['hardware']['temperature_c']
    print(f"Temperature: {temp:.1f}°C")

subscriber = ChannelSubscriber("rt/gripper/left/telemetry", String_)
subscriber.Init(telemetry_callback)
```

### Dex1 State Messages

Temperature is also included in Dex1 state messages at 200Hz on `rt/dex1/{side}/state`:

```python
from unitree_sdk2py.core.channel import ChannelSubscriber
from unitree_sdk2py.go2.sport.sport_client import MotorStates_

def state_callback(msg):
    if msg.states and len(msg.states) > 0:
        temp = msg.states[0].temperature  # uint8, degrees Celsius
        print(f"Temperature: {temp}°C")

subscriber = ChannelSubscriber("rt/dex1/left/state", MotorStates_)
subscriber.Init(state_callback)
```

### Temperature Monitoring Best Practices

1. **Monitor during extended operation** - Temperature rises during continuous use
2. **Watch for rapid increases** - Sudden temperature spikes may indicate issues
3. **Normal operating range** - 40-55°C during typical operation
4. **Warning threshold** - 60°C indicates elevated temperature, reduce duty cycle
5. **Critical threshold** - 75°C triggers automatic shutdown for servo protection

## GraspManager State Machine

The driver includes an intelligent grasp management system that maintains grip on objects:

**States:**
- **IDLE** - Gripper at rest, minimal force (0%)
- **MOVING** - Actively moving to commanded position (17% force = ~640mA actual)
- **CONTACT** - Detected obstacle, transitioning to grasp (10% force)
- **GRASPING** - Holding object at detected position (10% force = ~110mA actual)

**Active Grasp Management:**
- Continuous command stream at 30Hz from XR teleoperate
- GRASPING state maintains grip despite continuous close commands
- Only exits GRASPING on opening commands (position > grasping setpoint)
- Prevents oscillation and overload from repeated stall detection

**Stall Detection:**
- Monitors position stagnation (3 consecutive samples within 2.0% range)
- Triggers CONTACT → GRASPING transition
- Reduces force from 17% (moving) to 10% (grasping) to prevent overload

## Force Configuration

Force settings are configurable in `config_default.json`:

```json
"force_management": {
  "moving_force_pct": 17,      // 17% = 190mA commanded, ~640mA actual
  "holding_force_pct": 10,     // 10% = 112mA commanded, ~110mA actual  
  "grasping_force_pct": 10,    // 10% = 112mA commanded, ~110mA actual
  "idle_force_pct": 0          // 0% = no force when idle
}
```

**Current Multiplier:**
- MOVING state: ~3.2-3.4x commanded current (fighting spring force)
- GRASPING state: ~1.0x commanded current (at equilibrium)
- Example: 17% command = 190mA → ~640mA actual when closing

**Thermal Considerations:**
- Lower forces reduce heat generation
- Temperature monitored at 30Hz
- Overload protection triggers at ~70-80°C

## Operating Mode 5 (Current-Based Position Control)

The driver uses Dynamixel Operating Mode 5 for optimal performance:

**Why Mode 5:**
- Designed for joints with constant loads (gravity, springs)
- Active current control prevents overload under sustained force
- Used in humanoid robots (soccer players) for similar applications
- Reference: ROBOTIS gripper RH-P12-RN uses Mode 5 exclusively

**Control Flow:**
```
Position PID → Desired Current → Goal Current Limit → Current Controller → PWM → Motor
```

**Mode 5 vs Mode 4:**
- Mode 4: PID outputs PWM directly, Goal Current is just a limit
- Mode 5: PID outputs desired current, current controller actively manages torque
- Mode 5 prevents unlimited current draw when position cannot be reached

**Automatic Parameter Reset:**
- Switching to Mode 5 automatically resets Position PID Gain and PWM Limit
- Values optimized by ROBOTIS for current control
- Should not be manually overridden unless necessary

## GUI Control Tool

A GUI tool is provided for testing and manual control:

```bash
python3 grasp_control_gui.py --side left
```

**Features:**
- Position slider (0-100%)
- Quick position buttons (Open 100%, Half 50%, Close 0%)
- Live telemetry display:
  - GraspManager state (IDLE/MOVING/CONTACT/GRASPING) with color coding
  - Position, effort, temperature
  - Contact detection status
  - Hardware errors
- Continuous command mode (200Hz) or on-demand
- Direct hardware calibration button

**Telemetry Display:**
- Reads from `/tmp/driver_test.log`
- Updates at 2Hz
- Color-coded states: IDLE (gray), MOVING (blue), CONTACT (orange), GRASPING (green)

## Configuration

See [CONFIGURATION.md](./CONFIGURATION.md) for detailed configuration options including:
- Servo parameters and limits
- Communication settings
- Monitoring thresholds
- Calibration parameters
- Force management settings
- Stall detection parameters

## Servo Reset and Recovery

### Resetting the Servo

The servo can be reset by restarting the driver. This gives full control to the robot system to reset the servo state, which is critical for autonomous operation.

**To reset the servo:**
```bash
# Kill the running driver
pkill -9 -f ezgripper_dds_driver

# Restart the driver (will auto-calibrate and reset servo state)
python3 ezgripper_dds_driver.py --side left
```

**When to reset:**
- When gripper becomes unresponsive
- After communication failures
- To clear error states

**Note:** The driver restart performs a full initialization sequence including calibration, which resets the servo to a known good state.

## Information for Autonomous Systems

This section provides key information for robots and autonomous systems integrating the EZGripper driver.

### Servo State Management

**Automatic Reset Capability:**
- The servo can be reset by restarting the driver process
- No manual intervention required - fully autonomous
- Driver restart clears all error states and recalibrates
- This enables the robot to recover from errors without human assistance

**Error Handling:**
- Hardware errors are detected and logged
- Driver restart is the recommended recovery method
- Error states are logged but don't prevent driver initialization

### Control Flow

**Command Execution:**
- Commands received via DDS at up to 200 Hz
- Control loop executes at 30 Hz with bulk operations
- Position updates happen every control cycle (30 Hz)
- State feedback published at 200 Hz using predictive model

**Error Recovery:**
1. Detect error via hardware error monitoring
2. Log error details (error code, timestamp)
3. Restart driver process to reset servo
4. Driver auto-calibrates and resumes normal operation

**Calibration:**
- Runs automatically on driver startup
- Uses position control with collision detection
- Completes in ~1 second
- Works even when hardware errors are present
- Can be skipped with `--no-calibrate` flag if needed

### Integration Points

**DDS Topics:**
- Commands: `rt/dex1/{side}/cmd` (MotorCmds_)
- State: `rt/dex1/{side}/state` (MotorStates_)
- Compatible with Unitree G1 motor specification

**Position Feedback:**
- Real-time position updates at 30 Hz from servo
- Predictive model provides 200 Hz state publishing
- Position range: 0.0 rad (closed) to 5.4 rad (open)

**Health Monitoring:**
- Hardware error detection via bulk sensor reads
- Temperature monitoring and thermal prediction
- Contact detection via current monitoring
- All monitoring data available at 30 Hz

### Autonomous Operation Recommendations

1. **Monitor hardware_healthy flag** - Indicates servo error state
2. **Restart driver on persistent errors** - Automatic recovery mechanism
3. **Use calibration on startup** - Ensures consistent zero position
4. **Monitor position feedback** - Verify commands are being executed
5. **Check state publishing rate** - Should maintain ~200 Hz

## Known Limitations

**Present Current Register (Mode 5):**
- Register 126 (Present Current) may report 0mA during active position control
- This is a Mode 5 firmware behavior, not a driver bug
- Current is being applied (you can feel the force), but register doesn't reflect it
- Stall detection uses position stagnation instead of current monitoring

**Spring Force Current Multiplier:**
- Gripper has internal spring that resists closing
- Actual current draw is 3.2-3.4x commanded when fighting spring
- Example: 17% command (190mA) → ~640mA actual current
- This is normal behavior, not a malfunction
- Force settings account for this multiplier

**Temperature Monitoring:**
- Continuous high force can cause thermal overload
- Monitor temperature (register 146) at 30Hz
- Overload typically triggers at 70-80°C
- Reduce forces if temperature rises rapidly
- Allow servo to cool between intensive operations

**Calibration Time:**
- Takes 2-4 seconds depending on starting position
- Requires 5 consecutive stable readings (165ms minimum)
- 1 second hardcoded wait after moving to 50%
- Cannot be significantly accelerated without reducing reliability

## Troubleshooting

See [BUG_REPORT.md](./BUG_REPORT.md) for common issues and troubleshooting steps.

## License

This project is part of the SAKErobotics EZGripper ecosystem for Unitree robots.
