# Thermal Cycling Test Specification

**Version:** 1.0  
**Date:** 2026-02-14  
**Purpose:** Characterize gripper power consumption during rapid cycling via thermal method

---

## 1. Overview

The Thermal Cycling Test measures power consumption by monitoring temperature rise during continuous rapid grasp cycles. This test characterizes power consumption during dynamic operation (movement + contact).

---

## 2. Test Objectives

1. **Measure thermal power consumption** during continuous cycling at multiple force levels
2. **Establish cycling power profile** for operational duty cycles
3. **Validate DDS-only communication** with ezgripper driver
4. **Measure cycle rate** and movement characteristics

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

1. **Record Starting Temperature**
   - Read current temperature from DDS state
   - Purpose: Establish baseline for temperature rise

2. **Continuous Cycling**
   - **Closing Phase:**
     - Command: 0% position, test force level
     - Monitor: Position until < 3%
     - Transition: Switch to opening when position < 3%
   
   - **Opening Phase:**
     - Command: 30% position, test force level
     - Monitor: Position until > 27%
     - Transition: Switch to closing when position > 27%
   
   - **Duration:** Fixed time (default 120 seconds)
   - **Cycle Count:** Increment by 0.5 at each transition
   - **Purpose:** Generate continuous power consumption from movement and contact

3. **Cooldown Period**
   - Command: 30% position, low force (10%)
   - Duration: 60 seconds (between tests only)
   - Purpose: Allow thermal stabilization

### 4.2 Force Levels

- **Base Force:** 15% (configurable via `--base-force`)
- **Test Forces:** 1x, 2x, 3x base force
- **Default:** 15%, 30%, 45%

### 4.3 Test Duration

- **Default:** 120 seconds per force level (configurable via `--duration`)
- **No timeout:** Test runs for fixed duration regardless of temperature
- **Measurement:** Continuous throughout test

---

## 5. Data Collection

### 5.1 Detailed Measurements (30Hz)

Record at every control cycle during cycling:

| Field | Source | Type | Description |
|-------|--------|------|-------------|
| `timestamp` | System | float | Unix timestamp |
| `elapsed_sec` | Calculated | float | Time since test start |
| `force_pct` | Test param | float | Commanded force % |
| `cycle_number` | Calculated | int | Current cycle count |
| `position_pct` | DDS state | float | Actual position % |
| `target_position_pct` | Calculated | float | Target position (0% or 30%) |
| `temperature_c` | DDS state | int | Motor temperature °C |
| `phase` | Calculated | str | 'closing' or 'opening' |
| `velocity` | DDS state | float | Motor velocity (dq) |
| `torque` | DDS state | float | Estimated torque (tau_est) |
| `lost` | DDS state | int | Communication error flag |
| `reserve` | DDS state | int | Status/error codes |

### 5.2 Test Results (Per Force Level)

| Field | Type | Description |
|-------|------|-------------|
| `force_pct` | float | Commanded force % |
| `force_multiplier` | float | Multiplier vs base (1x, 2x, 3x) |
| `total_cycles` | int | Number of complete cycles |
| `total_time_sec` | float | Actual test duration |
| `start_temp_c` | float | Temperature at test start |
| `end_temp_c` | float | Temperature at test end |
| `temp_rise_c` | float | Total temperature rise |
| `heating_rate_c_per_sec` | float | Temp rise / total time |
| `relative_power` | float | Heating rate / base rate |

### 5.3 Output Files

1. **`{prefix}_measurements.csv`** - All 30Hz detailed measurements
2. **`{prefix}_results.csv`** - Summary results per force level
3. **`{prefix}_summary.json`** - Aggregated test summary

---

## 6. Expected Behavior

### 6.1 Cycle Characteristics

- **Cycle Time:** ~1-3 seconds per complete cycle (30% → 0% → 30%)
- **Closing Time:** ~0.5-1.5 seconds (30% → 0%)
- **Opening Time:** ~0.5-1.5 seconds (0% → 30%)
- **Total Cycles (120s):** ~40-120 cycles depending on force

