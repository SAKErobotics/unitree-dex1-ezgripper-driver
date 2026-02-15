# Force Optimization Guide

## Overview

This guide explains how to optimize gripper forces for stronger grasps without overloading the servo. The Force Optimization Tool provides interactive testing with real-time monitoring of current, temperature, and grasp stability.

## Force Settings That Affect Grasping

### Primary Force Parameters

Located in `config_default.json` under `servo.force_management`:

| Parameter | Default | Range | Effect on Grasping |
|-----------|---------|-------|-------------------|
| `moving_force_pct` | 17% | 10-100% | **Closing speed and contact force**. Higher = faster closing, stronger initial contact. Current multiplier: ~3.4x due to spring (17% → ~640mA actual) |
| `grasping_force_pct` | 10% | 5-50% | **Holding force after contact**. Higher = stronger grip, more thermal load. At equilibrium: ~1.0x multiplier (10% → ~110mA actual) |
| `idle_force_pct` | 10% | 0-30% | **Holding force when idle**. Maintains position against spring. Minimal thermal impact |

### Secondary Parameters

Located in `config_default.json` under `servo.collision_detection`:

| Parameter | Default | Range | Effect on Grasping |
|-----------|---------|-------|-------------------|
| `consecutive_samples_required` | 3 | 2-5 | **Contact detection sensitivity**. Lower = faster detection, more false positives |
| `stall_tolerance_pct` | 2.0% | 0.5-5.0% | **Position stability threshold**. Lower = tighter detection, may miss soft contacts |
| `contact_settle_time_ms` | 0ms | 0-500ms | **Settling time before grasp**. Allows force to stabilize (not in default config, added by tool) |

### Hardware Limits

Located in `config_default.json` under `servo.dynamixel_settings`:

| Parameter | Default | Max | Notes |
|-----------|---------|-----|-------|
| `current_limit` | 1120 units | 1600 units | **Hardware current limit**. 1120 = 3.76A (70% of max). Force percentages scale from this |

## Understanding Force Multipliers

The gripper has an internal spring that creates a force multiplier effect:

**MOVING State (fighting spring)**:
- Commanded: 17% × 1120 = 190 units = 638mA
- Actual: ~640mA × 3.4 = **~2176mA peak** when closing
- This is normal behavior, not a malfunction

**GRASPING State (at equilibrium)**:
- Commanded: 10% × 1120 = 112 units = 376mA
- Actual: ~110mA (1.0x multiplier at equilibrium)
- Much lower thermal load

## Recommended Force Profiles

### Conservative (Default)
**Best for**: Long operation times, thermal safety, light objects
```json
{
  "moving_force_pct": 17,
  "grasping_force_pct": 10,
  "idle_force_pct": 10
}
```
- Thermal safe for continuous operation
- Suitable for objects <500g
- Temperature stays <50°C

### Moderate
**Best for**: Medium objects, balanced performance
```json
{
  "moving_force_pct": 30,
  "grasping_force_pct": 20,
  "idle_force_pct": 10
}
```
- Good grip strength for 500-1000g objects
- Monitor temperature (may reach 55-60°C)
- Allow 5-10s rest between grasps

### Aggressive
**Best for**: Heavy objects, maximum grip strength
```json
{
  "moving_force_pct": 50,
  "grasping_force_pct": 35,
  "idle_force_pct": 10
}
```
- Strong grip for objects >1000g
- **Requires thermal monitoring**
- Temperature may reach 65-70°C
- Allow 15-30s rest between grasps
- Not suitable for continuous operation

### Maximum (Testing Only)
**Best for**: Short duration testing, maximum force evaluation
```json
{
  "moving_force_pct": 80,
  "grasping_force_pct": 50,
  "idle_force_pct": 10
}
```
- ⚠️ **High thermal load** - monitor closely
- Temperature will reach 70-80°C quickly
- Use only for <5s grasp duration
- Require 30-60s cooling between grasps
- Risk of thermal shutdown at 75°C

## Using the Force Optimization Tool

### Interactive Mode

```bash
cd ~/CascadeProjects/unitree-dex1-ezgripper-driver
python3 force_optimization_tool.py --side left
```

