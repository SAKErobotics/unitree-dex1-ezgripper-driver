# EZGripper DDS Interfaces

This driver provides **3 distinct DDS interfaces** for different use cases.

## Quick Reference

| Interface | Use Case | Topics | Force Control |
|-----------|----------|--------|---------------|
| **Agnostic Direct** | Universal control | `rt/gripper/{side}/cmd_direct` | ✅ Dynamic |
| **Dex1 Humanoid** | Unitree G1 only | `rt/dex1/{side}/cmd` | ❌ Fixed |
| **Telemetry** | Monitoring | `rt/gripper/{side}/telemetry` | N/A |

---

## 1. Agnostic Direct Control Interface ⭐

**Best for:** Custom robots, vision systems, non-Unitree platforms

**Topics:**
- Command: `rt/gripper/{side}/cmd_direct`
- State: `rt/gripper/{side}/state_direct`

**Command Format:**
```json
{
  "position_pct": 0.0,      // 0.0 (closed) to 100.0 (open)
  "force_limit_pct": 25     // 0 to 100% dynamic force
}
```

**Key Feature:** Adjust force on every cycle (soft for eggs, firm for heavy objects)

**Example:**
```python
import json
from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.pub import Publisher, DataWriter
import ctypes

class GenericStringIDL(ctypes.Structure):
    _fields_ = [("data", ctypes.c_char_p)]

participant = DomainParticipant()
cmd_topic = Topic(participant, "rt/gripper/left/cmd_direct", GenericStringIDL)
publisher = Publisher(participant)
writer = DataWriter(publisher, cmd_topic)

# Soft grasp (5% force)
payload = {"position_pct": 0.0, "force_limit_pct": 5}
msg_bytes = json.dumps(payload).encode('utf-8')
sample = GenericStringIDL(data=msg_bytes)
writer.write(sample)
```

---

## 2. Dex1 Humanoid Interface

**Best for:** Unitree G1 robots with XR teleoperate

**Topics:**
- Command: `rt/dex1/{side}/cmd`
- State: `rt/dex1/{side}/state`

**Command Format:**
- Position: 0.0 to 5.4 radians
- Force: Fixed from configuration files

**Key Feature:** Compatible with Unitree XR teleoperate framework

**Example:**
```bash
# Start driver
python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0
```

---

## 3. Telemetry Interface

**Best for:** Monitoring, diagnostics, contact detection

**Topics:**
- State: `rt/gripper/{side}/telemetry` (read-only)

**State Format:**
```json
{
  "hardware": {
    "temperature_c": 42.5,
    "error_code": 0
  },
  "contact": false,
  "pos": "50.0%",
  "state": "moving"
}
```

**Key Feature:** Real-time hardware health and contact detection

---

## Which Interface Should I Use?

### Use Agnostic Direct Control If:
- You're building a custom robot
- You need dynamic force control
- You're not using Unitree G1
- You want vision-based force adaptation

### Use Dex1 Humanoid Interface If:
- You're using Unitree G1 robot
- You need XR teleoperate compatibility
- You're okay with fixed force settings

### Use Telemetry Interface If:
- You need hardware health monitoring
- You want to detect contact events
- You're tracking grasp states

---

## Quick Start

### For Unitree G1 Users
```bash
python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0
```

### For Custom Robot Users
```python
# Use Agnostic Direct Control interface
# See example above
```

---

## Troubleshooting

### Interface Not Found
- Verify domain ID matches
- Check participant is running
- Ensure topic names are correct

### Message Format Errors
- Verify JSON structure for agnostic interface
- Check MotorCmds_ structure for Dex1 interface
- Ensure encoding is UTF-8
