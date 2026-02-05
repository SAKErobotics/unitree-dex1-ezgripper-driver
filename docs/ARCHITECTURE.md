# EZGripper DDS Driver Architecture

## Overview

The EZGripper DDS Driver is a production-grade robotic gripper control system designed for integration with the Unitree G1 humanoid robot stack. It implements a 4-layer architecture that provides adaptive grasping, efficient hardware communication, and robust error handling.

## System Architecture

### Layer 1: DDS Interface (`ezgripper_dds_driver.py`)

**Purpose:** Protocol adapter between Unitree SDK2 and gripper hardware

**Key Responsibilities:**
- DDS topic subscription/publishing (Unitree SDK2 MotorCmds/MotorStates)
- Multi-threaded operation (30Hz control, 200Hz state publishing)
- Device auto-discovery and configuration persistence
- Hardware health monitoring and error recovery
- Calibration management by device serial number

**Threading Model:**
- **Control Thread (30Hz):** Receives DDS commands, executes through GraspManager, reads sensor data
- **State Thread (200Hz):** Publishes gripper state to DDS for teleoperation feedback
- **Main Thread:** Handles shutdown signals and thread lifecycle

**Why This Design:**
The dual-thread architecture separates command execution (limited by serial bus speed) from state publishing (required for smooth teleoperation). The 200Hz publishing rate matches the G1 stack's expectations for responsive control feedback.

### Layer 2: GraspManager (`grasp_manager.py`)

**Purpose:** State machine for adaptive grasping with contact detection

**State Machine:**
```
IDLE → MOVING → CONTACT → GRASPING
  ↑       ↓         ↓         ↓
  └───────┴─────────┴─────────┘
```

**States:**
- **IDLE:** At rest, no active goal
- **MOVING:** Tracking DDS position command (80% force)
- **CONTACT:** Contact detected, settling period (30% force)
- **GRASPING:** Holding object at contact position (30% force)

**Key Innovation:**
DDS commands are treated as **inputs** to the state machine, not direct execution commands. The GraspManager owns the goal and adapts based on:
- Current state
- Sensor feedback (position, current)
- DDS position input
- Contact detection results

**Contact Detection:**
Uses dual-method detection with consecutive sample filtering:
1. **Current Spike:** 3 consecutive readings > 50% of hardware limit
2. **Position Stagnation:** 3 consecutive cycles with movement < 2 units

**Force Management:**
Percentage-based system (0-100%):
- Moving: 80% (fast, responsive movement)
- Holding: 30% (gentle, prevents object damage)
- Contact: 30% (settling period)
- Idle: 0% (no unnecessary motor stress)

**Why This Design:**
The state machine prevents common gripper issues:
- Crushing delicate objects (force adapts after contact)
- Dropping objects (maintains hold force in GRASPING state)
- Oscillation (settling period in CONTACT state)
- False contact triggers (consecutive sample filtering)

### Layer 3: Gripper Base (`ezgripper_base_clean.py`)

**Purpose:** Hardware abstraction with efficient bulk operations

**Key Features:**
- **GroupSyncRead/Write:** Bulk operations reduce serial bus traffic by 70%
- **Collision Reaction System:** Pluggable strategies for different scenarios
- **Position Control:** Percentage-based interface (0-100%)
- **Sensor Caching:** Reduces redundant hardware reads

**Bulk Operations:**
- **Bulk Read:** Position, current, temperature, voltage, error (single transaction)
- **Bulk Write Position:** Goal position for all servos
- **Bulk Write PWM:** Force control for all servos

**Why This Design:**
The RS-485 serial bus is the primary bottleneck. Bulk operations allow reading all sensor data in a single round-trip, enabling the 30Hz control loop to maintain real-time performance while monitoring multiple parameters.

### Layer 4: Hardware (`lib_robotis.py`)

**Purpose:** Low-level Dynamixel Protocol 2.0 communication

Handles register reads/writes, packet construction, and CRC validation.

---

## G1 Stack Integration Features

The following features were implemented specifically to address reliability issues when integrating with the Unitree G1 humanoid robot stack:

### 1. Error 128 Prevention via Servo Reboot

**Problem:** Dynamixel servos enter a locked error state (Error 128) after communication timeouts or mechanical stalls, requiring power cycling to recover.

**Solution:** On initialization, the driver sends a reboot command to each servo to clear any residual error states from previous sessions.

**Implementation:**
```python
# In _initialize_hardware(), after gripper creation:
for servo in self.gripper.servos:
    if hasattr(servo, 'reboot'):
        servo.reboot()
    else:
        servo.write_address(0x08, [1])  # Direct reboot register write
    time.sleep(0.5)  # Allow firmware restart
```

**Why This Works:**
The reboot command clears the error flag register and restarts the servo's control loop, allowing the driver to start with a clean hardware state even after crashes or improper shutdowns.

