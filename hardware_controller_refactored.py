#!/usr/bin/env python3
"""
Refactored EZGripper Hardware Controller with proper method isolation

Each state machine function is independent and clearly isolated.
No massive inline code - clean, testable, maintainable design.
"""

import time
import logging
from typing import Optional, Tuple
from ezgripper.ezgripper_base import Gripper
from ezgripper.ezgripper_base import set_torque_mode
from ezgripper.driver import create_connection

class HardwareController:
    def __init__(self, device: str, side: str):
        # Basic initialization
        self.device = device
        self.side = side
        self.logger = logging.getLogger(f"hardware_{side}")
        
        # Hardware state
        self.gripper: Optional[Gripper] = None
        self.connection = None
        self.is_calibrated = False
        
        # Cached state
        self.current_position_pct = 50.0
        self.current_effort_pct = 30.0
        self.last_effort_pct = None
        self.expected_position_pct = 50.0  # Sacred NO-LOAD position tracking
        
        # State machine state
        self.control_mode = 'position'  # 'position' or 'torque'
        self.resistance_detected = False
        self.torque_mode_start_time = None
        self.torque_mode_entry_position = None
        self.last_mode_switch_time = 0
        
        # Configuration constants
        self.current_threshold = 200
        self.torque_pulse_duration = 0.5
        self.position_mode_effort = 100
        self.torque_hold_current = 800
        
        # Initialize hardware
        self._initialize_hardware()
        self._load_calibration()
        
        self.logger.info(f"Hardware controller ready: {side} side")
    
    def _initialize_hardware(self):
        """Initialize hardware connection"""
        self.logger.info(f"Connecting to EZGripper on {self.device}")
        
        try:
            self.connection = create_connection(dev_name=self.device, baudrate=57600)
            self.gripper = Gripper(self.connection, f'ezgripper_{self.side}', [1])
            
            # Test connection
            if not self.gripper.servos:
                raise Exception("No servos found")
                
            self.logger.info(f"Hardware connected: position {self.gripper.get_position()}%")
            
        except Exception as e:
            self.logger.error(f"Hardware connection failed: {e}")
            raise
    
    def _load_calibration(self):
        """Load calibration data"""
        try:
            zero_pos = self._load_calibration_from_file()
            if zero_pos is not None:
                self.gripper.zero_positions = [zero_pos]
                self.is_calibrated = True
                self.logger.info(f"Loaded calibration for {self.side}: {zero_pos}")
            else:
                self._auto_calibrate()
                
        except Exception as e:
            self.logger.error(f"Calibration failed: {e}")
            raise
    
    def send_command(self, position_pct: float, effort_pct: float):
        """
        Main command interface - delegates to state machine
        
        Clean, isolated method that delegates to appropriate state handlers.
        No inline state machine logic here.
        """
        try:
            # Update sacred position tracking
            self._update_expected_position(position_pct)
            
            # Delegate to current state handler
            if self.control_mode == 'position':
                self._handle_position_mode(position_pct, effort_pct)
            elif self.control_mode == 'torque':
                self._handle_torque_mode(position_pct, effort_pct)
            
            # Update cached state
            self._update_cached_state(position_pct, effort_pct)
            
            # Log state transition
            self._log_state_transition(position_pct, effort_pct)
            
        except Exception as e:
            self.logger.error(f"Error sending command: {e}")
    
    def _update_expected_position(self, position_pct: float):
        """Update sacred expected position tracking"""
        self.expected_position_pct = position_pct
    
    def _handle_position_mode(self, position_pct: float, effort_pct: float):
        """
        Handle POSITION MODE state
        
        Isolated method for position mode logic.
        Clear, testable, single responsibility.
        """
        # Check for resistance detection trigger
        if self._should_detect_resistance(position_pct):
            self._enter_torque_mode(position_pct)
        else:
            self._execute_position_control(position_pct, effort_pct)
    
    def _handle_torque_mode(self, position_pct: float, effort_pct: float):
        """
        Handle TORQUE MODE state
        
        Isolated method for torque mode logic.
        Clear, testable, single responsibility.
        """
        # Check for torque mode exit conditions
        if self._should_exit_torque_mode(position_pct):
            self._exit_torque_mode(position_pct, effort_pct)
        else:
            self._maintain_torque_hold()
    
    def _should_detect_resistance(self, position_pct: float) -> bool:
        """
        Determine if resistance should be detected
        
        Isolated decision logic - easy to test and modify.
        """
        if not self._is_actually_closing(position_pct):
            return False
            
        avg_current = self._get_average_current()
        return avg_current > self.current_threshold
    
    def _is_actually_closing(self, position_pct: float) -> bool:
        """
        Determine if gripper is actually closing
        
        Uses sacred expected position for decision making.
        """
        return position_pct < self.expected_position_pct - 1.0
    
    def _enter_torque_mode(self, position_pct: float):
        """
        Enter torque mode - isolated transition logic
        
        Clean, single responsibility method.
        """
        self.logger.info(f"Resistance detected at pos={position_pct:.1f}%, switching to TORQUE mode")
        
        # Update state machine state
        self.resistance_detected = True
        self.control_mode = 'torque'
        self.torque_mode_start_time = time.time()
        
        # Record entry position (information only, never corrupts sacred data)
        actual_pos = self.gripper.get_position()
        self.torque_mode_entry_position = actual_pos
        
        self.logger.info(f"Torque mode: resistance detected at {actual_pos:.1f}%")
    
    def _execute_position_control(self, position_pct: float, effort_pct: float):
        """
        Execute normal position control
        
        Isolated control logic - easy to test and modify.
        """
        # Set effort if needed
        if self.last_effort_pct != self.position_mode_effort:
            self.gripper.set_max_effort(int(self.position_mode_effort))
            self.last_effort_pct = self.position_mode_effort
        
        # Execute position command
        servo_pos = self.gripper.scale(int(position_pct), self.gripper.GRIP_MAX)
        self.gripper._goto_position(servo_pos)
    
    def _should_exit_torque_mode(self, position_pct: float) -> bool:
        """
        Determine if torque mode should be exited
        
        Isolated decision logic with clear conditions.
        """
        # Condition 1: Opening command detected
        if self._is_opening_command(position_pct):
            return True
        
        # Condition 2: Torque pulse timeout
        if self._is_torque_timeout():
            return True
        
        return False
    
    def _is_opening_command(self, position_pct: float) -> bool:
        """Check if command indicates opening"""
        entry_pos = self.torque_mode_entry_position or self.expected_position_pct
        return position_pct > entry_pos + 1.0
    
    def _is_torque_timeout(self) -> bool:
        """Check if torque mode has timed out"""
        if not self.torque_mode_start_time:
            return False
        return (time.time() - self.torque_mode_start_time) > self.torque_pulse_duration
    
    def _exit_torque_mode(self, position_pct: float, effort_pct: float):
        """
        Exit torque mode - isolated transition logic
        
        Clean, single responsibility method.
        """
        self.logger.info(f"Switching to POSITION mode")
        
        # Update state machine state
        self.control_mode = 'position'
        self.resistance_detected = False
        self.torque_mode_start_time = None
        self.torque_mode_entry_position = None
        
        # Switch servo back to position mode
        self._switch_to_position_mode()
        
        # Execute the command that triggered the exit
        self._execute_position_control(position_pct, effort_pct)
    
    def _switch_to_position_mode(self):
        """Switch servos from torque to position mode"""
        for servo in self.gripper.servos:
            set_torque_mode(servo, False)
    
    def _maintain_torque_hold(self):
        """
        Maintain torque hold state
        
        Isolated holding logic - easy to test and modify.
        """
        self._set_holding_torque()
    
    def _update_cached_state(self, position_pct: float, effort_pct: float):
        """Update cached state for reporting"""
        self.current_position_pct = self.expected_position_pct
        self.current_effort_pct = effort_pct
    
    def _log_state_transition(self, position_pct: float, effort_pct: float):
        """Log state transition information"""
        # Implementation would log current state, mode, etc.
        pass
    
    # Helper methods - properly isolated
    def _read_current(self) -> float:
        """Read motor current"""
        return self.gripper.read_word(40)
    
    def _update_current_window(self, current: float):
        """Update rolling current window"""
        self.current_samples.append(current)
        if len(self.current_samples) > 5:
            self.current_samples.pop(0)
    
    def _get_average_current(self) -> float:
        """Get average current from window"""
        return sum(self.current_samples) / len(self.current_samples) if self.current_samples else 0
    
    def _set_holding_torque(self):
        """Apply holding torque"""
        self.gripper.set_max_effort(self.torque_hold_current)
    
    # Calibration methods - properly isolated
    def _load_calibration_from_file(self) -> Optional[int]:
        """Load calibration from file"""
        # Implementation would load from file
        return None
    
    def _save_calibration(self, zero_pos: int):
        """Save calibration to file"""
        # Implementation would save to file
        pass
    
    def _auto_calibrate(self):
        """Perform auto-calibration"""
        # Implementation would perform calibration
        pass

# Usage example - clean and simple
def main():
    controller = HardwareController("/dev/ttyUSB0", "left")
    
    # Simple, clean interface
    controller.send_command(0.0, 100.0)   # Close
    controller.send_command(50.0, 100.0)  # Middle
    controller.send_command(100.0, 100.0) # Open

if __name__ == "__main__":
    main()
