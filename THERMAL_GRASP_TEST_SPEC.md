# Thermal Grasp Test Specification

**Version:** 1.0  
**Date:** 2026-02-14  
**Purpose:** Characterize gripper power consumption during static hold via thermal method

---

## 1. Overview

The Thermal Grasp Test measures power consumption by monitoring temperature rise during a static grasp hold. This test characterizes the relationship between commanded force and actual power dissipation.

---

## 2. Test Objectives

1. **Measure thermal power consumption** at multiple force levels during static hold
2. **Establish force-to-power relationship** to predict operational heating
3. **Validate DDS-only communication** with ezgripper driver
4. **Detect thermal limits** or current limiting behavior

---

## 3. Test Architecture

### 3.1 Communication Requirements

**CRITICAL:** Test MUST use ONLY DDS interfaces. No direct gripper code calls.

- **Command Topic:** `rt/dex1/{side}/cmd` (MotorCmds_)
- **State Topic:** `rt/dex1/{side}/state` (MotorStates_)
- **Command Rate:** 30Hz continuous
- **State Read Rate:** 30Hz continuous

### 3.2 Dependencies

- **ezgripper_dds_driver** must be running before test starts
- Driver handles calibration automatically on startup
- Test assumes gripper is already calibrated

---

## 4. Test Procedure

### 4.1 Test Sequence

For each force level (15%, 30%, 45%):

1. **Move to Start Position**
   - Command: 30% position, low force (30%)
   - Duration: 3 seconds
   - Purpose: Establish consistent starting position

2. **Close to Contact**
   - Command: 0% position, test force level
   - Monitor: Position until < 3%
   - Purpose: Engage gripper spring mechanism

3. **Static Hold**
   - Command: 0% position, test force level (continuous at 30Hz)
   - Monitor: Temperature rise
   - Duration: Until target temperature rise OR 10 minute timeout
   - Purpose: Measure steady-state power consumption

4. **Return to Open**
   - Command: 30% position, low force (30%)
   - Duration: 1 second
   - Purpose: Release spring tension

5. **Cooldown Period**
   - Command: 30% position, low force (10%)
   - Duration: 60 seconds (between tests only)
   - Purpose: Allow thermal stabilization

### 4.2 Force Levels

- **Base Force:** 15% (configurable via `--base-force`)
- **Test Forces:** 1x, 2x, 3x base force
- **Default:** 15%, 30%, 45%

### 4.3 Temperature Rise Target

- **Default:** 5.0°C (configurable via `--temp-rise`)
- **Timeout:** 600 seconds (10 minutes)
- **Measurement:** Integer temperature from DDS state

---

## 5. Data Collection

### 5.1 Detailed Measurements (30Hz)

Record at every control cycle during static hold:

| Field | Source | Type | Description |
|-------|--------|------|-------------|
| `timestamp` | System | float | Unix timestamp |
| `elapsed_sec` | Calculated | float | Time since hold start |
| `force_pct` | Test param | float | Commanded force % |
| `position_pct` | DDS state | float | Actual position % |
| `temperature_c` | DDS state | int | Motor temperature °C |
| `grasp_state` | Fixed | str | 'holding' |
| `velocity` | DDS state | float | Motor velocity (dq) |
| `torque` | DDS state | float | Estimated torque (tau_est) |
| `lost` | DDS state | int | Communication error flag |
| `reserve` | DDS state | int | Status/error codes |

### 5.2 Test Results (Per Force Level)

| Field | Type | Description |
|-------|------|-------------|
| `force_pct` | float | Commanded force % |
| `force_multiplier` | float | Multiplier vs base (1x, 2x, 3x) |
| `start_temp_c` | float | Temperature at hold start |
| `end_temp_c` | float | Temperature at target rise |
| `temp_rise_c` | float | Actual temperature rise |
| `wall_time_sec` | float | Time to reach target rise |
| `heating_rate_c_per_sec` | float | Temp rise / wall time |
| `relative_power` | float | Heating rate / base rate |

### 5.3 Output Files

1. **`{prefix}_measurements.csv`** - All 30Hz detailed measurements
2. **`{prefix}_results.csv`** - Summary results per force level
3. **`{prefix}_summary.json`** - Aggregated test summary

---

## 6. Expected Behavior

### 6.1 Position Response

