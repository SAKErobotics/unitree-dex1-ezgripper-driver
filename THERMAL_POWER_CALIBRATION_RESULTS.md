# Thermal Power Calibration Results

**Date**: February 11, 2026  
**Gripper**: Left  
**Test Method**: Thermal heating rate measurement

## Executive Summary

Power consumption scales **non-linearly** with grasping force. Doubling the force more than doubles the power consumption. This has critical implications for battery life and thermal management.

## Test Methodology

### Approach
Measure power consumption via thermal heating rate:
1. Close gripper from 30% → 0% (tip-to-tip contact)
2. Hold at 0% with specified grasping force
3. Monitor temperature continuously
4. Record wall time to achieve 5°C temperature rise
5. Calculate heating rate (°C/second)
6. Heating rate is proportional to power consumption

### Test Configuration
- **Base force**: 15%
- **Force levels**: 15%, 30%, 45% (1x, 2x, 3x multipliers)
- **Temperature rise target**: 5°C per test
- **Cooldown between tests**: 60 seconds
- **Position**: Static hold at 0% (tip-to-tip contact)

### Why This Works
- Servo draws current to maintain position against spring force
- Current draw generates heat (I²R losses + motor inefficiency)
- Higher force → higher current → faster heating
- Heating rate directly correlates with power consumption

## Results

### Raw Data

| Force | Multiplier | Wall Time (s) | Heating Rate (°C/s) | Relative Power |
|-------|-----------|---------------|---------------------|----------------|
| 15%   | 1x        | 335.3         | 0.0149              | 1.00x          |
| 30%   | 2x        | 153.2         | 0.0326              | 2.19x          |
| 45%   | 3x        | 77.3          | 0.0647              | 4.34x          |

### Key Findings

**Non-Linear Power Scaling:**
- 2x force → 2.19x power (9.5% higher than linear)
- 3x force → 4.34x power (44.7% higher than linear)

**Power Relationship:**
```
Power ∝ Force^1.5 (approximately)
```

This suggests power scales with force raised to approximately the 1.5 power, not linearly.

### Implications

**Battery Life:**
- Using 45% force drains battery **4.3x faster** than 15% force
- Using 30% force drains battery **2.2x faster** than 15% force
- For maximum battery life, use minimum effective grasping force

**Thermal Management:**
- Higher forces generate heat much faster than expected
- 45% force heats servo 4.3x faster than 15% force
- Thermal limits will be reached much sooner at high forces

**Optimal Force Selection:**
- Start with lowest force that maintains grasp
- Only increase if object slips
- Avoid over-grasping (wastes power and generates excess heat)

## Comparison to Expected Linear Scaling

| Force | Expected Power (linear) | Actual Power | Error |
|-------|------------------------|--------------|-------|
| 15%   | 1.00x                  | 1.00x        | 0%    |
| 30%   | 2.00x                  | 2.19x        | +9.5% |
| 45%   | 3.00x                  | 4.34x        | +44.7%|

## Physical Explanation

The non-linear scaling likely comes from:

1. **Spring force multiplier**: The gripper uses a spring mechanism that amplifies force non-linearly
2. **Motor efficiency**: Motor efficiency decreases at higher currents
3. **I²R losses**: Resistive heating scales with current squared
4. **Friction**: Static friction increases with normal force

## Recommendations

### For General Grasping
- Start with 15-20% grasping force
- Only increase if object slips during manipulation
- Monitor temperature during extended grasps

### For Long Battery Life
- Use minimum effective force (15-20%)
- Avoid sustained high-force grasps
- Consider releasing and re-grasping rather than holding continuously

### For High-Force Applications
- Limit duration of high-force grasps
- Implement thermal monitoring and backoff
- Allow cooldown periods between high-force operations

## Next Steps

### Contact Characterization
Need to characterize the **contact/impact** phase separately:
- Power during rapid closing to contact
- Current spike at contact detection
- Transition from moving → contact → grasping states

### Proposed Contact Test
1. Rapid close from 30% → 0% at various forces
2. Measure current draw during movement
3. Detect contact point (position stagnation)
4. Measure contact impact current spike
5. Characterize transition to static grasp

This will complete the power profile for the full grasp cycle:
- **Moving**: 30% → contact position
- **Contact**: Impact and detection
- **Grasping**: Static hold at contact

## Test Files

- **Summary**: `thermal_cal_left_1770860824_summary.json`
- **Detailed results**: `thermal_cal_left_1770860824_results.csv`
- **Raw measurements**: `thermal_cal_left_1770860824_points.csv`
- **Test script**: `simple_power_calibration.py`

## Conclusion

The thermal calibration successfully established that **power consumption scales non-linearly with grasping force**, with a relationship closer to Force^1.5 than linear. This critical finding means that small reductions in grasping force can yield significant improvements in battery life and thermal performance.

For optimal gripper operation, use the minimum force necessary to maintain a stable grasp, as power consumption increases dramatically with force.
