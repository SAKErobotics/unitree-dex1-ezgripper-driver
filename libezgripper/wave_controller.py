#!/usr/bin/env python3
"""
Wave-Following Controller for EZGripper

Analyzes command stream to detect steady-state and modulate power.
Enables switching between movement and holding current.
"""

import time
from collections import deque
from typing import Optional


class WaveController:
    """
    Wave-following control algorithm
    
    Analyzes incoming position command stream to detect steady state.
    Switches between movement and holding current based on command variance.
    """
    
    def __init__(self, config):
        """
        Initialize wave controller
        
        Args:
            config: Config object with wave-following parameters
        """
        self.config = config
        
        # Command history
        self.history_window = config.wave_history_window
        self.position_history = deque(maxlen=self.history_window)
        self.timestamp_history = deque(maxlen=self.history_window)
        
        # Parameters
        self.variance_threshold = config.wave_variance_threshold
        self.position_tolerance = config.wave_position_tolerance
        self.mode_switch_delay = config.wave_mode_switch_delay
        
        # State
        self.current_mode = "moving"
        self.last_mode_switch = time.time()
        self.current_position = None
        
    def process_command(self, goal_position: float, current_position: Optional[float] = None) -> str:
        """
        Process incoming position command
        
        Args:
            goal_position: Commanded position (0-100%)
            current_position: Current actual position (optional)
            
        Returns:
            str: Recommended mode ("moving" or "holding")
        """
        # Update history
        self.position_history.append(goal_position)
        self.timestamp_history.append(time.time())
        
        if current_position is not None:
            self.current_position = current_position
        
        # Need enough history to analyze
        if len(self.position_history) < 3:
            return "moving"
        
        # Calculate variance of recent commands
        variance = self._calculate_variance()
        
        # Check if at goal position
        at_goal = self._is_at_goal(goal_position)
        
        # Determine if steady state
        is_steady = (variance < self.variance_threshold) and at_goal
        
        # Apply mode switch delay to prevent oscillation
        time_since_switch = time.time() - self.last_mode_switch
        
        if is_steady and self.current_mode == "moving":
            # Switch to holding if delay elapsed
            if time_since_switch >= self.mode_switch_delay:
                self.current_mode = "holding"
                self.last_mode_switch = time.time()
        
        elif not is_steady and self.current_mode == "holding":
            # Switch to moving immediately when movement detected
            self.current_mode = "moving"
            self.last_mode_switch = time.time()
        
        return self.current_mode
    
    def get_current_mode(self) -> str:
        """Get current control mode"""
        return self.current_mode
    
    def get_recommended_current(self) -> int:
        """
        Get recommended current limit based on mode
        
        Returns:
            int: Current limit in units
        """
        if self.current_mode == "holding":
            return self.config.holding_current
        else:
            return self.config.movement_current
    
    def reset(self):
        """Reset controller state"""
        self.position_history.clear()
        self.timestamp_history.clear()
        self.current_mode = "moving"
        self.last_mode_switch = time.time()
        self.current_position = None
    
    def _calculate_variance(self) -> float:
        """Calculate variance of position commands"""
        if len(self.position_history) < 2:
            return float('inf')
        
        positions = list(self.position_history)
        mean = sum(positions) / len(positions)
        variance = sum((p - mean) ** 2 for p in positions) / len(positions)
        
        return variance
    
    def _is_at_goal(self, goal_position: float) -> bool:
        """Check if current position is at goal"""
        if self.current_position is None:
            return False
        
        error = abs(self.current_position - goal_position)
        return error <= self.position_tolerance