**Menu Options**:
1. **Run single grasp test** - Test current settings with one grasp/release cycle
2. **Run continuous test** - Endurance testing with multiple cycles
3. **Adjust force settings** - Change moving/grasping/idle forces
4. **Adjust timing settings** - Change settle time, hold duration, detection thresholds
5. **View current settings** - Display active configuration
6. **View test summary** - Statistics from all tests
7. **Save results** - Export results to JSON
8. **Exit**

### Automated Testing

```bash
# Run 10 cycles with default settings
python3 force_optimization_tool.py --side left --auto

# Run 20 cycles
python3 force_optimization_tool.py --side left --auto --cycles 20

# Test right gripper
python3 force_optimization_tool.py --side right --dev /dev/ttyUSB1 --auto
```

## Testing Procedure

### Step 1: Baseline Test

Start with conservative settings to establish baseline:

```bash
python3 force_optimization_tool.py --side left
```

1. Select option 5 to view current settings
2. Select option 1 to run single grasp test
3. Note the metrics:
   - Time to contact
   - Max current
   - Peak temperature
   - Grasp stability

### Step 2: Incremental Force Increase

Gradually increase forces while monitoring thermal response:

1. Select option 3 (Adjust force settings)
2. Increase `moving_force_pct` by 10-15%
3. Increase `grasping_force_pct` by 5-10%
4. Run single test (option 1)
5. Check temperature and current
6. If temperature <60°C, repeat from step 2
7. If temperature >60°C, reduce forces by 5%

### Step 3: Endurance Testing

Test sustained operation at selected force level:

1. Select option 2 (Run continuous test)
2. Enter 10 cycles
3. Enter 5.0s rest time
4. Monitor temperature trends
5. If temperature rises >65°C, increase rest time or reduce forces

### Step 4: Optimize Timing

Fine-tune detection and settling parameters:

1. Select option 4 (Adjust timing settings)
2. Adjust `consecutive_samples` (2-4 recommended)
3. Adjust `stall_tolerance_pct` (1.0-2.0% recommended)
4. Add `contact_settle_time_ms` if needed (0-100ms)
5. Test with option 1

### Step 5: Save Configuration

1. Select option 7 to save results
2. Review JSON output for best performing settings
3. Update `config_default.json` with optimized values

## Monitoring Metrics

### Current (mA)
- **Normal**: 100-800mA during closing
- **Warning**: >1500mA sustained
- **Critical**: >2500mA (approaching hardware limit)

### Temperature (°C)
- **Safe**: <55°C (continuous operation)
- **Warning**: 55-65°C (monitor closely, reduce duty cycle)
- **Advisory**: 65-70°C (reduce forces or increase rest time)
- **Critical**: >70°C (reduce forces immediately)
- **Shutdown**: 75°C (automatic thermal protection)

### Grasp Stability
- **Stable**: Position change <1% during hold
- **Marginal**: Position change 1-3% (may need more force)
- **Unstable**: Position change >3% (increase grasping force)

### Time to Contact
- **Fast**: <0.5s (high moving force)
- **Normal**: 0.5-1.5s (moderate force)
- **Slow**: >1.5s (low force, may need increase)

## Thermal Management

### Cooling Strategies

1. **Duty Cycle**: Limit grasp duration, add rest periods
2. **Force Reduction**: Lower grasping force after initial contact
3. **Ambient Cooling**: Ensure adequate airflow around servo
4. **Thermal Monitoring**: Track temperature trends over time

### Recommended Duty Cycles

| Force Level | Grasp Duration | Rest Time | Duty Cycle |
|-------------|----------------|-----------|------------|
| Conservative (17/10%) | Continuous | None | 100% |
| Moderate (30/20%) | 10s | 5s | 67% |
| Aggressive (50/35%) | 5s | 15s | 25% |
| Maximum (80/50%) | 3s | 30s | 9% |

## Troubleshooting

### Problem: Grasp too weak, objects slip

**Solutions**:
1. Increase `grasping_force_pct` by 5-10%
2. Increase `moving_force_pct` for stronger initial contact
3. Decrease `stall_tolerance_pct` for earlier contact detection
4. Add `contact_settle_time_ms` (50-100ms) to allow force buildup

