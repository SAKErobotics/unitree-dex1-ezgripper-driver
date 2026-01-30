# Protocol 2 Migration - Implementation TODO

## Status: READY TO IMPLEMENT

This document provides a complete implementation guide for migrating from Dynamixel Protocol 1.0 to Protocol 2.0.

## CRITICAL: Unknown Current Formula

**BLOCKING ISSUE**: Protocol 2 current formula for register 126 is not documented in the MX-64(2.0) e-Manual.

**Temporary Solution**: Use Protocol 1 formula `I = 4.5mA * (CURRENT - 2048)` as starting point, then verify empirically.

**Verification Test**: After migration, run characterization tests and compare current readings with Protocol 1 baseline.

---

## Implementation Checklist

### Phase 1: Core Communication Layer (lib_robotis.py)

#### 1.1 Add Protocol 2 Constants

Add after line 43:

```python
# Protocol 2.0 Instructions
INST_PING = 0x01
INST_READ = 0x02
INST_WRITE = 0x03
INST_REG_WRITE = 0x04
INST_ACTION = 0x05
INST_FACTORY_RESET = 0x06
INST_REBOOT = 0x08
INST_CLEAR = 0x10
INST_STATUS = 0x55
INST_SYNC_READ = 0x82
INST_SYNC_WRITE = 0x83
INST_BULK_READ = 0x92
INST_BULK_WRITE = 0x93

# Protocol 2.0 Register Addresses for MX-64
class P2_Registers:
    # EEPROM
    MODEL_NUMBER = 0
    FIRMWARE_VERSION = 6
    ID = 7
    BAUD_RATE = 8
    RETURN_DELAY_TIME = 9
    DRIVE_MODE = 10
    OPERATING_MODE = 11  # Replaces Torque Control Mode Enable
    PROTOCOL_TYPE = 13
    HOMING_OFFSET = 20
    MOVING_THRESHOLD = 24
    TEMPERATURE_LIMIT = 31
    MAX_VOLTAGE_LIMIT = 32
    MIN_VOLTAGE_LIMIT = 34
    PWM_LIMIT = 36
    CURRENT_LIMIT = 38  # Replaces Torque Limit
    ACCELERATION_LIMIT = 40
    VELOCITY_LIMIT = 44
    MAX_POSITION_LIMIT = 48
    MIN_POSITION_LIMIT = 52
    SHUTDOWN = 63
    
    # RAM
    TORQUE_ENABLE = 64
    LED = 65
    STATUS_RETURN_LEVEL = 68
    REGISTERED_INSTRUCTION = 69
    HARDWARE_ERROR_STATUS = 70  # Replaces Error
    VELOCITY_I_GAIN = 76
    VELOCITY_P_GAIN = 78
    POSITION_D_GAIN = 80
    POSITION_I_GAIN = 82
    POSITION_P_GAIN = 84
    FEEDFORWARD_2ND_GAIN = 88
    FEEDFORWARD_1ST_GAIN = 90
    BUS_WATCHDOG = 98
    GOAL_PWM = 100
    GOAL_CURRENT = 102  # Replaces Goal Torque
    GOAL_VELOCITY = 104
    PROFILE_ACCELERATION = 108
    PROFILE_VELOCITY = 112
    GOAL_POSITION = 116
    REALTIME_TICK = 120
    MOVING = 122
    MOVING_STATUS = 123
    PRESENT_PWM = 124
    PRESENT_CURRENT = 126  # Replaces Current at 68
    PRESENT_VELOCITY = 128
    PRESENT_POSITION = 132
    VELOCITY_TRAJECTORY = 136
    POSITION_TRAJECTORY = 140
    PRESENT_INPUT_VOLTAGE = 144
    PRESENT_TEMPERATURE = 146
```

#### 1.2 Add CRC-16 Calculation

Add after `__calc_checksum()` method (line 276):

