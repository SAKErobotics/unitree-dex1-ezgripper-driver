# EZGripper Error Management System

## Overview

The EZGripper driver includes a comprehensive error management system for handling Dynamixel MX-64 servo errors in Protocol 2.0. The error manager provides automatic detection, classification, and recovery from common hardware errors.

## Features

### 1. Automatic Error Detection
- Monitors Hardware Error Status (Register 70)
- Checks errors on gripper initialization
- Can be called manually for periodic monitoring

### 2. Error Classification

**Hardware Error Types (Register 70 bits):**

| Bit | Value | Error Type | Severity | Description |
|-----|-------|------------|----------|-------------|
| 0 | 1 | Input Voltage | ERROR | Supply voltage out of range (9.5-16V) |
| 2 | 4 | Overheating | CRITICAL | Internal temperature exceeded limit (80°C) |
| 3 | 8 | Motor Encoder | CRITICAL | Motor encoder malfunction |
| 4 | 16 | Electrical Shock | CRITICAL | Electrical shock detected |
| 5 | 32 | Overload | ERROR | Persistent overload detected |

### 3. Automatic Recovery Strategies

#### Overload Error (Bit 5 = 32)
**Cause:** Motor under excessive load, cannot reach goal position

**Recovery Strategy:**
1. Disable torque
2. Wait 0.5s for motor to settle
3. Clear error (write 0 to register 70)
4. Reduce current limit to 70% (1359/1941)
5. Re-enable torque
6. Verify error cleared

**Prevention:**
- Don't command positions beyond physical limits
- Ensure nothing blocks gripper movement
- Use appropriate current limits for load

#### Input Voltage Error (Bit 0 = 1)
**Cause:** Supply voltage outside 9.5-16V range

**Recovery Strategy:**
1. Read current voltage (Register 144)
2. If voltage now in range (9.5-16V):
   - Clear error
   - Resume operation
3. If voltage still out of range:
   - Disable torque for safety
   - Log critical error
   - Require manual intervention

**Prevention:**
- Use stable 12V power supply
- Check power supply capacity (>2A recommended)
- Monitor voltage under load

#### Overheating Error (Bit 2 = 4)
**Cause:** Internal temperature exceeded 80°C limit

**Recovery Strategy:**
1. Disable torque immediately
2. Wait 30 seconds for cooling
3. Check temperature (Register 146)
4. If temperature < 70°C:
   - Clear error
   - Reduce current limit to 50% (970/1941)
   - Re-enable torque
5. If temperature still high:
   - Keep torque disabled
   - Require manual cooling

**Prevention:**
- Avoid continuous high-load operation
- Ensure adequate ventilation
- Monitor ambient temperature
- Use appropriate current limits

#### Critical Errors (Motor Encoder, Electrical Shock)
**Recovery Strategy:**
1. Attempt single error clear
2. If unsuccessful, require manual inspection

**Prevention:**
- Regular maintenance
- Avoid mechanical shock
- Check wiring integrity

## Usage

### Basic Usage with Auto-Recovery

```python
from libezgripper import create_connection, Gripper

# Create connection
connection = create_connection(dev_name='/dev/ttyUSB0', baudrate=1000000)

# Create gripper with error manager enabled (default)
gripper = Gripper(connection, 'my_gripper', [1], enable_error_manager=True)

# Error manager automatically:
# 1. Checks for errors on initialization
# 2. Attempts recovery if errors found
# 3. Logs all actions
```

### Manual Error Checking

```python
# Check for errors manually
if gripper.error_managers:
    error_mgr = gripper.error_managers[0]  # First servo
    
    error_code, description, severity = error_mgr.check_hardware_errors()
    
    if error_code != 0:
        print(f"Error detected: {description}")
        print(f"Severity: {severity}")
        
        # Attempt recovery
        if error_mgr.attempt_recovery(error_code):
            print("Recovery successful")
        else:
            print("Recovery failed - manual intervention required")
```

### Manual Error Clearing

```python
# Clear error without automatic recovery
if gripper.error_managers:
    error_mgr = gripper.error_managers[0]
    
    if error_mgr.clear_hardware_error():
        print("Error cleared successfully")
    else:
        print("Failed to clear error")
```

### Error Statistics

```python
# Get error statistics
if gripper.error_managers:
    error_mgr = gripper.error_managers[0]
    stats = error_mgr.get_error_statistics()
    
    print(f"Total errors: {stats['total_errors']}")
    print(f"Last error: 0x{stats['last_error']:02X}")
    print(f"Recovery attempts: {stats['recovery_attempts']}")
```

### Configuration Options

```python
# Disable auto-recovery
gripper = Gripper(connection, 'my_gripper', [1], enable_error_manager=False)

# Custom recovery settings
from libezgripper.error_manager import create_error_manager

error_mgr = create_error_manager(
    servo,
    auto_recover=True,           # Enable auto-recovery
    max_recovery_attempts=3      # Max attempts per error
)
```

## Error Recovery Flowchart

