# Protocol 2 Migration: Detailed Code Update Plan

## Overview

This document details every file that needs updating for Protocol 2 migration, with specific changes required for each file.

---

## Phase 1: Core Communication Layer

### 1. `libezgripper/lib_robotis.py` - **CRITICAL, HIGH COMPLEXITY**

**Current state**: Implements Protocol 1 packet structure and communication

**Required changes**:

#### A. Packet Structure Updates

**Protocol 1 packet format:**
```
[0xFF, 0xFF, ID, LENGTH, INSTRUCTION, PARAM1, PARAM2, ..., CHECKSUM]
```

**Protocol 2 packet format:**
```
[0xFF, 0xFF, 0xFD, 0x00, ID, LENGTH_L, LENGTH_H, INSTRUCTION, PARAM1, PARAM2, ..., CRC_L, CRC_H]
```

**Changes needed:**
- Update header: `[0xFF, 0xFF]` → `[0xFF, 0xFF, 0xFD, 0x00]`
- Change checksum to CRC-16
- Update length calculation (includes instruction + parameters + CRC)
- Add reserved byte (0x00)

#### B. Instruction Set Updates

**Protocol 1 instructions:**
```python
PING = 0x01
READ = 0x02
WRITE = 0x03
REG_WRITE = 0x04
ACTION = 0x05
RESET = 0x06
SYNC_WRITE = 0x83
```

**Protocol 2 instructions (ADD NEW):**
```python
PING = 0x01          # Same
READ = 0x02          # Same
WRITE = 0x03         # Same
REG_WRITE = 0x04     # Same
ACTION = 0x05        # Same
FACTORY_RESET = 0x06 # Changed from RESET
REBOOT = 0x08        # NEW
CLEAR = 0x10         # NEW
STATUS = 0x55        # NEW
SYNC_READ = 0x82     # NEW - KEY FEATURE
SYNC_WRITE = 0x83    # Same
BULK_READ = 0x92     # NEW - KEY FEATURE
BULK_WRITE = 0x93    # NEW - KEY FEATURE
```

#### C. Methods to Add

```python
def bulk_read(self, register_list):
    """
    Read multiple registers in one transaction
    
    Args:
        register_list: [(addr1, length1), (addr2, length2), ...]
    
    Returns:
        List of data arrays
    """
    # Build BULK_READ packet
    # Send and parse response
    pass

def bulk_write(self, register_list):
    """
    Write multiple registers in one transaction
    
    Args:
        register_list: [(addr1, data1), (addr2, data2), ...]
    """
    # Build BULK_WRITE packet
    # Send
    pass

def sync_read(self, start_addr, length):
    """
    Read consecutive registers in one transaction
    
    Args:
        start_addr: Starting register address
        length: Number of bytes to read
    
    Returns:
        Data array
    """
    # Build SYNC_READ packet
    # Send and parse response
    pass
```

#### D. CRC-16 Implementation

```python
def calculate_crc(self, data):
    """
    Calculate CRC-16 for Protocol 2
    
    Uses CRC-16-IBM (polynomial 0x8005)
    """
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc = crc >> 1
    return crc & 0xFFFF
```

#### E. Register Address Constants (ADD NEW)

```python
# Protocol 2 Register Addresses
class Protocol2Registers:
    # EEPROM Area
    MODEL_NUMBER = 0
    MODEL_INFORMATION = 2
    FIRMWARE_VERSION = 6
    ID = 7
    BAUD_RATE = 8
    RETURN_DELAY_TIME = 9
    DRIVE_MODE = 10
    OPERATING_MODE = 11  # Torque mode enable
    SECONDARY_ID = 12
    PROTOCOL_TYPE = 13
    
    # RAM Area
    TORQUE_ENABLE = 64
    LED_RED = 65
    STATUS_RETURN_LEVEL = 68
    REGISTERED_INSTRUCTION = 69
    HARDWARE_ERROR_STATUS = 70
    VELOCITY_I_GAIN = 76
    VELOCITY_P_GAIN = 78
    POSITION_D_GAIN = 80
    POSITION_I_GAIN = 82
    POSITION_P_GAIN = 84
    GOAL_PWM = 100
    GOAL_TORQUE = 102
    GOAL_VELOCITY = 104
    GOAL_POSITION = 116
    REALTIME_TICK = 120
    MOVING = 122
    MOVING_STATUS = 123
    PRESENT_PWM = 124
    PRESENT_LOAD = 126
    PRESENT_CURRENT = 126  # Same as load in Protocol 2
    PRESENT_VELOCITY = 128
    PRESENT_POSITION = 132
    VELOCITY_TRAJECTORY = 136
    POSITION_TRAJECTORY = 140
    PRESENT_INPUT_VOLTAGE = 144
    PRESENT_TEMPERATURE = 146
```