### Problem: Temperature rises too quickly

**Solutions**:
1. Decrease `grasping_force_pct` by 5-10%
2. Reduce grasp hold duration
3. Increase rest time between grasps
4. Check for mechanical binding or obstruction

### Problem: Contact detection unreliable

**Solutions**:
1. Adjust `consecutive_samples_required` (try 2-4)
2. Adjust `stall_tolerance_pct` (try 1.0-3.0%)
3. Increase `moving_force_pct` for clearer contact signal
4. Check for mechanical issues (spring tension, alignment)

### Problem: Servo overload (Error 128)

**Solutions**:
1. Immediately reduce all force settings by 20-30%
2. Check `current_limit` in config (should be ≤1120)
3. Verify no mechanical binding
4. Restart driver to clear error state

## Example Testing Session

```
$ python3 force_optimization_tool.py --side left

Options:
  1. Run single grasp test
  ...

Select option (1-8): 3

Current Force Settings:
  Moving Force: 17.0%
  Grasping Force: 10.0%
  Idle Force: 10.0%

Moving force % [17.0]: 30
Grasping force % [10.0]: 20
Idle force % [10.0]: 10

📝 Updated Force Profile:
   Moving: 30.0%
   Grasping: 20.0%
   Idle: 10.0%

Select option (1-8): 1

🧪 Starting Grasp Test
   Target Position: 0.0%
   Moving Force: 30.0%
   Grasping Force: 20.0%

Phase 1: Closing to 0.0%...
   State: moving   | Pos:  45.2% | Current:  520mA | Temp: 42.3°C
   State: moving   | Pos:  32.1% | Current:  680mA | Temp: 43.1°C
   State: moving   | Pos:  18.5% | Current:  720mA | Temp: 44.2°C
   State: moving   | Pos:   5.2% | Current:  750mA | Temp: 45.5°C

✅ CONTACT DETECTED at 2.3% (time: 0.85s)

Phase 2: Holding grasp for 5.0s...
   Hold: 1.0s | Pos:   2.3% | Current:  180mA | Temp: 46.2°C
   Hold: 2.0s | Pos:   2.3% | Current:  175mA | Temp: 47.1°C
   Hold: 3.0s | Pos:   2.3% | Current:  172mA | Temp: 47.8°C
   Hold: 4.0s | Pos:   2.3% | Current:  170mA | Temp: 48.4°C
   Hold: 5.0s | Pos:   2.3% | Current:  168mA | Temp: 48.9°C

✅ Grasp hold complete

📊 Test Results Summary
============================================================
Contact Detected:    ✅ YES
Grasp Stable:        ✅ YES
Time to Contact:     0.85s
Max Current:         750mA
Avg Current:         285mA
Peak Temperature:    48.9°C
Final Position:      2.3%
Thermal Warning:     ✅ NO
============================================================
```

## Applying Optimized Settings

After finding optimal settings through testing:

1. Edit `config_default.json`:
```json
"force_management": {
  "moving_force_pct": 30,      // Your optimized value
  "grasping_force_pct": 20,    // Your optimized value
  "idle_force_pct": 10
}
```

2. Restart the driver:
```bash
pkill -9 -f ezgripper_dds_driver
python3 ezgripper_dds_driver.py --side left
```

3. Verify settings are applied in driver logs

## Safety Guidelines

⚠️ **Always monitor temperature during testing**

⚠️ **Start with conservative settings and increase gradually**

⚠️ **Never exceed 75°C - automatic shutdown will occur**

⚠️ **Allow adequate cooling time between high-force tests**

⚠️ **Test with actual objects before deploying to production**

## Quick Reference

**For stronger grasps**: Increase `moving_force_pct` and `grasping_force_pct`

**For thermal safety**: Decrease forces, increase rest time

**For faster contact**: Increase `moving_force_pct`, decrease `consecutive_samples`

**For more reliable detection**: Increase `consecutive_samples`, adjust `stall_tolerance_pct`

**For continuous operation**: Keep forces ≤30/20%, monitor temperature trends