```
┌─────────────────────────────────┐
│  Gripper Initialization         │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Check Hardware Error (Reg 70)  │
└──────────────┬──────────────────┘
               │
         ┌─────┴─────┐
         │ Error=0?  │
         └─────┬─────┘
               │
       ┌───────┴───────┐
       │               │
      Yes             No
       │               │
       ▼               ▼
   ┌───────┐   ┌──────────────┐
   │ Ready │   │ Classify     │
   └───────┘   │ Error Type   │
               └──────┬───────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
   ┌─────────┐  ┌──────────┐  ┌─────────┐
   │Overload │  │ Voltage  │  │Overheat │
   └────┬────┘  └────┬─────┘  └────┬────┘
        │            │             │
        ▼            ▼             ▼
   ┌─────────┐  ┌──────────┐  ┌─────────┐
   │Reduce   │  │Check     │  │Cool     │
   │Current  │  │Voltage   │  │Down     │
   │70%      │  │Range     │  │30s      │
   └────┬────┘  └────┬─────┘  └────┬────┘
        │            │             │
        └────────────┼─────────────┘
                     │
                     ▼
            ┌────────────────┐
            │ Clear Error    │
            │ (Write 0→Reg70)│
            └────────┬───────┘
                     │
              ┌──────┴──────┐
              │ Verify      │
              │ Error=0?    │
              └──────┬──────┘
                     │
              ┌──────┴──────┐
              │             │
             Yes           No
              │             │
              ▼             ▼
         ┌────────┐   ┌──────────┐
         │Success │   │ Failed   │
         │Resume  │   │ Manual   │
         │Ops     │   │ Required │
         └────────┘   └──────────┘
```

## Logging

The error manager uses Python's `logging` module. Configure logging to see error manager output:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

**Log Levels:**
- `INFO`: Normal operations, recovery success
- `WARNING`: Errors detected, recovery attempts
- `ERROR`: Recovery failed, manual intervention needed
- `CRITICAL`: Critical hardware errors, safety shutdowns

## Best Practices

### 1. Enable Error Manager
Always enable the error manager for production use:
```python
gripper = Gripper(connection, 'gripper', [1], enable_error_manager=True)
```

### 2. Monitor Error Statistics
Periodically check error statistics to identify recurring issues:
```python
stats = error_mgr.get_error_statistics()
if stats['total_errors'] > 10:
    print("High error count - investigate root cause")
```

### 3. Handle Recovery Failures
Always check if recovery succeeded:
```python
if not error_mgr.attempt_recovery(error_code):
    # Recovery failed - stop operation
    gripper.release()  # Disable torque
    # Alert operator
```

### 4. Set Appropriate Current Limits
Use conservative current limits to prevent overload:
```python
gripper.set_max_effort(70)  # 70% of max current
```

### 5. Implement Graceful Degradation
If errors persist, reduce performance rather than failing:
```python
if error_mgr.recovery_attempts.get(error_code, 0) >= 2:
    # Reduce to 50% performance
    gripper.set_max_effort(50)
```

## Troubleshooting

### Error Won't Clear
**Symptom:** `clear_hardware_error()` returns False

**Solutions:**
1. Check if torque is disabled (required for clearing)
2. Wait longer between disable and clear (0.1s minimum)
3. Power cycle the servo
4. Check for physical damage

### Repeated Overload Errors
**Symptom:** Overload error keeps returning

**Solutions:**
1. Check for mechanical obstruction
2. Reduce current limit further (50% or lower)
3. Verify goal positions are within physical limits
4. Check for binding in gripper mechanism

### Voltage Errors
**Symptom:** Input voltage errors

**Solutions:**
1. Check power supply voltage (should be 12V ±10%)
2. Verify power supply current capacity (>2A)
3. Check wiring for voltage drop
4. Use shorter/thicker power cables

### Overheating
**Symptom:** Repeated overheating errors

**Solutions:**
1. Improve ventilation around servo
2. Reduce duty cycle (add delays between operations)
3. Lower current limit
4. Check ambient temperature (<40°C recommended)

## Integration with DDS Driver

The error manager integrates seamlessly with the DDS driver:

```python
# ezgripper_dds_driver.py automatically uses error manager
driver = EZGripperDDSDriver(
    side='left',
    device='/dev/ttyUSB0',
    domain=0
)

# Error manager runs on initialization
# Errors are logged via DDS driver's logger
# Recovery is automatic
```

## API Reference

### ErrorManager Class

**Constructor:**
```python
ErrorManager(servo, auto_recover=True, max_recovery_attempts=3)
```

**Methods:**
- `check_hardware_errors()` → (error_code, description, severity)
- `clear_hardware_error()` → bool
- `attempt_recovery(error_code)` → bool
- `recover_from_overload()` → bool
- `recover_from_voltage_error()` → bool
- `recover_from_overheating()` → bool
- `get_error_statistics()` → dict
- `reset_statistics()` → None

### Factory Function

```python
create_error_manager(servo, **kwargs) → ErrorManager
```

## See Also

- [Dynamixel Protocol 2.0 Specification](https://emanual.robotis.com/docs/en/dxl/protocol2/)
- [MX-64(2.0) Control Table](https://emanual.robotis.com/docs/en/dxl/mx/mx-64-2/)
- [DDS_INTERFACE_SPECIFICATION.md](./DDS_INTERFACE_SPECIFICATION.md)
- [README.md](./README.md)
