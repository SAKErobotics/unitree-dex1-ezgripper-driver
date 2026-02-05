# EZGripper Calibration Documentation

## Overview

Calibration establishes the gripper's zero position (fully closed) by detecting contact with a hard stop. This zero reference is used for all subsequent position calculations.

## Algorithm

### Contact Detection Method

The calibration uses **current-based contact detection** with **position stability verification**:

1. **Close slowly** with safe force (30% current = 480mA)
2. **Monitor current** for spike indicating contact
3. **Verify position stability** to confirm true contact (not transient spike)
4. **Record position** as zero reference
5. **Move to 50% position** with torque enabled to prevent spring force from opening gripper uncontrollably

### Parameters

```python
# Force settings
closing_current = 480mA          # 30% of 1600mA max
current_threshold = 400mA        # Contact detection threshold

# Stability verification
stable_required = 5              # Consecutive stable readings
position_threshold = 2 units     # Max position change when stable
cycle_period = 33ms              # Monitoring rate (30Hz)
timeout = 6.6 seconds            # Maximum calibration time
```

### State Machine

```
START
  ↓
CLOSING (write Goal Current + Goal Position)
  ↓
MONITORING (read current + position every 33ms)
  ↓
  ├─→ current > 400mA AND position stable for 5 cycles
  │     ↓
  │   CONTACT DETECTED
  │     ↓
  │   RECORD ZERO
  │     ↓
  │   MOVE TO 50% (with 40% current, torque enabled)
  │     ↓
  │   SUCCESS
  │
  └─→ timeout after 200 cycles (6.6s)
        ↓
      STOP MOTOR
        ↓
      FAILURE
```

## Implementation

### Code Location

`libezgripper/ezgripper_base_clean.py:483-594`

### Key Functions

```python
def calibrate(self):
    """
    Ultra-minimal calibration - just find zero
    
    Algorithm:
    1. Close slowly with safe force
    2. Monitor current
    3. Stop when current spike detected
    4. Record position as zero
    5. Open slowly
    6. Done
    """
```

### Register Operations

**Extended Position Control Mode (mode 4):**

1. **Goal Current (register 102)**: Sets torque limit
   - Write: 480mA (30% of 1600mA max)
   - 2 bytes, little-endian

2. **Goal Position (register 116)**: Sets target position
   - Write: current_pos - 15000 (beyond closed)
   - 4 bytes, signed, little-endian

3. **Present Current (register 126)**: Read actual current
   - Read: 2 bytes, signed
   - Monitor for >400mA spike

4. **Present Position (register 132)**: Read actual position
   - Read: 4 bytes, signed
   - Monitor for stability (change ≤2 units)

5. **Torque Enable (register 64)**: Enable/disable motor
   - Write: 0 to release after calibration

## Safety Features

### Current Limiting

- **Calibration current**: 480mA (30% of max)
- **Contact threshold**: 400mA
- **Hardware max**: 1600mA (never exceeded)

### Position Stability

Prevents false positives from:
- Transient current spikes
- Electrical noise
- Momentary contact

Requires **5 consecutive stable readings** (165ms total) before accepting contact.

### Timeout Protection

- **Maximum time**: 6.6 seconds
- **Action on timeout**: Stop motor, return failure
- **Prevents**: Infinite loops, thermal overload

### Immediate Release

After recording zero position:
- Torque disabled immediately (register 64 = 0)
- Prevents sustained force on hard stop
- Prevents servo overheating

## Configuration

### Config File

`config_default.json`:

```json
{
  "gripper": {
    "calibration": {
      "goto_position_target": -300,
      "goto_position_effort": 30,
      "settle_position": 50,
      "auto_on_init": true
    }
  }
}
```

### Parameters

- **goto_position_target**: -300% (beyond closed, ensures full closure)
- **goto_position_effort**: 30% (safe force level)
- **settle_position**: 50% (position to move to after calibration)
- **auto_on_init**: true (auto-calibrate on driver startup)

## Usage

### Manual Calibration

```python
from libezgripper import create_connection, create_gripper

connection = create_connection('/dev/ttyUSB0')
gripper = create_gripper(connection, 'test', [1])

# Run calibration
success = gripper.calibrate()

if success:
    print(f"Zero position: {gripper.zero_positions[0]}")
else:
    print("Calibration failed")
```

### Driver Calibration

```bash
# Auto-calibrate on startup (if auto_on_init=true)
python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0

# Manual calibration via driver
python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0 --calibrate
```

### GUI Calibration

The `grasp_control_gui.py` includes a "Calibrate Gripper" button that:
1. Bypasses DDS
2. Connects directly to hardware
3. Runs calibration
4. Saves zero offset to device config

## Persistence

### Storage Location

`/tmp/ezgripper_device_config.json`

### Format

```json
{
  "left": "/dev/ttyUSB0",
  "right": "/dev/ttyUSB1",
  "left_serial": "DA1Z9T40",
  "right_serial": "DA1Z9T41",
  "calibration": {
    "DA1Z9T40": 3731,
    "DA1Z9T41": 3698
  }
}
```

Calibration offsets are stored **by serial number**, not by side, to handle device swapping.

## Troubleshooting

### Calibration Fails (Timeout)

**Symptoms**: Timeout after 6.6 seconds, no contact detected

**Causes**:
- Gripper already at hard stop (current high but position not changing)
- Current threshold too high (>400mA)
- Gripper mechanically blocked

**Solutions**:
1. Manually open gripper before calibration
2. Lower current threshold to 300mA
3. Check for mechanical obstructions

### Servo Overload

**Symptoms**: High current (>1000mA), servo hot, Error 128

**Causes**:
- Calibration using too much force
- Torque not released after calibration
- Sustained force on hard stop

**Solutions**:
1. Verify closing_current = 480mA (30%)
2. Verify torque disable after calibration (register 64 = 0)
3. Check for code bugs (e.g., using old bulk_write_pwm instead of bulk_write_current)

### Incorrect Zero Position

**Symptoms**: Position readings offset, gripper doesn't close fully

**Causes**:
- False contact detection (transient spike)
- Calibration interrupted
- Wrong serial number mapping

**Solutions**:
1. Increase stable_required to 10 cycles
2. Re-run calibration
3. Verify serial number in device config

### Position Drift

**Symptoms**: Zero position changes over time

**Causes**:
- Mechanical wear
- Temperature effects
- Servo backlash

**Solutions**:
1. Re-calibrate periodically
2. Check for mechanical looseness
3. Consider temperature compensation

## Validation

### Post-Calibration Test

After calibration, the driver performs a validation test:

```python
# Move to 25% position
gripper.goto_position(25, 100)
time.sleep(1)

# Read actual position
actual = gripper.get_position()
error = abs(actual - 25.0)

# Verify accuracy
if error <= 10.0:
    print("✅ Calibration successful")
else:
    print(f"⚠️ Calibration issue (error: {error:.1f}%)")
```

### Expected Results

- **Error < 5%**: Excellent calibration
- **Error 5-10%**: Acceptable calibration
- **Error > 10%**: Re-calibrate recommended

## Best Practices

1. **Calibrate on startup**: Set `auto_on_init: true` in config
2. **Verify serial numbers**: Check device config after calibration
3. **Monitor current**: Watch for >1000mA during operation (indicates issue)
4. **Re-calibrate periodically**: Every 100 hours of operation or after mechanical changes
5. **Test after calibration**: Use validation test to confirm accuracy

## See Also

- [CONFIGURATION.md](../CONFIGURATION.md) - Configuration parameters
- [ERROR_MANAGEMENT.md](../ERROR_MANAGEMENT.md) - Error handling
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