- **15% force:** Position ~4.5-5.0% (minimal spring stretch)
- **30% force:** Position ~1.0-1.5% (moderate spring stretch)
- **45% force:** Position ~0.5-1.5% (maximum spring stretch)

Lower position = more spring stretch = more holding force

### 6.2 Thermal Response

**Ideal (Linear):**
- 2x force → 2x heating rate → 2x relative power
- 3x force → 3x heating rate → 3x relative power

**Actual (May be Non-Linear):**
- Thermal protection may activate at high temps
- Current limiting may cap actual force
- Mechanical saturation may occur

### 6.3 Timing

- **15% force:** ~300-600s for 5°C rise (baseline)
- **30% force:** ~150-300s for 5°C rise (2-2.5x faster)
- **45% force:** ~100-200s for 5°C rise (3-4x faster, if linear)

---

## 7. Pass/Fail Criteria

### 7.1 Test Validity

**PASS if:**
- ✅ All force levels complete without timeout
- ✅ Temperature rises monotonically
- ✅ Position stabilizes during hold
- ✅ No communication errors (`lost` = 0)
- ✅ DDS state updates continuously

**FAIL if:**
- ❌ Timeout (600s) before reaching target temp rise
- ❌ Temperature decreases during hold
- ❌ Communication errors (`lost` > 0)
- ❌ Position drifts significantly during hold

### 7.2 Data Quality

**PASS if:**
- ✅ Measurement rate ~30Hz (±10%)
- ✅ No missing DDS state fields
- ✅ Temperature readings are integers
- ✅ All output files created successfully

---

## 8. Known Limitations

1. **Temperature Resolution:** Integer °C (±0.5°C uncertainty)
2. **Starting Temperature:** Higher starting temp may affect results
3. **Ambient Temperature:** Not controlled or measured
4. **Spring Aging:** Spring properties may change over time
5. **Current Measurement:** Present Current register unreliable in Mode 5

---

## 9. Safety Limits

### 9.1 Temperature Limits

- **Maximum Temperature:** 70°C (recommended backoff)
- **Absolute Maximum:** 80°C (operating limit)
- **Test Abort:** If temperature exceeds 75°C during test
- **Cooldown Required:** If temperature > 50°C before test

### 9.2 Graceful Shutdown

**CRITICAL:** Test implements signal handlers to ensure safe gripper release on interruption.

**When Ctrl+C or kill is used:**
1. Signal handler catches SIGINT/SIGTERM
2. Executes emergency stop procedure
3. Sends gripper to 30% open position with 10% force
4. Holds for 1 second (30 commands at 30Hz)
5. Process exits cleanly

**Why this is necessary:**
- Without signal handlers, killing the test leaves gripper actively holding force
- DDS driver continues sending last command (0% position with force)
- Gripper remains closed and applying force until manually released
- **User must unpower servo** to release force (unsafe)

**With signal handlers:**
- Gripper **always** releases force before process exits
- Safe interruption at any time during test
- No manual intervention required

---

## 10. Usage

```bash
# Terminal 1: Start DDS driver
python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0

# Terminal 2: Run test (full path recommended)
/usr/bin/python3 /home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver/thermal_grasp_dds.py --side left --base-force 15 --temp-rise 5.0
```

### Safe Interruption

**To stop test safely:**
- Press **Ctrl+C** in Terminal 2
- Or use `kill <pid>` (not `kill -9`)
- Gripper will automatically release force and move to safe position
- Process will exit cleanly

**DO NOT use `kill -9`** - this bypasses signal handlers and leaves gripper holding force

### Command Line Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--side` | str | required | 'left' or 'right' |
| `--base-force` | float | 15.0 | Base force percentage |
| `--temp-rise` | float | 5.0 | Target temperature rise °C |
| `--output` | str | auto | Output filename prefix |

---

## 11. Validation Checklist

Implementation must satisfy:

- [ ] Uses ONLY DDS pub/sub (no direct gripper calls)
- [ ] Publishes commands at 30Hz continuously
- [ ] Reads state at 30Hz continuously
- [ ] Records all 10 DDS state fields
- [ ] Tests 3 force levels (1x, 2x, 3x)
- [ ] Implements 60s cooldown between tests
- [ ] Creates 3 output files (measurements, results, summary)
- [ ] Logs progress every 2 seconds
- [ ] Implements 600s timeout per test
- [ ] Calculates relative power correctly
