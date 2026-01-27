#!/usr/bin/env python3
"""
Hardware Controller Module for EZGripper

Handles direct hardware control of EZGripper:
- Executes position and effort commands
- Reads actual position from hardware
- Manages calibration
- No DDS communication (uses interface module)
"""

import time
import logging
import json
import os
from typing import Optional

from libezgripper import create_connection, Gripper
from libezgripper.ezgripper_base import set_torque_mode


class EZGripperHardwareController:
    """
    Hardware controller for EZGripper.
    
    Manages direct hardware communication and control.
    Separate from DDS interface for modularity.
    """
    
    def __init__(self, device: str, side: str):
        """
        Initialize hardware controller.
        
        Args:
            device: Serial device path (e.g., /dev/ttyUSB0)
            side: Gripper side ('left' or 'right')
        """
        self.device = device
        self.side = side
        self.logger = logging.getLogger(f"hardware_{side}")
        
        # Hardware state
        self.gripper: Optional[Gripper] = None
        self.connection = None
        self.is_calibrated = False
        
        # Control state
        self.current_position_pct = 50.0
        self.current_effort_pct = 30.0
        self.last_effort_pct = None  # Track to avoid redundant set_max_effort
        
        # Hybrid control state
        self.control_mode = 'position'  # 'position' or 'torque'
        self.last_commanded_position = 50.0
        self.resistance_detected = False
        self.current_samples = []  # Rolling window for current monitoring
        self.current_threshold = 300  # Current units indicating resistance
        self.current_window_size = 5  # Samples to average
        self.torque_hold_current = 800  # 78% torque for holding in torque mode (800/1023 max)
        self.position_mode_effort = 100  # 100% effort for position control (safe - firmware limited)
        self.torque_mode_start_time = None  # Track when torque mode started
        self.torque_mode_timeout = 1.0  # Switch to position control after 1 second in torque mode
        
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
            test_pos = self.gripper.get_position()
            self.current_position_pct = test_pos
            self.logger.info(f"Hardware connected: position {test_pos:.1f}%")
            
        except Exception as e:
            self.logger.error(f"Hardware connection failed: {e}")
            raise
    
    def _load_calibration(self):
        """Load calibration from device config"""
        config_file = '/tmp/ezgripper_device_config.json'
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                
                # Get serial number for this side
                serial_key = f"{self.side}_serial"
                if serial_key in config and config[serial_key] != 'unknown':
                    serial = config[serial_key]
                    
                    # Get calibration for this serial number
                    if 'calibration' in config and serial in config['calibration']:
                        zero_pos = config['calibration'][serial]
                        self.gripper.zero_positions[0] = zero_pos
                        self.is_calibrated = True
                        self.logger.info(f"Loaded calibration for {serial}: {zero_pos}")
                        return
        except Exception as e:
            self.logger.warning(f"Failed to load calibration: {e}")
        
        # No calibration found - auto-calibrate
        self.logger.info("No calibration found, running auto-calibration...")
        self.calibrate()
    
    def _save_calibration(self, zero_position: float):
        """Save calibration to device config"""
        config_file = '/tmp/ezgripper_device_config.json'
        
        try:
            # Load existing config
            config = {}
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
            
            # Get serial number for this side
            serial_key = f"{self.side}_serial"
            if serial_key in config and config[serial_key] != 'unknown':
                serial = config[serial_key]
                
                # Initialize calibration dict if needed
                if 'calibration' not in config:
                    config['calibration'] = {}
                
                # Save zero position for this serial number
                config['calibration'][serial] = zero_position
                
                # Write back
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)
                
                self.logger.info(f"Saved calibration for {serial}: {zero_position}")
            else:
                self.logger.error(f"Cannot save calibration - no serial number for {self.side}")
            
        except Exception as e:
            self.logger.error(f"Failed to save calibration: {e}")
    
    def calibrate(self):
        """Run calibration sequence"""
        self.logger.info("Starting calibration...")
        
        try:
            # Perform calibration - closes gripper and sets zero position
            self.gripper.calibrate()
            
            # Save actual zero position to device config for persistence
            zero_pos = self.gripper.zero_positions[0]
            self._save_calibration(zero_pos)
            
            # Move to 50% open position to release from closed state
            self.gripper.goto_position(50, 100)
            
            # goto_position reduces effort to TORQUE_HOLD (13%) at the end, so reset to 100%
            self.gripper.set_max_effort(100)
            self.last_effort_pct = 100
            
            # Mark as calibrated
            self.is_calibrated = True
            self.logger.info(f"✅ Calibration complete (zero_position: {zero_pos})")
            return True
                
        except Exception as e:
            self.logger.error(f"Calibration failed: {e}")
            return False
    
    def execute_command(self, position_pct: float, effort_pct: float):
        """
        Execute position and effort command with hybrid position/torque control.
        
        Strategy:
        - Position mode: Normal operation, moving freely
        - Detect resistance: Current sustained above threshold
        - Switch to torque mode: Hold with high force
        - Return to position mode: When commanded position decreases (opening)
        
        Args:
            position_pct: Target position (0-100%)
            effort_pct: Target effort (0-100%)
        """
        try:
            servo_pos = self.gripper.scale(int(position_pct), self.gripper.GRIP_MAX)
            
            # Read current to detect resistance
            current = self._read_current()
            self._update_current_window(current)
            avg_current = self._get_average_current()
            
            # Detect if commanded position is changing
            is_closing = position_pct > self.last_commanded_position + 1.0  # 1% hysteresis - actively closing
            is_opening = position_pct < self.last_commanded_position - 1.0  # 1% hysteresis - actively opening
            self.last_commanded_position = position_pct
            
            # Mode switching logic
            if self.control_mode == 'position':
                # Simple logic: If closing and stopped (high current) → switch to torque mode
                # No endpoint exclusions needed - closing is closing everywhere
                if avg_current > self.current_threshold and is_closing:
                    self.logger.info(f"Resistance detected (current={avg_current:.0f}), switching to TORQUE mode")
                    self.control_mode = 'torque'
                    self.resistance_detected = True
                    self.torque_mode_start_time = time.time()  # Start timer for safety backoff
                    
                    # Switch to torque mode and hold
                    for servo in self.gripper.servos:
                        set_torque_mode(servo, True)
                    self._set_holding_torque()
                else:
                    # Normal position control with 100% effort
                    # Safe for continuous operation - position control is firmware limited
                    if self.last_effort_pct != self.position_mode_effort:
                        self.gripper.set_max_effort(int(self.position_mode_effort))
                        self.last_effort_pct = self.position_mode_effort
                    
                    self.gripper._goto_position(servo_pos)
                    
            elif self.control_mode == 'torque':
                # Check if we should return to position mode
                if is_opening:
                    # Opening command - switch to position mode immediately
                    self.logger.info(f"Opening command detected, switching to POSITION mode")
                    self.control_mode = 'position'
                    self.resistance_detected = False
                    self.torque_mode_start_time = None
                    
                    # Switch back to position mode
                    for servo in self.gripper.servos:
                        set_torque_mode(servo, False)
                    
                    # Execute the opening command with 100% effort
                    if self.last_effort_pct != self.position_mode_effort:
                        self.gripper.set_max_effort(int(self.position_mode_effort))
                        self.last_effort_pct = self.position_mode_effort
                    self.gripper._goto_position(servo_pos)
                    
                elif self.torque_mode_start_time and (time.time() - self.torque_mode_start_time) > self.torque_mode_timeout:
                    # Timeout - read current position and switch to position control
                    # This creates a pulsed holding pattern: torque (1s) → position → torque (1s) → position...
                    # Reduces average current while maintaining grip
                    current_pos = self.gripper.get_position()
                    self.logger.info(f"Torque mode timeout ({self.torque_mode_timeout}s), switching to POSITION control at {current_pos:.1f}%")
                    self.control_mode = 'position'
                    self.resistance_detected = False
                    self.torque_mode_start_time = None
                    
                    # Use goto_position to switch to position mode at current location
                    self.gripper.goto_position(int(current_pos), 100)
                    self.last_effort_pct = 100  # goto_position sets effort
                else:
                    # Continue holding in torque mode (800/1023 max)
                    self._set_holding_torque()
            
            # Update cached state
            self.current_position_pct = position_pct
            self.current_effort_pct = effort_pct
            
            # Debug logging - log all commands to diagnose endpoint issues
            self.logger.info(f"CMD: mode={self.control_mode}, pos={position_pct:.1f}%, servo_pos={servo_pos}, effort={self.last_effort_pct}%, current={avg_current:.0f}")
            
        except Exception as e:
            self.logger.error(f"Command execution failed: {e}")
    
    def read_position(self) -> float:
        """
        Read actual position from hardware.
        
        Returns:
            Current position percentage (0-100)
        """
        try:
            actual_position = self.gripper.get_position()
            self.current_position_pct = actual_position
            return actual_position
        except Exception as e:
            self.logger.error(f"Position read failed: {e}")
            return self.current_position_pct
    
    def get_cached_position(self) -> float:
        """
        Get cached position without hardware read.
        
        Returns:
            Cached position percentage (0-100)
        """
        return self.current_position_pct
    
    def get_cached_effort(self) -> float:
        """Get cached effort value"""
        return self.current_effort_pct
    
    def _read_current(self) -> float:
        """Read current from servo (load)"""
        try:
            # Read present load (address 40, 2 bytes)
            load = self.gripper.servos[0].read_word_signed(40)
            # Convert to absolute current value
            return abs(load)
        except Exception as e:
            self.logger.debug(f"Failed to read current: {e}")
            return 0.0
    
    def _update_current_window(self, current: float):
        """Update rolling window of current samples"""
        self.current_samples.append(current)
        if len(self.current_samples) > self.current_window_size:
            self.current_samples.pop(0)
    
    def _get_average_current(self) -> float:
        """Get average current from rolling window"""
        if not self.current_samples:
            return 0.0
        return sum(self.current_samples) / len(self.current_samples)
    
    def _set_holding_torque(self):
        """Set high torque for holding in torque mode"""
        try:
            # In torque mode, set goal torque (address 71, 2 bytes)
            # Positive value for closing direction
            for servo in self.gripper.servos:
                servo.write_word(71, self.torque_hold_current)
        except Exception as e:
            self.logger.error(f"Failed to set holding torque: {e}")
    
    def shutdown(self):
        """Clean shutdown - move to safe position"""
        self.logger.info("Shutting down hardware...")
        try:
            if self.gripper:
                self.gripper.goto_position(50, 30)
                time.sleep(1)
        except Exception as e:
            self.logger.error(f"Shutdown failed: {e}")
