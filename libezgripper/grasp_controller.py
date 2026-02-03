#!/usr/bin/env python3
"""
Advanced Grasp Controller with Force Curve and Temperature-Aware Holding

Implements sophisticated grasping algorithm:
1. Grasping Phase: Rapid force reduction during closure (max → 50%)
2. Holding Phase: Temperature-aware force management
"""

import time
from typing import Dict, Any, Optional, List
from collections import deque


class MovingWindowFilter:
    """5-cycle moving window filter for sensor data"""
    
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.position_window = deque(maxlen=window_size)
        self.current_window = deque(maxlen=window_size)
    
    def update(self, position: float, current: float):
        """Add new sample to windows"""
        self.position_window.append(position)
        self.current_window.append(current)
    
    def get_filtered_position(self) -> Optional[float]:
        """Get filtered position (average of window)"""
        if len(self.position_window) == 0:
            return None
        return sum(self.position_window) / len(self.position_window)
    
    def get_filtered_current(self) -> Optional[float]:
        """Get filtered current (average of window)"""
        if len(self.current_window) == 0:
            return None
        return sum(self.current_window) / len(self.current_window)
    
    def get_position_change(self) -> Optional[float]:
        """Get position change over window (last - first)"""
        if len(self.position_window) < 2:
            return None
        return abs(self.position_window[-1] - self.position_window[0])
    
    def is_window_full(self) -> bool:
        """Check if window has enough samples"""
        return len(self.position_window) >= self.window_size
    
    def reset(self):
        """Clear windows"""
        self.position_window.clear()
        self.current_window.clear()


class GraspState:
    """State machine for grasp phases"""
    CLOSING = "closing"           # Initial fast close
    GRASPING = "grasping"         # Contact detected, ramping down force
    GRASP_SET = "grasp_set"       # Position stable, grasp complete
    HOLDING = "holding"           # Temperature-aware holding
    RELEASED = "released"         # Grasp released