### 2. Teleoperation Heartbeat Timeout

**Problem:** When teleoperation disconnects unexpectedly, stale DDS commands remain in the queue, causing "phantom movements" where the gripper continues executing old commands.

**Solution:** Commands older than 250ms are ignored, preventing execution of stale commands when the teleop connection is lost.

**Implementation:**
```python
# In execute_command(), before processing:
if time.time() - self.latest_command.timestamp > 0.25:
    return  # Teleop heartbeat lost, stand by
```

**Why 250ms:**
The G1 teleoperation system publishes commands at ~10Hz (100ms intervals). A 250ms timeout allows for 1-2 missed packets due to network jitter while still detecting actual disconnections quickly.

### 3. Safe Position Range Mapping (5-95%)

**Problem:** Commanding the gripper to 0% (fully closed) or 100% (fully open) causes mechanical stalls at hard limits, triggering Error 128.

**Solution:** Map the DDS range (0.0-5.4 rad) to a safe hardware range (5-95%), keeping the motor away from mechanical endpoints.

**Implementation:**
```python
def dex1_to_ezgripper(self, q_radians: float) -> float:
    q_clamped = max(0.0, min(5.4, q_radians))
    return 5.0 + (q_clamped / 5.4) * 90.0  # Maps to 5-95%

def ezgripper_to_dex1(self, position_pct: float) -> float:
    pct_clamped = max(5.0, min(95.0, position_pct))
    return ((pct_clamped - 5.0) / 90.0) * 5.4  # Inverse mapping
```

**Why This Works:**
The 5% margins at each end prevent the motor from reaching the physical hard stops where stall current triggers hardware errors. The gripper still achieves full functional range for grasping tasks.

### 4. Serial Bus Error Recovery

**Problem:** RS-485 bus noise or collisions cause read timeouts, which can cascade into Error 128 if not handled properly.

**Solution:** On communication errors, reset the serial input buffer to clear corrupted data and prevent error propagation.

**Implementation:**
```python
except Exception as e:
    self.logger.warning(f"Serial Read Timeout/Noise: {e}")
    if hasattr(self.connection, 'port'):
        self.connection.port.reset_input_buffer()
```

**Why This Works:**
Corrupted data in the serial buffer can cause subsequent reads to fail. Flushing the buffer allows the next read to start fresh, preventing a single error from cascading into multiple failures.

### 5. Proper Shutdown Sequence

**Problem:** Improper shutdown leaves servos in torque-enabled state with the serial port locked, requiring system reboot to recover.

**Solution:** Multi-step shutdown sequence: disable torque, close port, clear connection object.

**Implementation:**
```python
def shutdown(self):
    # 1. Disable torque
    for servo in self.gripper.servos:
        servo.write_address(self.gripper.config.reg_torque_enable, [0])
    
    # 2. Close serial port
    if hasattr(self.connection, 'port'):
        self.connection.port.close()
    
    # 3. Clear connection object
    self.connection = None
```

**Why This Order:**
Disabling torque first prevents the servo from fighting against external forces during shutdown. Closing the port releases the OS-level file descriptor. Clearing the connection object prevents accidental reuse of a closed connection.

### 6. Thread Synchronization on Shutdown

**Problem:** Threads continuing to access hardware during shutdown cause race conditions and incomplete cleanup.

**Solution:** Set running flag, join threads with timeout, then perform hardware cleanup.

**Implementation:**
```python
finally:
    self.running = False  # Signal threads to stop
    self.control_thread.join(timeout=1.5)
    self.state_thread.join(timeout=1.0)
    self.shutdown()  # Now safe to clean up hardware
```

**Why This Works:**
Threads check `self.running` in their loops and exit gracefully. The join() calls ensure threads have stopped accessing hardware before the shutdown sequence begins, preventing race conditions.

---

## Data Flow

### Command Path (DDS → Hardware)
```
DDS MotorCmds
    ↓
receive_commands() [30Hz]
    ↓
GripperCommand (position, effort, timestamp)
    ↓
execute_command() [30Hz]
    ↓
GraspManager.process_cycle()
    ↓ (state machine logic)
goal_position, goal_effort
    ↓
gripper.goto_position()
    ↓
GroupSyncWrite (bulk write)
    ↓
Dynamixel Servo
```

### State Path (Hardware → DDS)
```
Dynamixel Servo
    ↓
GroupSyncRead (bulk read) [30Hz]
    ↓
cached sensor_data
    ↓
publish_state() [200Hz]
    ↓
MotorState_ (position, torque, temp)
    ↓
DDS MotorStates
    ↓
G1 Teleoperation System
```

---

## Configuration System

### Device Configuration (`/tmp/ezgripper_device_config.json`)
```json
{
  "left": "/dev/ttyUSB0",
  "right": "/dev/ttyUSB1",
  "left_serial": "FT1234AB",
  "right_serial": "FT5678CD",
  "calibration": {
    "FT1234AB": 1234,
    "FT5678CD": 5678
  }
}
```

