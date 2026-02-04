#!/usr/bin/env python3
"""
GripperTelemetry Message Definition

Internal gripper state telemetry for monitoring, debugging, and AI learning.
Published at 30Hz (control loop rate) on separate DDS topic from xr_teleoperate interface.

This provides real internal state, not command echo.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GripperTelemetry:
    """
    Internal gripper state telemetry.
    
    Published at 30Hz to rt/gripper/{side}/telemetry topic.
    Provides algorithmic state and health metrics for monitoring and learning.
    """
    
    # Timestamp
    timestamp: float
    
    # Position Tracking (algorithmic)
    commanded_position_pct: float       # What DDS commanded (0-100%)
    actual_position_pct: float          # Real hardware position (0-100%)
    position_error_pct: float           # commanded - actual
    
    # GraspManager State Machine
    grasp_state: str                    # "idle", "moving", "contact", "grasping"
    managed_effort_pct: float           # GraspManager's computed effort (0-100%)
    commanded_effort_pct: float         # DDS commanded effort (0-100%)
    
    # Contact Detection Algorithm Status
    contact_detected: bool              # Final contact detection result
    contact_sample_count: int           # Consecutive samples meeting criteria (0-N)
    current_threshold_exceeded: bool    # Current > threshold
    position_stagnant: bool             # Position change < threshold
    
    # Health Monitoring (high-level)
    temperature_c: float                # Servo temperature (°C)
    current_ma: float                   # Current draw (mA)
    voltage_v: float                    # Supply voltage (V)
    is_moving: bool                     # Servo moving flag
    temperature_trend: str              # "rising", "falling", "stable"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'timestamp': self.timestamp,
            'position': {
                'commanded_pct': self.commanded_position_pct,
                'actual_pct': self.actual_position_pct,
                'error_pct': self.position_error_pct
            },
            'grasp_manager': {
                'state': self.grasp_state,
                'managed_effort_pct': self.managed_effort_pct,
                'commanded_effort_pct': self.commanded_effort_pct
            },
            'contact_detection': {
                'detected': self.contact_detected,
                'sample_count': self.contact_sample_count,
                'current_threshold_exceeded': self.current_threshold_exceeded,
                'position_stagnant': self.position_stagnant
            },
            'health': {
                'temperature_c': self.temperature_c,
                'current_ma': self.current_ma,
                'voltage_v': self.voltage_v,
                'is_moving': self.is_moving,
                'temperature_trend': self.temperature_trend
            }
        }
    
    @classmethod
    def from_driver_state(cls, driver):
        """
        Create telemetry from driver state.
        
        Args:
            driver: EZGripperDDSDriver instance with current state
            
        Returns:
            GripperTelemetry instance
        """
        import time
        
        # Get position data
        commanded_pos = driver.latest_command.position_pct if driver.latest_command else 0.0
        actual_pos = driver.actual_position_pct
        position_error = commanded_pos - actual_pos
        
        # Get GraspManager state
        grasp_state = driver.grasp_manager.state.value if hasattr(driver.grasp_manager, 'state') else "unknown"
        
        # Get effort data
        managed_effort = driver.managed_effort if hasattr(driver, 'managed_effort') else 0.0
        commanded_effort = driver.latest_command.effort_pct if driver.latest_command else 0.0
        
        # Get contact detection state
        gm = driver.grasp_manager
        contact_detected = False
        contact_sample_count = 0
        current_threshold_exceeded = False
        position_stagnant = False
        
        if hasattr(gm, 'contact_sample_count'):
            contact_sample_count = gm.contact_sample_count
            contact_detected = contact_sample_count >= gm.CONSECUTIVE_SAMPLES_REQUIRED
            
            # Check current threshold (need sensor data)
            if driver.current_sensor_data:
                current_ma = abs(driver.current_sensor_data.get('current', 0))
                current_pct = (current_ma / 1600.0) * 100.0
                current_threshold_exceeded = current_pct > gm.CURRENT_THRESHOLD_PCT
                
                # Check position stagnation
                if hasattr(gm, 'last_position') and gm.last_position is not None:
                    position_change = abs(actual_pos - gm.last_position)
                    position_stagnant = position_change < gm.STAGNATION_THRESHOLD
        
        # Get health data
        temperature_c = -1.0
        current_ma = 0.0
        voltage_v = 0.0
        is_moving = False
        temperature_trend = "unknown"
        
        if driver.current_sensor_data:
            temperature_c = driver.current_sensor_data.get('temperature', -1.0)
            current_ma = abs(driver.current_sensor_data.get('current', 0.0))
            voltage_v = driver.current_sensor_data.get('voltage', 0.0)
            is_moving = driver.current_sensor_data.get('is_moving', False)
        
        if hasattr(driver, 'health_monitor'):
            temperature_trend = driver.health_monitor.get_temperature_trend()
        
        return cls(
            timestamp=time.time(),
            commanded_position_pct=commanded_pos,
            actual_position_pct=actual_pos,
            position_error_pct=position_error,
            grasp_state=grasp_state,
            managed_effort_pct=managed_effort,
            commanded_effort_pct=commanded_effort,
            contact_detected=contact_detected,
            contact_sample_count=contact_sample_count,
            current_threshold_exceeded=current_threshold_exceeded,
            position_stagnant=position_stagnant,
            temperature_c=temperature_c,
            current_ma=current_ma,
            voltage_v=voltage_v,
            is_moving=is_moving,
            temperature_trend=temperature_trend
        )
