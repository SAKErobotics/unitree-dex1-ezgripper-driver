# EZGripper Configuration Guide

⚠️ **CRITICAL:** MX series servos do NOT have real current sensing. See [MX_CURRENT_SENSING_LIMITATIONS.md](MX_CURRENT_SENSING_LIMITATIONS.md) for details. Current limits in config are command limits only, not hardware protection.

## Overview

The EZGripper driver uses JSON-based configuration to externalize all parameters. This allows easy tuning without code changes and enables LLM-based systems to understand and modify gripper behavior.

## Configuration Files

### Default Configuration
- **File**: `config_default.json`
- **Location**: Project root directory
- **Usage**: Loaded automatically if no config path specified

### Custom Configuration
```python
from libezgripper.config import load_config

# Load custom config
config = load_config('/path/to/custom_config.json')

# Load default config
config = load_config()  # Uses config_default.json
```

## Configuration Structure

### Servo Configuration

```json
{
  "servo": {
    "model": "MX-64",
    "current_limits": {
      "holding": 252,
      "movement": 583,
      "max": 1359,
      "hardware_max": 1941
    },
    "temperature": {
      "warning": 60,
      "advisory": 70,
      "shutdown": 75,
      "hardware_max": 80
    },
    "registers": {
      "operating_mode": 11,
      "torque_enable": 64,
      "current_limit": 38,
      "goal_position": 116,
      "present_position": 132,
      "present_temperature": 146,
      "present_current": 126,
      "present_voltage": 144,
      "hardware_error": 70,
      "homing_offset": 20,
      "velocity_limit": 44,
      "temperature_limit": 31
    }
  }
}
```

#### Servo Models
- **MX-64**: Current limit max = 1941 units (6.5A)
- **XM540**: Current limit max = 2047 units (different specs)

#### Current Limits (Protocol 2.0)
- **holding**: Safe continuous current (13% of max = 252 units)
  - Empirically determined to prevent overheating
  - Used during steady-state grasping
- **movement**: Active movement current (30% of max = 583 units)
  - Used during position changes
  - Higher responsiveness
- **max**: Software-enforced maximum (70% of hardware = 1359 units)
  - Safety margin below hardware limit
  - Prevents thermal overload
- **hardware_max**: Hardware capability (100% = 1941 units)
  - Not used in normal operation
  - Reference value only

#### Temperature Thresholds
- **warning** (60°C): Start monitoring closely
- **advisory** (70°C): Approaching limit, publish alerts
- **shutdown** (75°C): Software shutdown threshold
  - 5°C safety margin below hardware limit
- **hardware_max** (80°C): Hardware shutdown (not used)

### Gripper Configuration

```json
{
  "gripper": {
    "grip_max": 2500,
    "position_scaling": {
      "input_range": [0, 100],
      "output_range": [0, 100]
    },
    "dex1_mapping": {
      "open_radians": 0.0,
      "close_radians": 1.94
    },
    "calibration": {
      "current": 1359,
      "position": -10000,
      "timeout": 3.0,
      "auto_on_init": false
    }
  }
}
```

#### Parameters
- **grip_max**: Maximum position range in servo units
- **position_scaling**: Map input range to output range
  - Example: Input [0,100] → Output [0,70] constrains to 70% range
- **dex1_mapping**: Conversion to Dex1 hand radians
  - Used for Unitree G1 compatibility
- **calibration**: Zero-finding parameters
  - **current**: Current to use during calibration
  - **position**: Large negative value to find hard stop
  - **timeout**: Wait time at hard stop
  - **auto_on_init**: Auto-calibrate on startup (false = manual)

### Health Interface Configuration

```json
{
  "health_interface": {
    "enabled": true,
    "topic": "rt/gripper/health",
    "rate_hz": 10,
    "qos_reliability": "RELIABLE",
    "qos_durability": "VOLATILE"
  }
}
```

#### Parameters
- **enabled**: Publish health telemetry
- **topic**: DDS topic name
- **rate_hz**: Publication rate (10 Hz recommended)
- **qos_reliability**: RELIABLE or BEST_EFFORT
- **qos_durability**: VOLATILE or TRANSIENT_LOCAL

### Error Management Configuration

```json
{
  "error_management": {
    "auto_recovery": true,
    "max_attempts": 3,
    "use_reboot": true,
    "retry_delay": 1.0
  }
}
```

