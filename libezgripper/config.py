#!/usr/bin/env python3
"""
Configuration loader for EZGripper driver

Loads and validates JSON configuration files.
Provides typed access to configuration parameters.

Configuration Structure (cleaned):
- servo.dynamixel_settings: Hardware settings applied to servo (used by ezgripper_base_clean.py)
- servo.force_management: Force settings per GraspManager state (used by grasp_manager.py)
- servo.collision_detection: Stall/contact detection settings (used by grasp_manager.py)
- gripper: Geometry and calibration settings (used by multiple modules)
- communication: Serial communication settings (used by lib_robotis.py)
- telemetry: Telemetry publishing settings (used by ezgripper_dds_driver.py)
- logging: Logging settings (used by config.py)
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
    
    # =========================================================================
    # Servo Dynamixel Settings - Hardware settings applied during initialization
    # Used by: ezgripper_base_clean.py:_setup_position_control()
    # =========================================================================
    
    @property
    def dynamixel_settings(self) -> Dict[str, Any]:
        """Get all dynamixel_settings as a dictionary (used by ezgripper_base_clean.py)"""
        return self._config['servo'].get('dynamixel_settings', {})
    
    @property
    def operating_mode(self) -> int:
        """Operating mode from dynamixel_settings (Mode 5 = Current-based Position Control)"""
        return self.dynamixel_settings.get('operating_mode', 5)
    
    @property
    def current_limit(self) -> int:
        """Hardware current limit in units (used for current calculations)"""
        return self.dynamixel_settings.get('current_limit', 1600)
    
    @property
    def profile_velocity(self) -> int:
        """Profile velocity for smooth movement"""
        return self.dynamixel_settings.get('profile_velocity', 500)
    
    @property
    def profile_acceleration(self) -> int:
        """Profile acceleration for smooth movement"""
        return self.dynamixel_settings.get('profile_acceleration', 800)
    
    # =========================================================================
    # Force Management Settings - Used by GraspManager
    # Used by: grasp_manager.py:__init__()
    # =========================================================================
    
    @property
    def force_management(self) -> Dict[str, Any]:
        """Get all force_management settings as a dictionary"""
        return self._config['servo'].get('force_management', {})
    
    @property
    def moving_force_pct(self) -> float:
        """Force during MOVING state (closing/opening)"""
        return self.force_management.get('moving_force_pct', 50)
    
    @property
    def grasping_force_pct(self) -> float:
        """Force during GRASPING state (holding after contact)"""
        return self.force_management.get('grasping_force_pct', 20.0)
    
    @property
    def idle_force_pct(self) -> float:
        """Force during IDLE state"""
        return self.force_management.get('idle_force_pct', 10)
    
    # =========================================================================
    # Collision Detection Settings - Used by GraspManager
    # Used by: grasp_manager.py:__init__()
    # =========================================================================
    
    @property
    def collision_detection(self) -> Dict[str, Any]:
        """Get all collision_detection settings as a dictionary"""
        return self._config['servo'].get('collision_detection', {})
    
    @property
    def stall_tolerance_pct(self) -> float:
        """Position range tolerance for stall detection"""
        return self.collision_detection.get('stall_tolerance_pct', 2.0)
    
    @property
    def consecutive_samples_required(self) -> int:
        """Number of consecutive stagnant readings to confirm contact"""
        return self.collision_detection.get('consecutive_samples_required', 3)
    
    # =========================================================================
    # Gripper Configuration - Geometry and calibration
    # Used by: ezgripper_base_clean.py, ezgripper_dds_driver.py
    # =========================================================================
    
    @property
    def grip_max(self) -> int:
        """Maximum position range in servo units (0-2500 for practical range)"""
        return self._config['gripper']['grip_max']
    
    @property
    def max_open_percent(self) -> int:
        """Maximum opening percentage (100% GUI command -> max_open_percent hardware)"""
        return self._config['gripper']['position_scaling']['max_open_percent']
    
    @property
    def dex1_open_radians(self) -> float:
        """Dex1 hand radians for open position"""
        return self._config['gripper']['dex1_mapping']['open_radians']
    
    @property
    def dex1_close_radians(self) -> float:
        """Dex1 hand radians for close position"""
        return self._config['gripper']['dex1_mapping']['close_radians']
    
    @property
    def calibration_auto_on_init(self) -> bool:
        """Automatically run calibration on driver initialization"""
        return self._config['gripper'].get('calibration', {}).get('auto_on_init', False)
    
    @property
    def calibration_goto_target(self) -> int:
        """Target position for calibration goto sequence"""
        return self._config['gripper'].get('calibration', {}).get('goto_position_target', -300)
    
    @property
    def calibration_goto_effort(self) -> int:
        """Effort level for calibration"""
        return self._config['gripper'].get('calibration', {}).get('goto_position_effort', 30)
    
    @property
    def calibration_settle_position(self) -> int:
        """Position after calibration"""
        return self._config['gripper'].get('calibration', {}).get('settle_position', 35)
    
    # =========================================================================
    # Communication Configuration - Serial communication
    # Used by: lib_robotis.py
    # =========================================================================
    
    @property
    def comm_device(self) -> str:
        """Serial device path for USB connection to Dynamixel servo"""
        return self._config['communication']['device']
    
    @property
    def comm_baudrate(self) -> int:
        """Serial communication speed (1Mbps is standard for Dynamixel)"""
        return self._config['communication']['baudrate']
    
    @property
    def comm_protocol_version(self) -> float:
        """Dynamixel Protocol version (2.0 for MX-64)"""
        return self._config['communication']['protocol_version']
    
    @property
    def comm_servo_id(self) -> int:
        """Dynamixel servo ID"""
        return self._config['communication']['servo_id']
    
    @property
    def comm_timeout(self) -> float:
        """Serial communication timeout in seconds"""
        return self._config['communication'].get('timeout', 0.5)
    
    @property
    def comm_smart_init(self) -> bool:
        """Enable smart initialization with automatic device detection"""
        return self._config['communication'].get('smart_init', True)
    
    # =========================================================================
    # Telemetry Configuration - Telemetry publishing
    # Used by: ezgripper_dds_driver.py
    # =========================================================================
    
    @property
    def telemetry_enabled(self) -> bool:
        """Enable telemetry data publishing"""
        return self._config.get('telemetry', {}).get('enabled', True)
    
    @property
    def telemetry_topic_prefix(self) -> str:
        """DDS topic prefix for telemetry messages"""
        return self._config.get('telemetry', {}).get('topic_prefix', 'rt/gripper')
    
    @property
    def telemetry_rate_hz(self) -> int:
        """Telemetry publish rate in Hz"""
        return self._config.get('telemetry', {}).get('rate_hz', 30)
    
    @property
    def telemetry_debug_enabled(self) -> bool:
        """Enable debug telemetry"""
        return self._config.get('telemetry', {}).get('debug_enabled', False)
    
    # =========================================================================
    # Logging Configuration
    # =========================================================================
    
    @property
    def log_enabled(self) -> bool:
        """Enable system logging"""
        return self._config.get('logging', {}).get('enabled', True)
    
    @property
    def log_level(self) -> str:
        """Logging level: DEBUG, INFO, WARNING, ERROR"""
        return self._config.get('logging', {}).get('level', 'INFO')
    
    # =========================================================================
    # Raw Access
    # =========================================================================
    
    def get_raw(self) -> Dict[str, Any]:
        """Get raw configuration dictionary (used by modules that need direct access)"""
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
    if 'dynamixel_settings' not in config['servo']:
        print("Missing servo.dynamixel_settings")
        return False
    
    if 'force_management' not in config['servo']:
        print("Missing servo.force_management")
        return False
    
    if 'collision_detection' not in config['servo']:
        print("Missing servo.collision_detection")
        return False
    
    # Validate gripper section
    if 'grip_max' not in config['gripper']:
        print("Missing gripper.grip_max")
        return False
    
    # Validate communication section
    if 'device' not in config['communication']:
        print("Missing communication.device")
        return False
    
    return True
