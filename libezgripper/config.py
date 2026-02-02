#!/usr/bin/env python3
"""
Configuration loader for EZGripper driver

Loads and validates JSON configuration files against schema.
Provides typed access to configuration parameters.
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigError(Exception):
    """Configuration loading or validation error"""
    pass


class Config:
    """Configuration container with typed access to parameters"""
    
    def __init__(self, config_dict: Dict[str, Any]):
        self._config = config_dict
    
    # Servo configuration
    @property
    def servo_model(self) -> str:
        return self._config['servo']['model']
    
    @property
    def operating_mode(self) -> int:
        return self._config['servo']['operating_mode']
    
    @property
    def holding_current(self) -> int:
        return self._config['servo']['current_limits']['holding']
    
    @property
    def movement_current(self) -> int:
        return self._config['servo']['current_limits']['movement']
    
    @property
    def max_current(self) -> int:
        return self._config['servo']['current_limits']['max']
    
    @property
    def hardware_max_current(self) -> int:
        return self._config['servo']['current_limits']['hardware_max']
    
    @property
    def pwm_limit(self) -> int:
        return self._config['servo'].get('pwm_limit', 885)
    
    @property
    def backpressure_control(self) -> Dict[str, Any]:
        return self._config['servo'].get('backpressure_control', {})
    
    @property
    def current_limits(self) -> Dict[str, int]:
        return {
            'holding': self.holding_current,
            'movement': self.movement_current,
            'max': self.max_current,
            'hardware_max': self.hardware_max_current
        }
    
    @property
    def temp_warning(self) -> int:
        return self._config['servo']['temperature']['warning']
    
    @property
    def temp_advisory(self) -> int:
        return self._config['servo']['temperature']['advisory']
    
    @property
    def temp_shutdown(self) -> int:
        return self._config['servo']['temperature']['shutdown']
    
    @property
    def temp_hardware_max(self) -> int:
        return self._config['servo']['temperature']['hardware_max']
    
    # Register addresses
    @property
    def reg_operating_mode(self) -> int:
        return self._config['servo']['registers']['operating_mode']
    
    @property
    def reg_torque_enable(self) -> int:
        return self._config['servo']['registers']['torque_enable']
    
    @property
    def reg_current_limit(self) -> int:
        return self._config['servo']['registers']['current_limit']
    
    @property
    def reg_goal_current(self) -> int:
        return self._config['servo']['registers']['goal_current']
    
    @property
    def reg_pwm_limit(self) -> int:
        return self._config['servo']['registers']['pwm_limit']
    
    @property
    def reg_goal_pwm(self) -> int:
        return self._config['servo']['registers']['goal_pwm']
    
    @property
    def reg_present_pwm(self) -> int:
        return self._config['servo']['registers']['present_pwm']
    
    @property
    def reg_goal_position(self) -> int:
        return self._config['servo']['registers']['goal_position']
    
    @property
    def reg_present_position(self) -> int:
        return self._config['servo']['registers']['present_position']
    
    @property
    def reg_present_temperature(self) -> int:
        return self._config['servo']['registers']['present_temperature']
    
    @property
    def reg_present_current(self) -> int:
        return self._config['servo']['registers']['present_current']
    
    @property
    def reg_present_voltage(self) -> int:
        return self._config['servo']['registers']['present_voltage']
    
    @property
    def reg_hardware_error(self) -> int:
        return self._config['servo']['registers']['hardware_error']
    
    @property
    def reg_homing_offset(self) -> int:
        return self._config['servo']['registers']['homing_offset']
    
    @property
    def reg_return_delay_time(self) -> int:
        return self._config['servo']['registers']['return_delay_time']
    
    @property
    def reg_status_return_level(self) -> int:
        return self._config['servo']['registers']['status_return_level']
    
    # EEPROM optimization settings
    @property
    def eeprom_return_delay_time(self) -> int:
        return self._config['servo']['eeprom_settings']['return_delay_time']
    
    @property
    def eeprom_status_return_level(self) -> int:
        return self._config['servo']['eeprom_settings']['status_return_level']
    
    # Gripper configuration
    @property
    def grip_max(self) -> int:
        return self._config['gripper']['grip_max']
    
    @property
    def position_input_range(self) -> tuple:
        return tuple(self._config['gripper']['position_scaling']['input_range'])
    
    @property
    def position_output_range(self) -> tuple:
        return tuple(self._config['gripper']['position_scaling']['output_range'])
    
    @property
    def dex1_open_radians(self) -> float:
        return self._config['gripper']['dex1_mapping']['open_radians']
    
    @property
    def dex1_close_radians(self) -> float:
        return self._config['gripper']['dex1_mapping']['close_radians']
    
    @property
    def calibration_current(self) -> int:
        return self._config['gripper'].get('calibration', {}).get('current', self.max_current)
    
    @property
    def calibration_position(self) -> int:
        return self._config['gripper'].get('calibration', {}).get('position', -10000)
    
    @property
    def calibration_timeout(self) -> float:
        return self._config['gripper'].get('calibration', {}).get('timeout', 3.0)
    
    @property
    def calibration_auto_on_init(self) -> bool:
        return self._config['gripper'].get('calibration', {}).get('auto_on_init', False)
    
    @property
    def calibration_pwm(self) -> int:
        return self._config['gripper'].get('calibration', {}).get('pwm', 100)
    
    # Wave-following configuration
    @property
    def wave_following_enabled(self) -> bool:
        return self._config.get('wave_following', {}).get('enabled', True)
    
    @property
    def wave_history_window(self) -> int:
        return self._config.get('wave_following', {}).get('history_window', 10)
    
    @property
    def wave_variance_threshold(self) -> float:
        return self._config.get('wave_following', {}).get('variance_threshold', 2.0)
    
    @property
    def wave_position_tolerance(self) -> float:
        return self._config.get('wave_following', {}).get('position_tolerance', 5.0)
    
    @property
    def wave_mode_switch_delay(self) -> float:
        return self._config.get('wave_following', {}).get('mode_switch_delay', 0.5)
    
    # Health interface configuration
    @property
    def health_enabled(self) -> bool:
        return self._config.get('health_interface', {}).get('enabled', True)
    
    @property
    def health_topic(self) -> str:
        return self._config.get('health_interface', {}).get('topic', 'rt/gripper/health')
    
    @property
    def health_rate_hz(self) -> float:
        return self._config.get('health_interface', {}).get('rate_hz', 10.0)
    
    @property
    def health_qos_reliability(self) -> str:
        return self._config.get('health_interface', {}).get('qos_reliability', 'RELIABLE')
    
    # Error management configuration
    @property
    def error_auto_recovery(self) -> bool:
        return self._config.get('error_management', {}).get('auto_recovery', True)
    
    @property
    def error_max_attempts(self) -> int:
        return self._config.get('error_management', {}).get('max_attempts', 3)
    
    @property
    def error_use_reboot(self) -> bool:
        return self._config.get('error_management', {}).get('use_reboot', True)
    
    # Communication configuration
    @property
    def comm_device(self) -> str:
        return self._config['communication']['device']
    
    @property
    def comm_baudrate(self) -> int:
        return self._config['communication']['baudrate']
    
    @property
    def comm_protocol_version(self) -> float:
        return self._config['communication']['protocol_version']
    
    @property
    def comm_servo_id(self) -> int:
        return self._config['communication']['servo_id']
    
    @property
    def comm_timeout(self) -> float:
        return self._config['communication'].get('timeout', 0.5)
    
    @property
    def comm_smart_init(self) -> bool:
        return self._config['communication'].get('smart_init', True)
    
    # Logging configuration
    @property
    def log_enabled(self) -> bool:
        return self._config.get('logging', {}).get('enabled', True)
    
    @property
    def log_level(self) -> str:
        return self._config.get('logging', {}).get('level', 'INFO')
    
    def get_raw(self) -> Dict[str, Any]:
        """Get raw configuration dictionary"""
        return self._config


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from JSON file
    
    Args:
        config_path: Path to config file. If None, uses default config.
        
    Returns:
        Config object with typed access to parameters
        
    Raises:
        ConfigError: If config file not found or invalid
    """
    if config_path is None:
        # Use default config in same directory as driver
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config_default.json'
        )
    
    config_file = Path(config_path)
    if not config_file.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_file, 'r') as f:
            config_dict = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in config file: {e}")
    except Exception as e:
        raise ConfigError(f"Failed to load config file: {e}")
    
    # Basic validation
    if not validate_config(config_dict):
        raise ConfigError("Configuration validation failed")
    
    return Config(config_dict)


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate configuration structure
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if valid, False otherwise
    """
    # Check required top-level keys
    required_keys = ['servo', 'gripper', 'communication']
    for key in required_keys:
        if key not in config:
            print(f"Missing required configuration section: {key}")
            return False
    
    # Validate servo section
    if 'current_limits' not in config['servo']:
        print("Missing servo.current_limits")
        return False
    
    if 'temperature' not in config['servo']:
        print("Missing servo.temperature")
        return False
    
    if 'registers' not in config['servo']:
        print("Missing servo.registers")
        return False
    
    # Validate current limits
    limits = config['servo']['current_limits']
    if limits['holding'] > limits['movement']:
        print("Warning: holding_current > movement_current")
    
    if limits['movement'] > limits['max']:
        print("Warning: movement_current > max_current")
    
    if limits['max'] > limits['hardware_max']:
        print("Error: max_current > hardware_max_current")
        return False
    
    # Validate temperature thresholds
    temps = config['servo']['temperature']
    if temps['warning'] >= temps['advisory']:
        print("Warning: warning temp >= advisory temp")
    
    if temps['advisory'] >= temps['shutdown']:
        print("Warning: advisory temp >= shutdown temp")
    
    if temps['shutdown'] > temps['hardware_max']:
        print("Error: shutdown temp > hardware_max temp")
        return False
    
    return True


def get_servo_config(config: Config) -> Dict[str, Any]:
    """Get servo-specific configuration as dictionary"""
    return {
        'model': config.servo_model,
        'current_limits': {
            'holding': config.holding_current,
            'movement': config.movement_current,
            'max': config.max_current,
            'hardware_max': config.hardware_max_current
        },
        'temperature': {
            'warning': config.temp_warning,
            'advisory': config.temp_advisory,
            'shutdown': config.temp_shutdown,
            'hardware_max': config.temp_hardware_max
        }
    }


def get_gripper_config(config: Config) -> Dict[str, Any]:
    """Get gripper-specific configuration as dictionary"""
    return {
        'grip_max': config.grip_max,
        'position_scaling': {
            'input_range': config.position_input_range,
            'output_range': config.position_output_range
        },
        'dex1_mapping': {
            'open_radians': config.dex1_open_radians,
            'close_radians': config.dex1_close_radians
        }
    }
