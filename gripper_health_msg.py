#!/usr/bin/env python3
"""
DDS message definition for gripper health state

Simple dataclass for health telemetry publishing.
"""

from dataclasses import dataclass


@dataclass
class GripperHealthState:
    """Gripper health telemetry message"""
    
    timestamp: float          # Unix timestamp
    servo_id: int            # Servo ID
    
    # Hardware status
    temperature: float       # °C
    current: float          # mA
    voltage: float          # V
    hardware_error: int     # Error code from register 70
    
    # Position & movement
    present_position: int   # Current position
    goal_position: int      # Commanded position
    is_moving: bool         # Is servo moving
    
    # Thermal management
    temperature_trend: str  # "rising", "falling", "stable"
    temperature_rate: float # °C/sec
    
    # Control state
    control_mode: str       # "moving" or "holding"
    current_limit: int      # Current limit setting
