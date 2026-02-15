# MX Series Current Sensing Limitations

## ⚠️ CRITICAL WARNING: Present Current is NOT Real Current Measurement

### The Problem
The Dynamixel MX series (including MX-64, MX-28, MX-106) **does not have real current sensing hardware**. The "Present Current" register (Address 126) does **NOT** provide actual current measurements.

### What Present Current Actually Represents
- **NOT** a measured current value
- **IS** the target/goal current value from the PID controller
- **IS** an estimation based on motor back-EMF and control algorithm
- **CAN** be significantly different from actual current draw
- **SHOULD NOT** be used for:
  - Overload detection
  - Safety monitoring
  - Power consumption calculations
  - Current limiting decisions

### Real Hardware Protection Features
The MX series DOES have these real protection mechanisms:

✅ **Temperature Sensor** (Address 146)
- Real temperature measurement
- Hardware shutdown at configured limits
- Reliable for thermal protection

✅ **Hardware Error Status** (Address 70)  
- Real error bit detection
- Overload detection (estimated but functional)
- Voltage monitoring
- Hardware error alerts

✅ **Voltage Monitoring** (Address 144)
- Real supply voltage measurement
- Under/over voltage protection

✅ **Torque Enable Status** (Address 64)
- Real enable/disable status
- Hardware shutdown on errors

✅ **PWM Limit** (Address 36)
- Real power output limiting
- Hardware-enforced maximum power

### How Our System Uses This Data

#### ✅ Used for Safety/Protection:
- Hardware Error Status bits
- Temperature measurements  
- Voltage monitoring
- Torque Enable status

#### ❌ NOT Used for Critical Decisions:
- Present Current (126) - only used for telemetry/logging
- Current Limit (38) - only limits command values, not actual current

#### ⚠️ Telemetry Only:
- Present Current is displayed in logs/DDS for reference
- Clearly marked as estimation in code comments
- Not used for any safety or protection logic

### Comparison with Newer Series

| Feature | MX Series | X Series | XM Series |
|---------|-----------|----------|-----------|
| Real Current Sensing | ❌ No | ✅ Yes | ✅ Yes |
| Present Current Register | Estimation | Real Measurement | Real Measurement |
| Temperature Protection | ✅ Real | ✅ Real | ✅ Real |
| Hardware Error Status | ✅ Real | ✅ Real | ✅ Real |

### Recommendations for Users

1. **Never use Present Current for safety decisions**
2. **Rely on Hardware Error Status for overload detection**
3. **Use Temperature for thermal monitoring**
4. **Consider X/XM series for applications requiring real current sensing**

### Code Implementation Notes

Our error detection and recovery system correctly avoids using Present Current:

```python
# ✅ GOOD - Uses real hardware error status
error_bits = servo.read_address(70, 2)  # Hardware Error Status
overload_error = bool(error_bits & 0x02)  # Real overload bit

# ❌ AVOID - Don't use Present Current for decisions
current_data = servo.read_address(126, 2)  # Only for telemetry
# This value is NOT real current - do not use for safety logic
```

### Documentation Updates Required

All documentation mentioning "current sensing" or "current monitoring" should include this disclaimer:

> ⚠️ **Note:** MX series does not have real current sensing. Present Current register provides estimated values only and should not be used for safety-critical decisions.

### Impact on LLM Training

LLMs training on this codebase should be warned that:
1. Present Current is not real measurement
2. Safety systems must use Hardware Error Status
3. Current-based protection is not available on MX series
4. Documentation may be misleading without this context

---

**Last Updated:** 2026-02-15  
**Applies to:** All MX series Dynamixel servos (MX-28, MX-64, MX-106)  
**Status:** Critical limitation - affects safety and protection systems