```python
def __calc_crc(self, data):
    """
    Calculate CRC-16 for Protocol 2.0
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

#### 1.3 Update send_instruction() for Protocol 2

Replace lines 313-341 with:

```python
def send_instruction(self, instruction, exceptionOnErrorResponse = True):
    ''' send_instruction with Protocol 2.0 packet structure '''
    # Protocol 2.0 packet: [0xFF, 0xFF, 0xFD, 0x00, ID, LEN_L, LEN_H, INST, PARAMS..., CRC_L, CRC_H]
    length = len(instruction) + 3  # instruction + params + CRC(2)
    len_l = length & 0xFF
    len_h = (length >> 8) & 0xFF
    
    packet_base = [0xFF, 0xFF, 0xFD, 0x00, self.servo_id, len_l, len_h] + instruction
    crc = self.__calc_crc(packet_base)
    crc_l = crc & 0xFF
    crc_h = (crc >> 8) & 0xFF
    msg = packet_base + [crc_l, crc_h]
    
    with self.dyn.lock:
        failures = 0
        while True:
            try:
                self.dyn.flush_input()
                self.send_serial(msg)
                data, err = self.receive_reply()
                break
            except (CommunicationError, serial.SerialException, socket.timeout) as e:
                failures += 1
                if failures > self.retry_count:
                    raise
                warning("send_instruction retry %d, error: %s"%(failures, e))
    
    if exceptionOnErrorResponse:
        if err != 0:
            self.process_err(err)
        return data
    else:
        return data, err
```

#### 1.4 Update receive_reply() for Protocol 2

Replace lines 358-381 with:

```python
def receive_reply(self):
    """Receive Protocol 2.0 status packet"""
    # Protocol 2.0 status: [0xFF, 0xFF, 0xFD, 0x00, ID, LEN_L, LEN_H, INST, ERR, PARAMS..., CRC_L, CRC_H]
    
    # Read header [0xFF, 0xFF, 0xFD, 0x00]
    header = self.dyn.read_serial(4)
    if list(header) != [0xFF, 0xFF, 0xFD, 0x00]:
        raise CommunicationError('Invalid Protocol 2.0 header')
    
    # Read ID
    servo_id = ord(self.dyn.read_serial(1))
    if servo_id != self.servo_id:
        raise CommunicationError('Incorrect servo ID: %d, expected %d' % (servo_id, self.servo_id))
    
    # Read length
    len_l = ord(self.dyn.read_serial(1))
    len_h = ord(self.dyn.read_serial(1))
    length = len_l + (len_h << 8)
    
    # Read instruction
    inst = ord(self.dyn.read_serial(1))
    
    # Read error
    err = ord(self.dyn.read_serial(1))
    
    # Read parameters (length - 4 for inst, err, crc_l, crc_h)
    param_len = length - 4
    if param_len > 0:
        params = self.dyn.read_serial(param_len)
    else:
        params = b''
    
    # Read CRC
    crc_l = ord(self.dyn.read_serial(1))
    crc_h = ord(self.dyn.read_serial(1))
    crc_received = crc_l + (crc_h << 8)
    
    # Calculate CRC
    packet_for_crc = [0xFF, 0xFF, 0xFD, 0x00, servo_id, len_l, len_h, inst, err] + list(params)
    crc_calc = self.__calc_crc(packet_for_crc)
    
    if crc_calc != crc_received:
        raise CommunicationError('CRC mismatch: calculated %04X, received %04X' % (crc_calc, crc_received))
    
    return list(params), err
```

#### 1.5 Add Bulk Read Method

Add after `write_addressX()` method:

```python
def bulk_read(self, read_list):
    """
    Bulk read multiple registers in one transaction (Protocol 2.0)
    
    Args:
        read_list: List of (address, length) tuples
        
    Returns:
        List of data arrays corresponding to each read
    """
    # Build bulk read instruction
    # Format: [INST_BULK_READ, [addr1_L, addr1_H, len1_L, len1_H], [addr2_L, addr2_H, len2_L, len2_H], ...]
    params = []
    for addr, length in read_list:
        params.extend([
            addr & 0xFF,
            (addr >> 8) & 0xFF,
            length & 0xFF,
            (length >> 8) & 0xFF
        ])
    
    msg = [INST_BULK_READ] + params
    data = self.send_instruction(msg)
    
    # Parse response - data contains all requested values concatenated
    results = []
    offset = 0
    for _, length in read_list:
        results.append(data[offset:offset+length])
        offset += length
    
    return results
