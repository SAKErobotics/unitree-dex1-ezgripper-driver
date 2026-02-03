# Smart Grasp Algorithm

## Overview

The Smart Grasp algorithm provides sophisticated force management during grasping operations with temperature-aware holding. This is the **default production algorithm** for the EZGripper.

## Algorithm Phases

### 1. CLOSING Phase
**Goal:** Fast approach to object

- **Force:** 100% (configurable `max_force`)
- **Detection:** 5-cycle moving window filter monitors:
  - Current spike (>150mA threshold)
  - Position stagnation (<2 units movement)
- **Transition:** When contact detected → GRASPING phase

### 2. GRASPING Phase
**Goal:** Rapid force reduction as grasp wraps around object

- **Force Curve:** Exponential decay from max → grasp_set
  - Formula: `F(t) = grasp_set + (max - grasp_set) × e^(-3t)`
  - Reaches 50% in ~0.5 seconds
  - Accelerates if position stabilizes early
  
- **Monitoring:**
  - 5-cycle filtered position change
  - Continuous force adjustment
  - Fast reaction to position stabilization

- **Transition:** When position change < 0.5 units → GRASP_SET phase

### 3. GRASP_SET Phase
**Goal:** Confirm grasp is stable

- **Force:** 50% (configurable `grasp_set_force`)
- **Duration:** Immediate transition
- **Transition:** → HOLDING phase

### 4. HOLDING Phase
**Goal:** Maintain grasp with temperature awareness

- **Base Force:** 30% (configurable `holding_force_low`)
- **Dynamic Adjustment:**
  - **Normal operation:** 30% force
  - **Slip detected:** Increase to 50% (`holding_force_mid`)
  - **Temperature warning (>60°C):** Limit to 30%
  - **Temperature critical (>70°C):** Reduce to 21% (30% × 0.7)

- **Slip Detection:**
  - Position change > 3 units over 5-cycle window
  - Automatic force increase if temperature allows

- **Temperature Management:**
  - Continuous monitoring
  - Gradual force changes (30% step per cycle)
  - Prevents overheating while maintaining grip

## Configuration Parameters

```python
SmartGraspReaction(
    max_force=100,              # Initial closing force (%)
    grasp_set_force=50,         # Force when grasp is set (%)
    holding_force_low=30,       # Low holding force (%)
    holding_force_mid=50,       # Mid holding force (%)
    temp_warning=60,            # Temperature warning (°C)
    temp_critical=70            # Temperature critical (°C)
)
```

## Force Curve Visualization

```
Time(s) | Force(%) | Visual
--------|----------|---------------------------------------
0.000   | 100.0%   | ████████████████████████████████████████████████
0.050   |  92.1%   | ██████████████████████████████████████████████
0.100   |  85.5%   | ███████████████████████████████████████████
0.150   |  79.9%   | ████████████████████████████████████████
0.200   |  75.2%   | ██████████████████████████████████████
0.250   |  71.1%   | ████████████████████████████████████
0.300   |  67.6%   | ██████████████████████████████████
0.350   |  64.5%   | ████████████████████████████████
0.400   |  61.8%   | ███████████████████████████████
0.450   |  59.4%   | ██████████████████████████████
0.500   |  57.3%   | █████████████████████████████
0.550   |  55.4%   | ████████████████████████████
0.600   |  53.7%   | ███████████████████████████
0.650   |  52.3%   | ██████████████████████████
0.700   |  51.0%   | ██████████████████████████
0.750   |  50.0%   | █████████████████████████
```

## Usage Example

```python
from libezgripper.collision_reactions import SmartGraspReaction

# Create smart grasp reaction
smart_grasp = SmartGraspReaction(
    max_force=100,
    grasp_set_force=50,
    holding_force_low=30,
    holding_force_mid=50
)

# Enable collision monitoring
gripper.enable_collision_monitoring(smart_grasp)

# Command close - algorithm handles the rest
gripper.goto_position(0, 100)

# In control loop
while True:
    result = gripper.update_main_loop()
    
    if result['reaction_result']:
        state = result['reaction_result']['grasp_state']
        force = result['reaction_result']['current_force']
        print(f"State: {state}, Force: {force:.1f}%")
    
    time.sleep(0.033)  # 30Hz
```

## Benefits

1. **Fast Approach:** 100% force for quick closing
2. **Gentle Contact:** Rapid force reduction prevents damage
3. **Adaptive Holding:** Adjusts to object properties
4. **Temperature Safe:** Prevents overheating
5. **Slip Recovery:** Automatically increases force if object slips
6. **Smooth Control:** 5-cycle filter eliminates noise

## State Transitions

```
CLOSING
   ↓ (contact detected)
GRASPING
   ↓ (position stable)
GRASP_SET
   ↓ (immediate)
HOLDING
   ↓ (continuous monitoring)
   ↺ (adjust force based on temp/slip)
```

## Monitoring Data

The algorithm provides detailed monitoring:

```python
stats = smart_grasp.controller.get_statistics()

# Available statistics:
stats['state']                    # Current state
stats['current_force']            # Current force (%)
stats['time_since_contact']       # Time since contact (s)
stats['time_since_grasp_set']     # Time in holding (s)
stats['grasp_duration']           # Time to complete grasp (s)
stats['avg_temperature']          # Average temperature (°C)
stats['max_temperature']          # Peak temperature (°C)
```

## Testing

```bash
# Test with hardware
python3 test_smart_grasp.py

# Visualize force curve only
python3 test_smart_grasp.py --visualize
```

## Implementation Details

### Moving Window Filter
- Window size: 5 cycles (~165ms at 30Hz)
- Filters: position and current
- Provides: filtered values and position change

### Force Calculation
- Exponential decay: `F(t) = F_final + (F_initial - F_final) × e^(-kt)`
- Decay rate: k = 3.0 (fast initial reduction)
- Position-aware: Accelerates if position stable

### Temperature Response
- **Normal (<60°C):** Full force range available
- **Warning (60-70°C):** Limited to low force
- **Critical (>70°C):** Force reduced by 30%
- **Smooth transitions:** 30% step per cycle

## Future Enhancements

- [ ] Machine learning for object-specific force profiles
- [ ] Vibration detection for slip prediction
- [ ] Multi-object grasp strategies
- [ ] Energy optimization algorithms