#### F. Methods to Update

**Every method using register addresses needs updating:**

```python
# OLD (Protocol 1)
def read_encoder(self):
    data = self.read_address(0x24, 2)  # Address 36
    
# NEW (Protocol 2)
def read_encoder(self):
    data = self.read_address(132, 2)  # Address 132

# OLD (Protocol 1)
def enable_torque(self):
    return self.write_address(0x18, [1])  # Address 24
    
# NEW (Protocol 2)
def enable_torque(self):
    return self.write_address(64, [1])  # Address 64
```

**All methods requiring updates:**
- `init_cont_turn()` - addr 8 → 52
- `kill_cont_turn()` - addr 8 → 52
- `is_moving()` - addr 46 → 122
- `read_voltage()` - addr 42 → 144
- `read_temperature()` - addr 43 → 146
- `read_load()` - addr 40 → 126
- `read_present_speed()` - addr 38 → 128
- `read_encoder()` - addr 36 → 132
- `enable_torque()` - addr 24 → 64
- `disable_torque()` - addr 24 → 64
- `set_angvel()` - addr 32 → 104
- `write_id()` - addr 3 → 7
- `write_baudrate()` - addr 4 → 8

**Estimated effort**: 2-3 days

---

## Phase 2: Gripper Control Layer

### 2. `libezgripper/ezgripper_base.py` - **MEDIUM COMPLEXITY**

**Current state**: High-level gripper control using Protocol 1 addresses

**Required changes**:

#### A. Torque Mode Control

```python
# OLD (Protocol 1)
def set_torque_mode(servo, val):
    if val:
        servo.write_address(70, [1])  # Torque Control Mode Enable
    else:
        servo.write_address(70, [0])

# NEW (Protocol 2)
def set_torque_mode(servo, val):
    # Protocol 2 uses Operating Mode register
    if val:
        servo.write_address(11, [0])  # 0 = Current (Torque) Control Mode
    else:
        servo.write_address(11, [3])  # 3 = Position Control Mode
```

**Note**: Protocol 2 has different operating modes:
- 0: Current (Torque) Control
- 1: Velocity Control
- 3: Position Control (default)
- 4: Extended Position Control
- 5: Current-based Position Control
- 16: PWM Control

#### B. Position/Torque Register Updates

```python
# Update all direct register writes
# Goal Position: 30 → 116
# Torque Limit: 34 → 38 (but different meaning in Protocol 2)
# Goal Torque: 71 → 102
```

**Estimated effort**: 1 day

---

## Phase 3: Application Layer

### 3. `hardware_controller.py` - **HIGH IMPACT, MEDIUM COMPLEXITY**

**Current state**: Main control logic with resistance detection

**Required changes**:

#### A. Current Reading Update

```python
# OLD (Protocol 1)
def _read_current(self) -> float:
    current_raw = self.gripper.servos[0].read_word(68)
    current_ma = int(4.5 * (current_raw - 2048))
    return abs(current_ma)

# NEW (Protocol 2)
def _read_current(self) -> float:
    # Protocol 2: Current at address 126
    # Formula may be different - NEEDS VERIFICATION
    current_raw = self.gripper.servos[0].read_word(126)
    # TODO: Verify Protocol 2 current formula
    current_ma = int(??? * (current_raw - ???))
    return abs(current_ma)
```

**CRITICAL**: Protocol 2 current formula needs research/verification

#### B. Bulk Read Implementation (NEW CAPABILITY)

```python
def read_servo_state(self) -> dict:
    """
    Read all servo state in one bulk read transaction
    
    Returns:
        dict with current, position, load, error
    """
    # Bulk read: Current@126, Position@132, Load@126, Error@70
    data = self.gripper.servos[0].bulk_read([
        (126, 2),  # Current (2 bytes)
        (132, 4),  # Position (4 bytes)
        (126, 2),  # Load (2 bytes, same as current)
        (70, 1),   # Hardware Error Status (1 byte)
    ])
    
    return {
        'current': self._parse_current(data[0]),
        'position': self._parse_position(data[1]),
        'load': self._parse_load(data[2]),
        'error': data[3],
        'timestamp': time.time()
    }
```

#### C. Control Loop Update