```

#### 1.6 Add Bulk Write Method

Add after bulk_read():

```python
def bulk_write(self, write_list):
    """
    Bulk write multiple registers in one transaction (Protocol 2.0)
    
    Args:
        write_list: List of (address, data) tuples where data is list of bytes
    """
    # Build bulk write instruction
    # Format: [INST_BULK_WRITE, [addr1_L, addr1_H, data1...], [addr2_L, addr2_H, data2...], ...]
    params = []
    for addr, data in write_list:
        params.extend([
            addr & 0xFF,
            (addr >> 8) & 0xFF
        ] + data)
    
    msg = [INST_BULK_WRITE] + params
    self.send_instruction(msg)
```

#### 1.7 Update All Register Address References

Update these methods with new addresses:

```python
# Line 159: init_cont_turn()
self.write_address(52, [0,0])  # Was 0x08

# Line 164: kill_cont_turn()
self.write_address(52, [255, 3])  # Was 0x08

# Line 169: is_moving()
data = self.read_address(122, 1)  # Was 0x2e

# Line 175: read_voltage()
data = self.read_address(144, 1)  # Was 0x2a

# Line 181: read_temperature()
data = self.read_address(146, 1)  # Was 0x2b

# Line 188: read_load()
data = self.read_address(126, 2)  # Was 0x28

# Line 196: read_present_speed()
speed = self.read_word(128)  # Was 38

# Line 204: read_encoder()
data = self.read_address(132, 2)  # Was 0x24

# Line 219: enable_torque()
return self.write_address(64, [1])  # Was 0x18

# Line 222: disable_torque()
return self.write_address(64, [0])  # Was 0x18

# Line 234: set_angvel()
return self.write_address(104, [lo,hi])  # Was 0x20

# Line 239: write_id()
return self.write_address(7, [new_id])  # Was 0x03

# Line 242: write_baudrate()
return self.write_address(8, [rate])  # Was 0x04
```

---

### Phase 2: Gripper Control Layer

#### 2.1 Update ezgripper_base.py

Replace `set_torque_mode()` function (lines 38-42):

```python
def set_torque_mode(servo, val):
    """
    Set operating mode for Protocol 2.0
    
    Operating Mode values:
    - 0: Current (Torque) Control Mode
    - 1: Velocity Control Mode
    - 3: Position Control Mode (default)
    - 4: Extended Position Control Mode
    - 5: Current-based Position Control Mode
    """
    if val:
        # Enable torque control mode
        servo.write_address(11, [0])  # Operating Mode = Current Control
    else:
        # Return to position control mode
        servo.write_address(11, [3])  # Operating Mode = Position Control
```

---

### Phase 3: Application Layer

#### 3.1 Update hardware_controller.py

Update `_read_current()` method (lines 449-471):

```python
def _read_current(self) -> float:
    """
    Read actual motor current from servo.
    
    Protocol 2.0: Register 126 (Present Current)
    
    TODO: Verify formula - using Protocol 1 formula as baseline:
    Formula: I = (4.5mA) * (CURRENT - 2048)
    
    This needs empirical verification after migration!
    
    Returns:
        Current magnitude in mA (absolute value)
    """
    try:
        # Read present current (address 126, 2 bytes)
        current_raw = self.gripper.servos[0].read_word(126)
        
        # Using Protocol 1 formula as starting point - NEEDS VERIFICATION
        current_ma = int(4.5 * (current_raw - 2048))
        
        # Return absolute value for magnitude comparison
        return abs(current_ma)
    except Exception as e:
        self.logger.debug(f"Failed to read current: {e}")
        return 0.0
```

Add new bulk read method:

```python
def read_servo_state_bulk(self) -> dict:
    """
    Read all servo state in one bulk read transaction (Protocol 2.0 feature)
    
    Returns:
        dict with current, position, load, error
    """
    try:
        servo = self.gripper.servos[0]
        
        # Bulk read: Current@126, Position@132, Hardware_Error@70
        data_arrays = servo.bulk_read([
            (126, 2),  # Present Current (2 bytes)
            (132, 4),  # Present Position (4 bytes)
            (70, 1),   # Hardware Error Status (1 byte)
        ])
        
        # Parse current
        current_raw = data_arrays[0][0] + (data_arrays[0][1] << 8)
        current_ma = int(4.5 * (current_raw - 2048))  # TODO: Verify formula
        
        # Parse position
        pos_bytes = data_arrays[1]
        position = pos_bytes[0] + (pos_bytes[1] << 8) + (pos_bytes[2] << 16) + (pos_bytes[3] << 24)
        if position >= 2147483648:
            position -= 4294967296  # Convert to signed
        
        # Parse error
        error = data_arrays[2][0]
        
        return {
            'current': abs(current_ma),
            'position': position,
            'error': error,
            'timestamp': time.time()
        }
    except Exception as e:
        self.logger.debug(f"Failed to read servo state: {e}")
        return None
