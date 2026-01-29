# Dynamixel Protocol 1 to Protocol 2 Migration Analysis

## Current State: Protocol 1.0

The codebase currently uses Dynamixel Protocol 1.0 for MX-64 servo communication.

## Register Address Mapping: Protocol 1 → Protocol 2

Based on code analysis, here are all Protocol 1 register addresses currently used:

### Control Registers

| Register Name | Protocol 1 Addr | Protocol 2 Addr | Usage in Code |
|--------------|----------------|----------------|---------------|
| **ID** | 3 (0x03) | 7 | `lib_robotis.py`: `write_id()` |
| **Baud Rate** | 4 (0x04) | 8 | `lib_robotis.py`: `write_baudrate()` |
| **CCW Angle Limit** | 8 (0x08) | 52 | `lib_robotis.py`: `init_cont_turn()`, `kill_cont_turn()` |
| **Error** | 18 (0x12) | 70 | `clear_servo_error.py`, `hardware_controller.py` |
| **Torque Enable** | 24 (0x18) | 64 | `lib_robotis.py`: `enable_torque()`, `disable_torque()` |
| **Goal Position** | 30 (0x1E) | 116 | **CRITICAL** - Used everywhere for position commands |
| **Moving Speed** | 32 (0x20) | 104 | `lib_robotis.py`: `set_angvel()` |
| **Torque Limit** | 34 (0x22) | 38 | **CRITICAL** - Used for effort control |
| **Present Position** | 36 (0x24) | 132 | **CRITICAL** - Used everywhere for position reading |
| **Present Speed** | 38 (0x26) | 128 | `lib_robotis.py`: `read_present_speed()` |
| **Present Load** | 40 (0x28) | 126 | `lib_robotis.py`: `read_load()` |
| **Present Voltage** | 42 (0x2A) | 144 | `lib_robotis.py`: `read_voltage()` |
| **Present Temperature** | 43 (0x2B) | 146 | `lib_robotis.py`: `read_temperature()` |
| **Moving** | 46 (0x2E) | 122 | `lib_robotis.py`: `is_moving()` |
| **Current** | 68 (0x44) | 126 | **CRITICAL** - `hardware_controller.py`: `_read_current()` |
| **Torque Control Mode Enable** | 70 (0x46) | 11 | **CRITICAL** - Used for torque mode switching |
| **Goal Torque** | 71 (0x47) | 102 | **CRITICAL** - Used for torque mode control |

### Files Using Protocol 1 Register Addresses

#### Core Library Files
1. **`libezgripper/lib_robotis.py`**
   - Low-level servo communication
   - Uses addresses: 3, 4, 8, 18, 24, 30, 32, 36, 38, 40, 42, 43, 46
   - Methods: `read_word()`, `write_word()`, `read_address()`, `write_address()`

2. **`libezgripper/ezgripper_base.py`**
   - High-level gripper control
   - Uses register 70 (torque mode enable)
   - Method: `set_torque_mode()`

#### Application Files
3. **`hardware_controller.py`**
   - **CRITICAL** - Main control logic
   - Uses registers: 18 (error), 68 (current), 70 (torque mode), 71 (goal torque)
   - Method: `_read_current()` - **JUST UPDATED** to use register 68

4. **`clear_servo_error.py`**
   - Error recovery
   - Uses registers: 18 (error), 24 (torque enable), 70 (torque mode)

#### Test Files
5. **`test_mode_characterization.py`**
   - Uses registers: 18, 30, 34, 36, 40, 68, 70, 71
   - Characterization tests for position/torque modes

6. **`test_incremental_torque.py`**
   - Uses registers: 34, 36, 40, 68, 70, 71
   - Torque mode testing

7. **`test_movement_current.py`**
   - Uses registers: 30, 68, 70
   - Movement current testing

## Critical Differences: Protocol 1 vs Protocol 2

### 1. Register Addresses
- **ALL register addresses are different**
- Most critical: Goal Position (30→116), Present Position (36→132), Current (68→126)

### 2. Current Register
- **Protocol 1 (addr 68)**: Formula `I = 4.5mA * (CURRENT - 2048)`
- **Protocol 2 (addr 126)**: Different formula and scaling - **NEEDS VERIFICATION**

### 3. Torque Control Mode
- **Protocol 1**: Separate enable (addr 70) and goal torque (addr 71)
- **Protocol 2**: Different control mechanism - **NEEDS RESEARCH**

### 4. Communication Protocol
- **Protocol 1**: Different packet structure
- **Protocol 2**: Enhanced error detection, sync/bulk read/write

## Migration Impact Assessment

### HIGH IMPACT (Core Functionality)
1. **`libezgripper/lib_robotis.py`**
   - ALL register addresses need updating
   - Packet structure may need changes
   - **Effort: HIGH** - Core communication layer

2. **`hardware_controller.py`**
   - Current reading formula needs verification
   - Torque mode control may work differently
   - **Effort: MEDIUM** - Logic stays same, addresses change

### MEDIUM IMPACT (Application Layer)
3. **`libezgripper/ezgripper_base.py`**
   - Torque mode enable mechanism
   - **Effort: LOW** - Single register change

4. **`clear_servo_error.py`**
   - Error register address
   - **Effort: LOW** - Simple address updates

### LOW IMPACT (Test Files)
5. All test files
   - Address updates only
   - **Effort: LOW** - Mechanical changes

## Migration Strategy

### Phase 1: Research & Planning
1. Obtain MX-64 Protocol 2.0 documentation
2. Verify current formula for Protocol 2
3. Understand torque mode differences
4. Document all behavioral changes

### Phase 2: Core Library Update
1. Update `lib_robotis.py` with Protocol 2 packet structure
2. Create address mapping constants
3. Update all register addresses
4. Add Protocol 2 specific features (sync read/write)

### Phase 3: Application Layer Update
1. Update `hardware_controller.py` current reading
2. Update torque mode control
3. Update error handling

### Phase 4: Testing
1. Update all test files
2. Run characterization tests
3. Verify resistance detection
4. Validate torque mode behavior

## Estimated Effort

- **Core Library (lib_robotis.py)**: 2-3 days
- **Application Layer**: 1 day
- **Testing & Validation**: 2-3 days
- **Total**: 5-7 days

## Risks

1. **Current formula may be different** - Resistance detection threshold will need recalibration
2. **Torque mode behavior may differ** - Control logic may need adjustment
3. **Communication timing** - Protocol 2 may have different timing requirements
4. **Backward compatibility** - Need to support both protocols or fully migrate

## Recommendation

**DO NOT MIGRATE** unless there is a specific reason to use Protocol 2 features:
- Sync/bulk read/write for multiple servos
- Better error detection
- Higher communication speed

**Current Protocol 1 implementation works correctly** with the updated current formula. Migration would be significant effort with minimal benefit for single-servo control.

## If Migration is Required

1. Create a Protocol 2 branch
2. Implement Protocol 2 in `lib_robotis.py` first
3. Test thoroughly with characterization tests
4. Update application layer incrementally
5. Maintain Protocol 1 version until Protocol 2 is fully validated