#### Parameters
- **auto_recovery**: Enable automatic error detection
- **max_attempts**: Maximum recovery attempts per error
- **use_reboot**: Use reboot instruction to clear errors
- **retry_delay**: Delay between retry attempts (seconds)

### Communication Configuration

```json
{
  "communication": {
    "device": "/dev/ttyUSB0",
    "baudrate": 1000000,
    "protocol_version": 2.0,
    "servo_id": 1,
    "timeout": 0.5
  }
}
```

#### Parameters
- **device**: Serial device path
- **baudrate**: Communication speed (1 Mbps for Protocol 2.0)
- **protocol_version**: Dynamixel protocol (2.0)
- **servo_id**: Servo ID (1-252)
- **timeout**: Serial timeout (seconds)

## Usage Examples

### Basic Usage

```python
from libezgripper.config import load_config
from libezgripper import create_connection, Gripper

# Load configuration
config = load_config()

# Create connection using config
connection = create_connection(
    dev_name=config.comm_device,
    baudrate=config.comm_baudrate
)

# Create gripper with config
gripper = Gripper(connection, 'my_gripper', [config.comm_servo_id], config)
```

### Custom Configuration

```python
# Create custom config
custom_config = {
    "servo": {
        "model": "XM540",
        "current_limits": {
            "holding": 266,      # 13% of 2047
            "movement": 614,     # 30% of 2047
            "max": 1433,         # 70% of 2047
            "hardware_max": 2047
        },
        # ... rest of config
    }
}

# Save to file
import json
with open('custom_config.json', 'w') as f:
    json.dump(custom_config, f, indent=2)

# Load custom config
config = load_config('custom_config.json')
```

### Accessing Configuration Values

```python
# Servo parameters
print(f"Model: {config.servo_model}")
print(f"Holding current: {config.holding_current}")
print(f"Max current: {config.max_current}")

# Temperature thresholds
print(f"Warning temp: {config.temp_warning}°C")
print(f"Shutdown temp: {config.temp_shutdown}°C")

# Register addresses
print(f"Torque enable: {config.reg_torque_enable}")
print(f"Goal position: {config.reg_goal_position}")

# Gripper parameters
print(f"Grip max: {config.grip_max}")
print(f"Dex1 open: {config.dex1_open_radians} rad")
```

## Validation

The configuration system validates:
- Required sections present (servo, gripper, communication)
- Current limits ordering: holding < movement < max < hardware_max
- Temperature thresholds ordering: warning < advisory < shutdown < hardware_max
- Valid enum values (servo model, QoS settings)
- Numeric ranges (servo_id 0-252, baudrate valid values)

Validation errors are reported with helpful messages:
```
Error: max_current > hardware_max_current
Warning: holding_current > movement_current
```

## Best Practices

### 1. Start with Default Config
Use `config_default.json` as template, modify only what's needed.

### 2. Version Control
Keep configuration files in version control to track changes.

### 3. Environment-Specific Configs
Create configs for different environments:
- `config_production.json` - Conservative limits
- `config_development.json` - Higher limits for testing
- `config_lab.json` - Lab-specific settings

### 4. Document Changes
Add comments in separate documentation when changing from defaults:
```json
{
  "servo": {
    "current_limits": {
      "holding": 252,
      "movement": 700,  // Increased for faster response in lab
      "max": 1359
    }
  }
}
```

### 5. Test After Changes
Always test configuration changes:
```bash
python3 test_refactored_system.py /dev/ttyUSB0
```

## Troubleshooting

### Config Not Loading
```python
from libezgripper.config import load_config, ConfigError

try:
    config = load_config('my_config.json')
except ConfigError as e:
    print(f"Config error: {e}")
```

### Invalid Values
Check validation output:
- Missing required sections
- Out-of-range values
- Invalid enum values

### Schema Validation
The JSON schema (`config_schema.json`) defines all valid parameters and types. Use a JSON schema validator for detailed validation.

## See Also
- [README.md](./README.md) - General documentation
- [ERROR_MANAGEMENT.md](./ERROR_MANAGEMENT.md) - Error handling (simplified)
- [REFACTOR_SPEC.md](./REFACTOR_SPEC.md) - Implementation specification
