#!/usr/bin/env python3
"""
Health Monitor for EZGripper

Pure data collection module - no decision making.
Monitors temperature, current, voltage, position.
Calculates temperature trends.
"""

import time
from collections import deque
from typing import Dict, Any


class HealthMonitor:
    """
    Health monitoring for servo
    
    Collects telemetry data without making decisions.
    Provides temperature trend analysis.
    """
    
    def __init__(self, servo, config):
        """
        Initialize health monitor
        
        Args:
            servo: Robotis_Servo instance
            config: Config object with register addresses
        """
        self.servo = servo
        self.config = config
        
        # Temperature history for trend calculation
        self.temp_history = deque(maxlen=10)
        self.temp_timestamps = deque(maxlen=10)
        
    def read_temperature(self) -> float:
        """Read current temperature in Celsius"""
        try:
            temp = self.servo.read_address(self.config.reg_present_temperature)[0]
            
            # Update history
            self.temp_history.append(temp)
            self.temp_timestamps.append(time.time())
            
            return float(temp)
        except Exception as e:
            return -1.0  # Error indicator
    
    def read_current(self) -> float:
        """Read current draw in mA"""
        try:
            # Current is 2 bytes, signed
            data = self.servo.read_address(self.config.reg_present_current, 2)
            current_raw = data[0] + (data[1] << 8)
            
            # Handle signed 16-bit
            if current_raw >= 32768:
                current_raw -= 65536
            
            # Convert to mA (unit is 1 mA for MX-64)
            return float(current_raw)
        except Exception as e:
            return -1.0
    
    def read_voltage(self) -> float:
        """Read supply voltage in V"""
        try:
            # Voltage is 2 bytes
            data = self.servo.read_address(self.config.reg_present_voltage, 2)
            voltage_raw = data[0] + (data[1] << 8)
            
            # Convert to volts (unit is 0.1V)
            return voltage_raw * 0.1
        except Exception as e:
            return -1.0
    
    def read_position(self) -> int:
        """Read current position"""
        try:
            return self.servo.read_encoder()
        except Exception as e:
            return 0
    
    def read_goal_position(self) -> int:
        """Read goal position"""
        try:
            data = self.servo.read_address(self.config.reg_goal_position, 4)
            position = data[0] + (data[1] << 8) + (data[2] << 16) + (data[3] << 24)
            
            # Handle signed 32-bit
            if position >= 2147483648:
                position -= 4294967296
            
            return position
        except Exception as e:
            return 0
    
    def is_moving(self) -> bool:
        """Check if servo is currently moving"""
        try:
            # Register 122 (Moving) - 1 byte
            moving = self.servo.read_address(122)[0]
            return bool(moving)
        except Exception as e:
            return False
    
    def get_temperature_trend(self) -> str:
        """
        Calculate temperature trend
        
        Returns:
            "rising", "falling", or "stable"
        """
        if len(self.temp_history) < 3:
            return "stable"
        
        # Calculate rate of change over last few readings
        recent_temps = list(self.temp_history)[-5:]
        
        if len(recent_temps) < 2:
            return "stable"
        
        # Simple linear trend
        avg_change = (recent_temps[-1] - recent_temps[0]) / len(recent_temps)
        
        if avg_change > 0.5:  # Rising more than 0.5°C per reading
            return "rising"
        elif avg_change < -0.5:  # Falling more than 0.5°C per reading
            return "falling"
        else:
            return "stable"
    
    def get_temperature_rate(self) -> float:
        """
        Calculate temperature change rate in °C/sec
        
        Returns:
            Rate of temperature change (positive = rising)
        """
        if len(self.temp_history) < 2:
            return 0.0
        
        # Use last 5 readings for rate calculation
        temps = list(self.temp_history)[-5:]
        times = list(self.temp_timestamps)[-5:]
        
        if len(temps) < 2:
            return 0.0
        
        # Calculate rate
        temp_delta = temps[-1] - temps[0]
        time_delta = times[-1] - times[0]
        
        if time_delta > 0:
            return temp_delta / time_delta
        else:
            return 0.0
    
    def get_health_snapshot(self) -> Dict[str, Any]:
        """
        Get complete health snapshot
        
        Returns:
            Dictionary with all health data
        """
        return {
            "timestamp": time.time(),
            "temperature": self.read_temperature(),
            "current": self.read_current(),
            "voltage": self.read_voltage(),
            "position": self.read_position(),
            "goal_position": self.read_goal_position(),
            "is_moving": self.is_moving(),
            "temperature_trend": self.get_temperature_trend(),
            "temperature_rate": self.get_temperature_rate()
        }