class GraspController:
    """
    Advanced grasp controller with force curve and temperature-aware holding
    
    Grasping Phase:
    - Detects contact (current spike or position stagnation)
    - Rapidly reduces force from max → 50% as position stabilizes
    - Uses 5-cycle moving window filter for smooth control
    - Monitors position change to detect grasp set
    
    Holding Phase:
    - Monitors temperature
    - Uses middle force as max grasp force
    - Holds at lower force, increases if needed
    - Prevents overheating
    """
    
    def __init__(self, 
                 max_force: float = 100,
                 grasp_set_force: float = 50,
                 holding_force_low: float = 30,
                 holding_force_mid: float = 50,
                 holding_force_high: float = 70,
                 temp_warning_threshold: float = 60,
                 temp_critical_threshold: float = 70,
                 position_stable_threshold: float = 2.0):
        """
        Args:
            max_force: Initial closing force (0-100%)
            grasp_set_force: Force when grasp is set (0-100%)
            holding_force_low: Low holding force (0-100%)
            holding_force_mid: Mid holding force (0-100%)
            holding_force_high: High holding force (0-100%)
            temp_warning_threshold: Temperature warning (°C)
            temp_critical_threshold: Temperature critical (°C)
            position_stable_threshold: Position change threshold (units)
        """
        self.max_force = max_force
        self.grasp_set_force = grasp_set_force
        self.holding_force_low = holding_force_low
        self.holding_force_mid = holding_force_mid
        self.holding_force_high = holding_force_high
        self.temp_warning_threshold = temp_warning_threshold
        self.temp_critical_threshold = temp_critical_threshold
        self.position_stable_threshold = position_stable_threshold
        
        # State
        self.state = GraspState.CLOSING
        self.filter = MovingWindowFilter(window_size=5)
        self.contact_detected_time = None
        self.grasp_set_time = None
        self.current_force = max_force
        
        # History for analysis
        self.force_history = []
        self.position_history = []
        self.current_history = []
        self.temp_history = []
    
    def update(self, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update grasp controller with new sensor data
        
        Args:
            sensor_data: Current sensor readings
            
        Returns:
            dict: Control output with force and state
        """
        position = sensor_data.get('position', 0)
        current = sensor_data.get('current', 0)
        temperature = sensor_data.get('temperature', 0)
        
        # Update filter
        self.filter.update(position, abs(current))
        
        # Get filtered values
        filtered_position = self.filter.get_filtered_position()
        filtered_current = self.filter.get_filtered_current()
        position_change = self.filter.get_position_change()
        
        # State machine
        if self.state == GraspState.CLOSING:
            return self._handle_closing(sensor_data, filtered_current, position_change)
        
        elif self.state == GraspState.GRASPING:
            return self._handle_grasping(sensor_data, filtered_position, position_change)
        
        elif self.state == GraspState.GRASP_SET:
            return self._handle_grasp_set(sensor_data)
        
        elif self.state == GraspState.HOLDING:
            return self._handle_holding(sensor_data, temperature)
        
        else:
            return {'force': 0, 'state': self.state, 'action': 'idle'}
    
    def _handle_closing(self, sensor_data: Dict[str, Any], 
                       filtered_current: Optional[float],
                       position_change: Optional[float]) -> Dict[str, Any]:
        """Handle CLOSING state - detect contact"""
        
        # Wait for filter to fill
        if not self.filter.is_window_full():
            return {
                'force': self.max_force,
                'state': self.state,
                'action': 'closing_fast',
                'message': 'Filling filter window...'
            }
        
        # Detect contact: current spike or position stagnation
        current_threshold = 150  # mA
        stagnation_threshold = 2  # units
        
        contact_detected = False
        reason = ""
        
        if filtered_current and filtered_current > current_threshold:
            contact_detected = True
            reason = f"current spike ({filtered_current:.1f}mA)"
        
        if position_change is not None and position_change < stagnation_threshold:
            contact_detected = True
            reason = f"position stagnation (Δ={position_change:.1f})"
        
        if contact_detected:
            self.state = GraspState.GRASPING
            self.contact_detected_time = time.time()
            print(f"  🤏 Contact detected: {reason}")
            print(f"  🔽 Starting force reduction: {self.max_force}% → {self.grasp_set_force}%")
            return {
                'force': self.max_force,
                'state': self.state,
                'action': 'contact_detected',
                'reason': reason
            }
        
        return {
            'force': self.max_force,
            'state': self.state,
            'action': 'closing_fast'
        }
    
    def _handle_grasping(self, sensor_data: Dict[str, Any],
                        filtered_position: Optional[float],
                        position_change: Optional[float]) -> Dict[str, Any]:
        """Handle GRASPING state - rapid force reduction during closure"""
        
        if not self.contact_detected_time:
            self.contact_detected_time = time.time()
        
        # Time since contact
        elapsed = time.time() - self.contact_detected_time
        
        # Force reduction curve: exponential decay from max to grasp_set
        # Fast initial reduction, then slower
        # Target: reach grasp_set_force in ~0.5 seconds
        decay_rate = 3.0  # Controls speed of decay
        force_range = self.max_force - self.grasp_set_force
        
        # Exponential decay: F(t) = grasp_set + (max - grasp_set) * e^(-decay_rate * t)
        self.current_force = self.grasp_set_force + force_range * (2.71828 ** (-decay_rate * elapsed))
        
        # Also factor in position change - faster reduction if position stable
        if position_change is not None:
            # If position nearly stable, accelerate to grasp_set_force
            if position_change < self.position_stable_threshold:
                # Accelerate decay
                self.current_force = min(self.current_force, 
                                        self.grasp_set_force + (self.current_force - self.grasp_set_force) * 0.5)
        
        # Record history
        self.force_history.append(self.current_force)
        if filtered_position:
            self.position_history.append(filtered_position)
        
        # Check if grasp is set (position stable)
        if position_change is not None and position_change < 0.5:  # Very stable
            self.state = GraspState.GRASP_SET
            self.grasp_set_time = time.time()
            grasp_duration = elapsed
            print(f"  ✅ Grasp set in {grasp_duration:.3f}s at position {filtered_position:.1f}%")
            print(f"  🔒 Final force: {self.current_force:.1f}%")
            return {
                'force': self.grasp_set_force,
                'state': self.state,
                'action': 'grasp_set',
                'grasp_duration': grasp_duration
            }
        
        return {
            'force': self.current_force,
            'state': self.state,
            'action': 'ramping_down_force',
            'elapsed': elapsed,
            'position_change': position_change
        }
    
    def _handle_grasp_set(self, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle GRASP_SET state - transition to holding"""
        
        # Transition to holding immediately
        self.state = GraspState.HOLDING
        print(f"  🫱 Transitioning to holding mode")
        print(f"  📊 Force range: {self.holding_force_low}% - {self.holding_force_mid}% - {self.holding_force_high}%")
        
        return {
            'force': self.holding_force_low,  # Start at low force
            'state': self.state,
            'action': 'transition_to_holding'
        }
    
    def _handle_holding(self, sensor_data: Dict[str, Any], temperature: float) -> Dict[str, Any]:
        """
        Handle HOLDING state - temperature-aware force management
        
        Strategy:
        - Normally hold at low force (30%)
        - If object slips (position change), increase to mid force (50%)
        - Monitor temperature:
          - Normal (<60°C): Can use up to mid force
          - Warning (60-70°C): Reduce to low force
          - Critical (>70°C): Reduce force further or release
        """
        
        position = sensor_data.get('position', 0)
        current = abs(sensor_data.get('current', 0))
        
        # Record temperature history
        self.temp_history.append(temperature)
        
        # Get position change from filter
        position_change = self.filter.get_position_change()
        
        # Determine target force based on temperature and slip
        target_force = self.holding_force_low  # Default: low force
        reason = "normal_hold"
        
        # Check for slip (position change while holding)
        if position_change is not None and position_change > 3.0:
            # Object slipping, increase force
            if temperature < self.temp_warning_threshold:
                target_force = self.holding_force_mid
                reason = "slip_detected_increase_force"
            else:
                # Temperature high, can't increase force much
                target_force = min(self.holding_force_mid, self.holding_force_low + 10)
                reason = "slip_detected_but_temp_high"
        
        # Temperature management
        if temperature >= self.temp_critical_threshold:
            # Critical temperature - reduce force significantly
            target_force = min(target_force, self.holding_force_low * 0.7)
            reason = "critical_temp_reduce_force"
            print(f"  ⚠️  CRITICAL TEMP: {temperature}°C - Reducing force to {target_force:.1f}%")
        
        elif temperature >= self.temp_warning_threshold:
            # Warning temperature - limit force
            target_force = min(target_force, self.holding_force_low)
            reason = "warning_temp_limit_force"
            if len(self.temp_history) % 10 == 0:  # Print occasionally
                print(f"  🌡️  Temp warning: {temperature}°C - Limiting force to {target_force:.1f}%")
        
        # Smooth force changes
        if hasattr(self, '_last_holding_force'):
            # Gradual change
            force_diff = target_force - self._last_holding_force
            self.current_force = self._last_holding_force + force_diff * 0.3  # 30% step
        else:
            self.current_force = target_force
        
        self._last_holding_force = self.current_force
        
        return {
            'force': self.current_force,
            'state': self.state,
            'action': reason,
            'temperature': temperature,
            'position_change': position_change,
            'current': current
        }
    
    def reset(self):
        """Reset controller to initial state"""
        self.state = GraspState.CLOSING
        self.filter.reset()
        self.contact_detected_time = None
        self.grasp_set_time = None
        self.current_force = self.max_force
        self.force_history.clear()
        self.position_history.clear()
        self.current_history.clear()
        self.temp_history.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get grasp statistics"""
        stats = {
            'state': self.state,
            'current_force': self.current_force,
        }
        
        if self.contact_detected_time:
            stats['time_since_contact'] = time.time() - self.contact_detected_time
        
        if self.grasp_set_time:
            stats['time_since_grasp_set'] = time.time() - self.grasp_set_time
            stats['grasp_duration'] = self.grasp_set_time - self.contact_detected_time
        
        if self.temp_history:
            stats['avg_temperature'] = sum(self.temp_history) / len(self.temp_history)
            stats['max_temperature'] = max(self.temp_history)
        
        return stats