### 6.2 Position Response

- **Closing Target:** 0% (contact with spring)
- **Opening Target:** 30% (release spring)
- **Transition Threshold:** ±3% hysteresis
- **Position Range:** 0-30% continuous oscillation

### 6.3 Thermal Response

**Ideal (Linear):**
- 2x force → 2x heating rate → 2x relative power
- 3x force → 3x heating rate → 3x relative power

**Actual (May be Non-Linear):**
- Higher forces = faster movement = more cycles = more power
- Thermal protection may activate at high temps
- Current limiting may cap actual force

### 6.4 Temperature Rise

- **15% force:** ~2-5°C rise in 120s (baseline)
- **30% force:** ~4-10°C rise in 120s (2-2.5x baseline)
- **45% force:** ~6-15°C rise in 120s (3-4x baseline, if linear)

---

## 7. Pass/Fail Criteria

### 7.1 Test Validity

**PASS if:**
- ✅ Test completes full duration
- ✅ Cycles occur continuously (no stalls)
- ✅ Temperature rises or stays stable
- ✅ Position oscillates between targets
- ✅ No communication errors (`lost` = 0)
- ✅ DDS state updates continuously

**FAIL if:**
- ❌ Gripper stalls (no position change for >5s)
- ❌ Temperature exceeds 75°C
- ❌ Communication errors (`lost` > 0)
- ❌ Cycle count = 0 (no movement)

### 7.2 Data Quality

**PASS if:**
- ✅ Measurement rate ~30Hz (±10%)
- ✅ No missing DDS state fields
- ✅ Temperature readings are integers
- ✅ Cycle count increments properly
- ✅ Phase alternates between 'closing' and 'opening'
- ✅ All output files created successfully

---

## 8. Known Limitations

1. **Temperature Resolution:** Integer °C (±0.5°C uncertainty)
2. **Starting Temperature:** Higher starting temp may affect results
3. **Ambient Temperature:** Not controlled or measured
4. **Cycle Rate Variation:** Depends on force level and temperature
5. **Spring Aging:** Spring properties may change over time
6. **Movement Power:** Cannot separate movement vs contact power

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
- DDS driver continues sending last command (cycling between 0% and 30%)
- Gripper may be closed with force applied when process terminates
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
/usr/bin/python3 /home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver/thermal_cycling_dds.py --side left --base-force 15 --duration 120
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
| `--duration` | int | 120 | Test duration in seconds |
| `--output` | str | auto | Output filename prefix |

---

## 11. Validation Checklist

Implementation must satisfy:

- [ ] Uses ONLY DDS pub/sub (no direct gripper calls)
- [ ] Publishes commands at 30Hz continuously
- [ ] Reads state at 30Hz continuously
- [ ] Records all 12 DDS state fields
- [ ] Tests 3 force levels (1x, 2x, 3x)
- [ ] Implements continuous cycling (no pauses)
- [ ] Implements 60s cooldown between tests
- [ ] Creates 3 output files (measurements, results, summary)
- [ ] Logs progress every 5 seconds
- [ ] Tracks cycle count correctly
- [ ] Alternates between closing and opening phases
- [ ] Calculates relative power correctly

---

## 12. Differences from Grasp Test

| Aspect | Grasp Test | Cycling Test |
|--------|------------|--------------|
| **Motion** | Static hold | Continuous cycling |
| **Duration** | Variable (until temp rise) | Fixed (120s default) |
| **Cycles** | 0 (static) | 40-120 cycles |
| **Position** | ~0-5% (contact) | 0-30% (oscillating) |
| **Power Source** | Static holding force | Movement + contact |
| **Timeout** | 600s | None (fixed duration) |
| **Measurement Fields** | 10 fields | 12 fields (adds cycle, target, phase) |