```

#### 3.2 Update clear_servo_error.py

Update register addresses (lines 51-65):

```python
# Disable torque mode FIRST (required before clearing error)
print("Disabling torque mode...")
servo.write_address(11, [3])  # Operating Mode = Position Control (was 70)
servo.write_address(64, [0])  # Torque Enable = 0 (was 24)
time.sleep(0.1)

if error != 0:
    print("Clearing error state...")
    # Write 0 to hardware error status register (after torque disabled)
    servo.write_address(70, [0])  # Was 18
    time.sleep(0.1)
    
    # Verify
    error = servo.read_address(70, 1)[0]  # Was 18
    print(f"Error state after clear: {error} (0x{error:02X})")

# Set to safe position mode
print("Setting safe current limit...")
servo.write_word(38, 512)  # Current Limit (was 34 for Torque Limit)
```

---

### Phase 4: Test Files

Update all test files with new register addresses. Common pattern:

```python
# Position registers
servo.read_word(132)  # Was 36 - Present Position
servo.write_word(116, pos)  # Was 30 - Goal Position

# Current/Load registers  
servo.read_word(126)  # Was 68 - Present Current (was 40 for Load in P1)

# Torque registers
servo.write_word(38, limit)  # Was 34 - Current Limit (was Torque Limit)
servo.write_word(102, goal)  # Was 71 - Goal Current (was Goal Torque)

# Mode control
servo.write_address(11, [0])  # Was 70 - Operating Mode (Torque Control)
servo.write_address(11, [3])  # Position Control Mode

# Error
servo.write_address(70, [0])  # Was 18 - Hardware Error Status
```

Files to update:
- test_mode_characterization.py
- test_incremental_torque.py
- test_movement_current.py
- test_simple_positions.py
- test_measure_range.py
- test_position_mapping.py
- test_spring_pullback.py
- test_verify_current.py
- test_resistance_mapping.py
- test_backoff_torque.py
- test_gripper.py

---

## Testing Plan

### 1. Basic Communication Test
```bash
python3 -c "from libezgripper import create_connection, Gripper; \
conn = create_connection('/dev/ttyUSB0', 57600); \
g = Gripper(conn, 'test', [1]); \
print('Position:', g.get_position())"
```

### 2. Current Reading Verification
```bash
python3 test_movement_current.py /dev/ttyUSB0
# Compare results with Protocol 1 baseline
```

### 3. Full Characterization
```bash
python3 test_mode_characterization.py --dev /dev/ttyUSB0
# Verify current values match Protocol 1 characterization
```

### 4. Bulk Operations Test
Create new test to verify bulk read/write performance improvement.

---

## Expected Issues & Solutions

### Issue 1: Current Formula Different
**Symptom**: Current readings don't match Protocol 1 baseline  
**Solution**: Derive formula empirically by comparing known states

### Issue 2: Torque Mode Behavior Different
**Symptom**: Gripper doesn't hold with same force  
**Solution**: Adjust Operating Mode settings or Goal Current values

### Issue 3: Packet Timing Different
**Symptom**: Communication errors or timeouts  
**Solution**: Adjust timeout values in serial port configuration

---

## Rollback Plan

If migration fails:
```bash
git reset --hard HEAD~1  # Return to Protocol 1 baseline
```

Protocol 1 implementation is fully functional and committed.

---

## Success Criteria

- [ ] All register reads/writes work
- [ ] Current readings within 10% of Protocol 1 baseline
- [ ] Resistance detection works reliably
- [ ] Bulk read provides 3-5x data improvement
- [ ] All characterization tests pass
- [ ] No regression in control quality

---

## Estimated Implementation Time

- lib_robotis.py updates: 4-6 hours
- Application layer updates: 2-3 hours
- Test file updates: 2-3 hours
- Testing & validation: 3-4 hours
- **Total: 11-16 hours** (1.5-2 days)

---

## Notes

- Keep Protocol 1 version in git history for reference
- Document any behavioral differences discovered
- Update characterization data after validation
- Consider creating Protocol 1/2 abstraction layer for future flexibility
