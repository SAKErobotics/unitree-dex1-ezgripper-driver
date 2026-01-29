# Predictive State Publishing Algorithm for EZGripper DDS Driver

## Problem Statement

The G1 XR teleoperate system expects state feedback at 200 Hz, but the EZGripper hardware can only provide actual position readings at ~5-10 Hz due to serial communication overhead (~5-10ms per read). Publishing stale data causes control loop issues.

## Solution: Predictive State Model

Publish predicted gripper position at 200 Hz based on commanded position and calibrated movement speed, with periodic synchronization to actual hardware position.

---

## Algorithm Overview

### Phase 1: Movement Speed Calibration

**Goal:** Determine the maximum movement speed of the gripper in position mode with 100% torque.

**Procedure:**
1. Command gripper from 0% → 100% at 100% torque (position mode)
2. Measure elapsed time for full range movement
3. Calculate movement speed: `speed = 100% / elapsed_time` (units: %/second)
4. Repeat 3-5 times and average for accuracy
5. Store calibrated speed in device config file

**Measured Results (EZGripper with 100% effort, calibrated):**

**Overhead Characterization (20-30%, 20-40%, 20-50%, 20-60%, 20-70%, 20-80%):**
- Fixed overhead: **0.526 seconds** (DDS latency + command processing + position settling)
- Actual gripper movement speed: **952.43 %/sec** (very fast!)
- Time is dominated by overhead, not distance
- At 200 Hz: **4.76%** position change per update (5ms)

**Key Insight:** The gripper moves extremely fast (~0.1s for full range), but system overhead (primarily position stabilization wait) adds ~0.5s to all movements.

---

### Phase 2: Predictive State Publishing

**Goal:** Publish realistic gripper position at 200 Hz without blocking on serial reads.

**State Variables:**
- `commanded_position` - Latest position from DDS command
- `predicted_position` - Current predicted position (published to DDS)
- `actual_position` - Last known position from hardware (updated at 5-10 Hz)
- `movement_speed` - Calibrated speed from Phase 1 (e.g., 50 %/sec)

**Update Loop (200 Hz):**
```python
dt = 1/200  # 5ms timestep

# Calculate position delta based on calibrated speed
max_delta = movement_speed * dt  # 952.43 %/sec * 0.005s = 4.76%

# Move predicted position toward commanded position
position_error = commanded_position - predicted_position

if abs(position_error) <= max_delta:
    # Reached target
    predicted_position = commanded_position
else:
    # Move at maximum speed toward target
    direction = 1 if position_error > 0 else -1
    predicted_position += direction * max_delta

# Publish predicted position at 200 Hz
publish_state(predicted_position)
```

**Key Properties:**
- Never teleports - always respects velocity limit
- Realistic lag that matches actual gripper physics
- No serial communication required for prediction
- Smooth, continuous movement

---

### Phase 3: Reality Synchronization

**Goal:** Detect obstacles and correct prediction drift using actual hardware position.

**Hardware Position Read (5-10 Hz):**
```python
# Read actual position from hardware (slow, ~5-10ms)
actual_position = gripper.get_position()

# Compare predicted vs actual
position_divergence = abs(predicted_position - actual_position)

if position_divergence > STALL_THRESHOLD:
    # Gripper hit obstacle or stalled
    # Clamp predicted position to actual
    predicted_position = actual_position
    
    # Optionally increase reported torque to indicate resistance
    reported_torque = HIGH_TORQUE
else:
    # Normal operation - apply gentle correction
    # Slowly drift predicted toward actual to handle model errors
    correction_rate = 0.1  # 10% correction per sync
    predicted_position += (actual_position - predicted_position) * correction_rate
```

**Thresholds:**
- `STALL_THRESHOLD` = 10% - If predicted and actual diverge by more than 10%, gripper is stalled
- `correction_rate` = 0.1 - Gently correct prediction errors over time

---

## Implementation Architecture

### Threading Model

**Thread 1: DDS Command Reception (200 Hz)**
- Receive DDS commands from G1 XR
- Update `commanded_position`
- Update `predicted_position` using velocity model
- Publish predicted state at 200 Hz