```python
# OLD (Protocol 1) - Multiple transactions
def execute_command(self, position_pct, effort_pct):
    current = self._read_current()              # Transaction 1
    # ... logic ...
    servo.write_word(34, torque_limit)          # Transaction 2
    servo.write_word(30, servo_pos)             # Transaction 3

# NEW (Protocol 2) - Bulk operations
def execute_command(self, position_pct, effort_pct):
    # Single bulk read for all state
    state = self.read_servo_state()             # Transaction 1 (gets all)
    
    # ... logic using state.current, state.position, state.load ...
    
    # Single bulk write for commands
    servo.bulk_write([
        (38, torque_limit),                     # Torque Limit
        (116, servo_pos),                       # Goal Position
    ])                                          # Transaction 2
```

#### D. Multi-Sensor Resistance Detection (NEW)

```python
def detect_resistance_advanced(self, state: dict) -> bool:
    """
    Enhanced resistance detection using multiple sensors
    
    Args:
        state: Dict from read_servo_state() with current, load, position
    
    Returns:
        True if resistance detected
    """
    # Current-based detection
    current_high = state['current'] > self.current_threshold
    
    # Load-based detection (independent sensor)
    load_high = state['load'] > self.load_threshold
    
    # Position-based detection (stuck at position)
    position_error = abs(state['position'] - self.target_position)
    position_stuck = position_error > self.stuck_threshold
    
    # Require 2 out of 3 sensors to agree
    detections = sum([current_high, load_high, position_stuck])
    
    if detections >= 2:
        self.logger.info(f"Resistance detected: current={current_high}, "
                        f"load={load_high}, stuck={position_stuck}")
        return True
    
    return False
```

**Estimated effort**: 2 days

---

### 4. `clear_servo_error.py` - **LOW COMPLEXITY**

**Required changes**:

```python
# OLD (Protocol 1)
servo.write_address(70, [0])  # Disable torque mode
servo.write_address(24, [0])  # Disable torque enable
servo.write_address(18, [0])  # Clear error

# NEW (Protocol 2)
servo.write_address(11, [3])  # Set to Position Control Mode
servo.write_address(64, [0])  # Disable torque enable
servo.write_address(70, [0])  # Clear hardware error status
```

**Estimated effort**: 0.5 days

---

## Phase 4: Test Files

### 5. Test Files - **LOW COMPLEXITY, HIGH VOLUME**

**All test files need register address updates:**

#### Files requiring updates:
- `test_mode_characterization.py`
- `test_incremental_torque.py`
- `test_movement_current.py`
- `test_simple_positions.py`
- `test_measure_range.py`
- `test_position_mapping.py`
- `test_spring_pullback.py`
- `test_verify_current.py`
- `test_resistance_mapping.py`
- `test_backoff_torque.py`
- `test_gripper.py`

#### Common changes for all test files:

```python
# Register address updates
servo.read_word(36)  → servo.read_word(132)  # Position
servo.read_word(40)  → servo.read_word(126)  # Load
servo.read_word(68)  → servo.read_word(126)  # Current (same as load in P2)
servo.write_word(30, pos) → servo.write_word(116, pos)  # Goal Position
servo.write_word(34, torque) → servo.write_word(38, torque)  # Torque Limit
servo.write_word(71, goal) → servo.write_word(102, goal)  # Goal Torque
servo.write_address(70, [1]) → servo.write_address(11, [0])  # Torque mode
servo.write_address(18, [0]) → servo.write_address(70, [0])  # Clear error
```

#### Current formula updates:

```python
# OLD (Protocol 1)
current_ma = int(4.5 * (current_raw - 2048))

# NEW (Protocol 2)
# TODO: Verify Protocol 2 current formula from documentation
current_ma = int(??? * (current_raw - ???))
```

**Estimated effort**: 2 days (mechanical changes, but many files)

---

## Phase 5: Documentation Updates

### 6. Documentation Files

**Files to update:**
- `DDS_INTERFACE_SPECIFICATION.md` - Update register references
- `README.md` - Note Protocol 2 usage
- `PROTOCOL_MIGRATION_ANALYSIS.md` - Mark as completed
- `PROTOCOL2_BULK_OPERATIONS_ANALYSIS.md` - Add implementation notes

**Estimated effort**: 0.5 days

---

## Critical Research Required

### 1. Protocol 2 Current Formula - **BLOCKING**

**Must verify before implementation:**
- What is the current formula for Protocol 2 register 126?
- Is it the same as Protocol 1 (4.5mA * (value - 2048))?
- Or is it different?