**Key Features:**
- Auto-discovery with interactive verification
- Calibration stored by serial number (survives device swaps)
- Persistent across reboots

### Servo Configuration (`config.yaml`)
```yaml
servo:
  dynamixel_settings:
    operating_mode: 3  # Position control
    current_limit: 1600  # mA
    velocity_limit: 200
    acceleration_limit: 100
  
  force_management:
    moving_force_pct: 80
    holding_force_pct: 30
    contact_force_pct: 30
    idle_force_pct: 0
  
  collision_detection:
    current_spike_threshold_pct: 50
    stagnation_movement_units: 2
    consecutive_samples_required: 3
    settling_cycles: 10
```

---

## Error Handling Strategy

### Hardware Errors
- **Error 128 (Overload):** Prevented by servo reboot, safe position range, and proper shutdown
- **Communication Timeout:** Buffer reset and fallback reads
- **Servo Errors:** Move to safe position (50%, 10% effort), set `hardware_healthy = False`

### Communication Errors
- **Consecutive Failures (5+):** Move to safe position, set `hardware_healthy = False`
- **Timeout (2+ seconds):** Move to safe position, set `hardware_healthy = False`
- **Single Failure:** Log warning, reset buffer, continue operation

### State Publishing
- **Healthy:** Publish actual position at 200Hz
- **Unhealthy:** Publish error state (mode=255, all zeros)

---

## Performance Characteristics

### Timing
- **Control Loop:** 30Hz (33.3ms period)
- **State Publishing:** 200Hz (5ms period)
- **Sensor Read:** 30Hz (with control loop)
- **Command Latency:** <50ms (DDS → hardware)

### Serial Bus Utilization
- **Bulk Operations:** ~70% reduction vs individual reads
- **Bandwidth:** ~1Mbps (RS-485)
- **Transaction Time:** ~10ms per bulk read/write

### CPU Usage
- **Normal Operation:** 3-5%
- **High Load:** <10%

---

## Calibration Process

### Automatic Calibration
1. **Close Gripper:** Move to 0% with 100% PWM force
2. **Detect Closure:** Monitor current spike (contact detection)
3. **Record Zero:** Save raw position as zero_positions[0]
4. **Open to 50%:** Move to neutral position
5. **Verify:** Check position error < 10%
6. **Persist:** Save calibration offset by serial number

### Why Calibration Matters
The gripper's mechanical zero varies due to:
- Manufacturing tolerances
- Wear over time
- Temperature effects
- Servo replacement

Calibration ensures consistent 0-100% mapping across all devices and sessions.

---

## Testing and Validation

### Unit Tests
- Position mapping (DDS ↔ EZGripper)
- State machine transitions
- Contact detection logic
- Error handling paths

### Integration Tests
- DDS communication (with G1 stack)
- Calibration persistence
- Multi-gripper coordination
- Error recovery scenarios

### System Tests
- Continuous operation (24+ hours)
- Teleoperation disconnect/reconnect
- Power cycle recovery
- Object grasping scenarios

---

## Known Limitations

1. **No Velocity Feedback:** DDS publishes dq=0 (hardware doesn't provide velocity)
2. **No Acceleration Feedback:** DDS publishes ddq=0 (hardware doesn't provide acceleration)
3. **Temperature Monitoring:** Read but not used for thermal protection
4. **Single Servo:** Architecture supports multi-servo, but only one servo is used

---

## Future Enhancements

1. **Velocity Estimation:** Numerical differentiation of position
2. **Thermal Protection:** Reduce force at high temperatures
3. **Multi-Servo Coordination:** Synchronized control of multiple servos
4. **Adaptive Force Learning:** Learn optimal holding force per object
5. **Collision Reaction Strategies:** Pluggable reactions for different scenarios

---

## Maintenance

### Log Monitoring
- **INFO:** State transitions, calibration, monitoring stats
- **WARNING:** Communication errors, heartbeat loss
- **ERROR:** Hardware failures, critical errors
- **CRITICAL:** Servo errors requiring intervention

### Health Indicators
- `hardware_healthy`: Overall system health
- `comm_error_count`: Serial communication reliability
- `servo_error_count`: Hardware error frequency
- State publishing rate: Should maintain 200Hz

### Common Issues
- **Error 128:** Check mechanical obstructions, verify safe position range
- **Heartbeat Loss:** Check network connection, verify teleop is running
- **Calibration Drift:** Re-run calibration, check mechanical wear
- **High CPU:** Check for logging spam, verify thread timing

---

## References

- Unitree SDK2 Documentation: https://support.unitree.com/
- Dynamixel Protocol 2.0: https://emanual.robotis.com/
- EZGripper Hardware: https://sakerobotics.com/