**Thread 2: Hardware Execution (50 Hz)**
- Send position commands to servo via serial
- Read actual position at 5-10 Hz
- Detect resistance/stall
- Sync predicted position with actual

**Shared State (thread-safe):**
- `commanded_position` - Latest command from DDS
- `predicted_position` - Current prediction
- `actual_position` - Last hardware reading
- `movement_speed` - Calibrated speed constant

---

## Benefits

1. **Fast Feedback (200 Hz)** - Matches G1 XR expectations
2. **Realistic Lag** - Reflects actual gripper movement speed
3. **No Serial Bottleneck** - Predictions don't require hardware reads
4. **Obstacle Detection** - Divergence indicates resistance
5. **Self-Correcting** - Periodic sync prevents drift
6. **Smooth Control** - No position jumps or teleporting

---

## Calibration Data Storage

Store calibrated movement speed in device config file:

```json
{
  "left": "/dev/ttyUSB0",
  "left_serial": "DA1Z9T40",
  "calibration": {
    "DA1Z9T40": 3010
  },
  "movement_speed": {
    "DA1Z9T40": 50.0
  }
}
```

**Units:** %/second (percentage of full range per second)

---

## Future Enhancements

1. **Direction-specific speeds** - Opening vs closing may have different speeds
2. **Load-dependent speeds** - Speed may vary with gripper load
3. **Acceleration modeling** - Add acceleration/deceleration phases
4. **Adaptive calibration** - Automatically recalibrate during operation
5. **Predictive torque** - Model expected torque based on movement phase

### Torque-Based Force Feedback (Pressure Simulation)

**Goal:** Provide touch/pressure feedback to G1 XR control system using motor torque data.

**Approach:**

The EZGripper uses a hybrid position/torque control algorithm that switches between position mode and torque mode when resistance is detected. This mode switching provides a natural trigger for force feedback.

**Algorithm:**

1. **Normal Operation (Position Mode)**
   - No resistance detected
   - **Reported force = 0.0** (no contact with object)
   - `tau_est = 0.0` in published state
   - Gripper moving freely through air

2. **Resistance Detection Trigger**
   - Hybrid controller detects obstacle/resistance (gripper makes contact)
   - Switches from position mode → torque mode
   - **Begin reporting non-zero force feedback**
   - This is when apparent force starts to occur

3. **Force Lookup During Torque Mode**
   - Read motor current from servo (register 40)
   - Lookup force value from calibrated force table
   - Force table maps motor current → grip force (Newtons or %)
   - Publish as `tau_est` in `HGMotorState_`
   - **Force > 0 indicates object contact and grip strength**

4. **Force Table Calibration**
   - Pre-calibrate gripper with known loads
   - Measure motor current at different grip forces
   - Build lookup table: `current → force`
   - Store in device config

**Implementation:**

```python
# Only report force when in torque mode (resistance detected)
if gripper.control_mode == "torque":
    # Read motor current
    motor_current = gripper.servos[0].read_word(40)  # 0-1023
    
    # Lookup calibrated force from table
    grip_force = force_lookup_table[motor_current]  # Newtons or %
    
    # Publish as torque estimate
    motor_state.tau_est = grip_force / 10.0
else:
    # Position mode - no contact
    motor_state.tau_est = 0.0
```

**Benefits:**
- Force feedback only when meaningful (object contact)
- Accurate force via calibrated lookup table
- Leverages existing hybrid control algorithm
- No false positives during free movement
- Provides G1 XR with grip force information

**Calibration Data Storage:**

```json
{
  "force_lookup": {
    "DA1Z9T40": {
      "0": 0.0,
      "100": 0.5,
      "200": 1.2,
      "300": 2.0,
      ...
      "1023": 10.0
    }
  }
}
```

**Units:** Motor current (0-1023) → Grip force (Newtons or percentage)

---

## References

- G1 XR Teleoperate: 200 Hz command rate, 500 Hz state subscription
- EZGripper Serial: ~5-10ms per position read
- Dex1 Hand Protocol: `HGHandCmd_`, `HGHandState_` message types