**Source**: MX-64(2.0) e-Manual at emanual.robotis.com

### 2. Protocol 2 Torque Control Behavior

**Must understand:**
- How does Operating Mode (register 11) work?
- Is torque control (mode 0) the same as Protocol 1 torque mode?
- What are the differences in behavior?

### 3. Protocol 2 Bulk Read/Write Packet Format

**Must implement correctly:**
- Exact packet structure for BULK_READ (0x92)
- Exact packet structure for BULK_WRITE (0x93)
- Response parsing for bulk operations

---

## Dependencies & Order of Implementation

### Critical Path:

```
1. Research Protocol 2 specs (BLOCKING)
   ↓
2. Update lib_robotis.py packet structure
   ↓
3. Implement bulk read/write methods
   ↓
4. Update register address constants
   ↓
5. Update ezgripper_base.py
   ↓
6. Update hardware_controller.py
   ↓
7. Update test files
   ↓
8. Run characterization tests
   ↓
9. Recalibrate thresholds
   ↓
10. Validate in xr-teleop
```

### Parallel Work Possible:

- Documentation updates (can happen anytime)
- Test file updates (after lib_robotis.py done)
- clear_servo_error.py (after lib_robotis.py done)

---

## Testing Requirements

### Unit Tests Needed:

1. **Packet structure tests**
   - Verify Protocol 2 packet format
   - Verify CRC-16 calculation
   - Test bulk read/write packet construction

2. **Communication tests**
   - Test single read/write
   - Test bulk read/write
   - Test sync read/write

3. **Register address tests**
   - Verify all register addresses correct
   - Test read/write to each register

### Integration Tests Needed:

1. **Control loop tests**
   - Verify bulk read gets all state
   - Verify bulk write sends all commands
   - Measure control loop timing

2. **Resistance detection tests**
   - Test multi-sensor detection
   - Verify threshold calibration
   - Test false positive rate

3. **Characterization tests**
   - Re-run mode characterization
   - Re-run incremental torque test
   - Re-run movement current test

### Validation Tests:

1. **xr-teleop integration**
   - Test position tracking (should be 10x smoother)
   - Test resistance detection (should be more reliable)
   - Test error recovery (should be faster)

---

## Risk Mitigation

### Risks & Mitigation Strategies:

1. **Risk**: Current formula is different in Protocol 2
   - **Mitigation**: Research thoroughly before implementation
   - **Fallback**: Keep Protocol 1 version until verified

2. **Risk**: Torque mode behavior is different
   - **Mitigation**: Test extensively with characterization tests
   - **Fallback**: Adjust control logic if needed

3. **Risk**: Bulk operations don't work as expected
   - **Mitigation**: Test with simple read/write first
   - **Fallback**: Use individual operations if bulk fails

4. **Risk**: Breaking existing functionality
   - **Mitigation**: Implement in separate branch
   - **Fallback**: Keep Protocol 1 version working

5. **Risk**: Performance doesn't improve as expected
   - **Mitigation**: Benchmark before and after
   - **Fallback**: Optimize implementation

---

## Success Criteria

### Must Have:
- [ ] All register addresses updated correctly
- [ ] Bulk read/write working
- [ ] Current reading accurate
- [ ] Resistance detection working
- [ ] All tests passing

### Should Have:
- [ ] 10x improvement in position update rate
- [ ] Multi-sensor resistance detection
- [ ] Continuous error monitoring
- [ ] Control loop timing improved

### Nice to Have:
- [ ] Adaptive control loop rate
- [ ] Load data in published state
- [ ] Force feedback capability

---

## Estimated Total Effort

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Research Protocol 2 specs | 1 day | None |
| Update lib_robotis.py | 2-3 days | Research |
| Update ezgripper_base.py | 1 day | lib_robotis.py |
| Update hardware_controller.py | 2 days | lib_robotis.py |
| Update clear_servo_error.py | 0.5 days | lib_robotis.py |
| Update test files | 2 days | lib_robotis.py |
| Testing & validation | 2-3 days | All above |
| Documentation | 0.5 days | Anytime |
| **Total** | **11-13 days** | Sequential |

---

## Next Steps (Planning Phase)

1. **Review this plan** with team
2. **Research Protocol 2 specs** - Get MX-64(2.0) documentation
3. **Verify current formula** - Critical for resistance detection
4. **Create implementation branch** - Don't break existing code
5. **Set up testing environment** - Validate each phase
6. **Schedule implementation** - Allocate 2-3 weeks
