# DDS Driver Class Structure Specification

## Problem Statement
The `ezgripper_dds_driver.py` file contains three methods that are incorrectly defined at module level instead of being class methods of `CorrectedEZGripperDriver`:
- `state_loop` (lines 782-805)
- `run` (lines 807-878) 
- `shutdown` (appears to be missing or misplaced)

These methods use `self` and are intended to be instance methods but are not indented as part of the class.

## Current Structure Analysis

### Class: CorrectedEZGripperDriver
- **Location**: Lines 155-780
- **Last method**: `_handle_communication_error` (lines 767-780)
- **Issue**: Class ends at line 780, but methods that should be part of it are defined at lines 782+

### Module-level functions that should be class methods:
1. **state_loop** (lines 782-805)
   - Uses `self`: YES
   - Purpose: State thread that publishes predicted position at 200 Hz
   - Should be: Instance method of CorrectedEZGripperDriver

2. **run** (lines 807-878)
   - Uses `self`: YES
   - Purpose: Start multi-threaded driver with control and state threads
   - Should be: Instance method of CorrectedEZGripperDriver

3. **shutdown** (location TBD)
   - Uses `self`: YES (expected)
   - Purpose: Clean shutdown of hardware
   - Should be: Instance method of CorrectedEZGripperDriver

### Module-level functions that should remain at module level:
1. **discover_ezgripper_devices** (lines 45-59) - Utility function
2. **verify_device_mapping** (lines 62-92) - Utility function
3. **get_device_config** (lines 95-152) - Utility function
4. **main** (lines 881-939) - Entry point

## Solution Specification

### Objective
Move `state_loop`, `run`, and `shutdown` methods inside the `CorrectedEZGripperDriver` class with proper indentation.

### Requirements

1. **Indentation Rules**:
   - Class methods must have 4 spaces base indentation (1 level)
   - Method bodies must have 8 spaces indentation (2 levels)
   - Nested blocks add 4 spaces per level

2. **Method Placement**:
   - Insert methods after the last existing method (`_handle_communication_error`)
   - Maintain method order: `state_loop`, `run`, `shutdown`
   - Preserve all existing code logic

3. **Validation**:
   - File must parse without syntax errors
   - AST analysis must show all three methods as part of CorrectedEZGripperDriver
   - Driver instance must have `run()` and `shutdown()` attributes

## Implementation Plan

### Step 1: Identify exact line ranges
- Find exact start/end lines for each method
- Identify any methods between line 780 and 782

### Step 2: Calculate indentation changes
- Method definition: Add 4 spaces (e.g., `def state_loop(self):` → `    def state_loop(self):`)
- Method body: Add 4 spaces to all existing indentation
  - Lines with 0 spaces → 8 spaces
  - Lines with 4 spaces → 8 spaces (if already indented)
  - Lines with 8 spaces → 12 spaces (nested blocks)
  - Empty lines: preserve as-is

### Step 3: Apply changes
- Process file line by line
- Apply indentation rules based on line number ranges
- Preserve blank lines and comments

### Step 4: Verify
- Parse with ast.parse() to ensure no syntax errors
- Check that methods are in class using AST analysis
- Test driver instantiation and method access

## Expected Output

After fix, AST analysis should show:
```
Class: CorrectedEZGripperDriver
  Methods:
    - __init__
    - _initialize_hardware
    - ... (existing methods)
    - _handle_communication_error
    - state_loop  ← ADDED
    - run         ← ADDED
    - shutdown    ← ADDED
```

Module-level functions should only be:
```
- discover_ezgripper_devices
- verify_device_mapping
- get_device_config
- main
```

## Success Criteria
1. ✅ File parses without syntax errors
2. ✅ All three methods appear in CorrectedEZGripperDriver class via AST
3. ✅ Driver instance has `run()` and `shutdown()` methods
4. ✅ DDS driver starts without AttributeError
5. ✅ All existing functionality preserved
