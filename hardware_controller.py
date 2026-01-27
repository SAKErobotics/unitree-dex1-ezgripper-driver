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
import time
import json
import os
import threading
from typing import Optional, Tuple

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
        
        # Cached state
        self.current_position_pct = 50.0  # Cached position for reporting
        self.current_effort_pct = 30.0
        self.last_effort_pct = None  # Track to avoid redundant set_max_effort
        self.expected_position_pct = 50.0  # Expected NO-LOAD position based on commands (never corrupted by measurements)
        
        # Hybrid control state
        self.control_mode = 'position'  # 'position', 'torque', or 'backoff_torque'
        self.last_commanded_position = 50.0
        self.resistance_detected = False
        self.current_samples = []  # Rolling window for current monitoring
        self.current_threshold = 200  # Current units indicating resistance (lifetime reliable for new and aged servos)
        self.current_window_size = 2  # Samples to average (faster response)
        self.torque_hold_current = 800  # 78% torque for holding in torque mode (800/1023 max)
        self.backoff_torque_current = 133  # 13% torque for back-off holding (133/1023)
        self.position_mode_effort = 100  # 100% effort for position control (safe - firmware limited)
        self.torque_mode_start_time = None  # Track when torque mode started
        self.torque_mode_entry_position = None  # Track position when entering torque mode
        self.torque_pulse_duration = 0.5  # Hold in torque for 0.5s then back-off
        self.backoff_mode_timeout = 5.0  # Exit backoff after 5s if no opening command
        self.last_mode_switch_time = 0  # Track last mode switch for cooldown
        self.mode_switch_cooldown = 0.5  # Cooldown period after mode switch to prevent rapid cycling
        self.backoff_entry_position = None  # Track position when entering back-off mode
        self.backoff_mode_start_time = None  # Track when backoff mode started
        
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
                
                # Get serial number for this side, or use side name as fallback
                serial_key = f"{self.side}_serial"
                if serial_key in config and config[serial_key] != 'unknown':
                    key = config[serial_key]
                else:
                    # Use side name as key if no serial number
                    key = self.side
                
                # Get calibration for this key
                if 'calibration' in config and key in config['calibration']:
                    zero_pos = config['calibration'][key]
                    self.gripper.zero_positions[0] = zero_pos
                    self.is_calibrated = True
                    self.logger.info(f"Loaded calibration for {key}: {zero_pos}")
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
            
            # Get serial number for this side, or use side name as fallback
            serial_key = f"{self.side}_serial"
            if serial_key in config and config[serial_key] != 'unknown':
                key = config[serial_key]
            else:
                # Use side name as key if no serial number
                key = self.side
            
            # Initialize calibration dict if needed
            if 'calibration' not in config:
                config['calibration'] = {}
            
            # Save zero position for this key
            config['calibration'][key] = zero_position
            
            # Write back
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            self.logger.info(f"Saved calibration for {key}: {zero_position}")
            
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
            self.gripper.move_with_torque_management(50, 100)
            
            # goto_position reduces effort to TORQUE_HOLD (13%) at the end, so reset to 100%
            self.gripper.set_max_effort(100)
            self.last_effort_pct = 100
            
            # Initialize cached state and expected position from calibration
            self.current_position_pct = 50.0
            self.expected_position_pct = 50.0  # Establish foundational NO-LOAD position at calibration
            
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
            
            # Debug: Track control mode at function entry
            self.logger.debug(f"Command entry: mode={self.control_mode}, cmd={position_pct:.1f}%, tracked={self.expected_position_pct:.1f}%")
            
            # Read current to detect resistance
            current = self._read_current()
            self._update_current_window(current)
            avg_current = self._get_average_current()
            
            # Detect if commanded position is changing relative to ACTUAL position
            # This is critical - we compare against where the gripper actually is, not where we commanded it
            # Closing = position_pct DECREASING (going toward 0%), Opening = position_pct INCREASING (going toward 100%)
            
            # Sacred NO-LOAD relationships are NEVER reset - differences provide information, not corruption
            
            is_closing = position_pct < self.expected_position_pct - 1.0  # 1% hysteresis - actively closing
            is_opening = position_pct > self.expected_position_pct + 1.0  # 1% hysteresis - actively opening
            
            # Debug: Track closing/opening logic
            self.logger.debug(f"Direction logic: cmd={position_pct:.1f}%, tracked={self.expected_position_pct:.1f}%, is_closing={is_closing}, is_opening={is_opening}")
            
            # Mode switching logic
            if self.control_mode == 'position':
                # Detect resistance during closing (validated threshold works for new and aged servos)
                # Only detect resistance when actually closing toward objects (< 65% position)
                # This prevents false triggers during free space movement and full-open torque grasps
                # Use instant current reading for faster response, avg for stability
                if is_closing and position_pct < 65.0 and (current > self.current_threshold or avg_current > self.current_threshold):
                    self.logger.debug(f"Resistance detection trigger: is_closing={is_closing}, current={current}, avg_current={avg_current}, threshold={self.current_threshold}")
                    self.logger.info(f"Resistance detected (instant={current}, avg={avg_current}) at pos={position_pct:.1f}%, switching to TORQUE mode")
                    self.resistance_detected = True
                    self.control_mode = 'torque'
                    self.torque_mode_start_time = time.time()
                    
                    # Use commanded position as entry reference to prevent manual interference
                    # Actual position can change if user manually holds gripper open
                    self.torque_mode_entry_position = position_pct
                    # DON'T update expected_position_pct - keep tracking commanded positions
                    self.logger.info(f"Torque mode: resistance detected at commanded position {position_pct:.1f}%")
                else:
                    # Check if resistance detection was blocked by position threshold
                    if is_closing and position_pct >= 65.0 and (current > self.current_threshold or avg_current > self.current_threshold):
                        self.logger.debug(f"Resistance detection blocked by position threshold: pos={position_pct:.1f}% >= 65.0%, current={current}")
                    
                    # Normal position control with 100% effort
                    # Safe for continuous operation - position control is firmware limited
                    if self.last_effort_pct != self.position_mode_effort:
                        self.gripper.set_max_effort(int(self.position_mode_effort))
                        self.last_effort_pct = self.position_mode_effort
                    
                    self.gripper._goto_position(servo_pos)
                    
                    # Position tracking handled at end of function (line 302)
                    
            elif self.control_mode == 'torque':
                # In torque mode: hold for 0.5s then return to position
                # Exit immediately if commanded position is more open than entry position
                # IMPORTANT: Ignore all other commands to prevent torque pumping
                entry_pos = self.torque_mode_entry_position if self.torque_mode_entry_position else self.expected_position_pct
                is_more_open_than_entry = position_pct > entry_pos + 1.0  # 1% hysteresis
                
                # Debug: Log entry position comparison to detect manual interference
                actual_pos = self.gripper.get_position()
                self.logger.debug(f"Torque mode check: cmd={position_pct:.1f}%, entry={entry_pos:.1f}%, actual={actual_pos:.1f}%, is_opening={is_more_open_than_entry}")
                
                if is_more_open_than_entry:
                    # Opening command - switch to position mode immediately
                    self.logger.info(f"Opening command detected, switching to POSITION mode")
                    self.control_mode = 'position'
                    self.resistance_detected = False
                    self.torque_mode_start_time = None
                    self.last_mode_switch_time = time.time()
                    
                    # Switch back to position mode
                    for servo in self.gripper.servos:
                        set_torque_mode(servo, False)
                    
                    # Execute the opening command with 100% effort
                    if self.last_effort_pct != self.position_mode_effort:
                        self.gripper.set_max_effort(int(self.position_mode_effort))
                        self.last_effort_pct = self.position_mode_effort
                    self.gripper._goto_position(servo_pos)
                    
                elif self.torque_mode_start_time:
                    # Check timeout for back-off transition
                    time_in_torque = time.time() - self.torque_mode_start_time
                    self.logger.debug(f"Torque mode timeout check: time_in_torque={time_in_torque:.2f}s, threshold={self.torque_pulse_duration}s")
                    
                    if time_in_torque > self.torque_pulse_duration:
                        # 0.5s timeout - switch to BACKOFF TORQUE mode with 13% torque
                        # This provides back-off holding instead of returning to position mode
                        # Use torque entry position to prevent manual interference
                        self.logger.info(f"Torque pulse complete ({self.torque_pulse_duration}s), switching to BACKOFF TORQUE mode at {self.torque_mode_entry_position:.1f}% with 13% torque")
                        self.control_mode = 'backoff_torque'
                        self.backoff_entry_position = self.torque_mode_entry_position
                        self.last_mode_switch_time = time.time()
                        
                        # Reduce torque to 13% for back-off holding
                        self.gripper.set_max_effort(self.backoff_torque_current)
                        self.last_effort_pct = self.backoff_torque_current
                    else:
                        # Timeout not reached yet, continue holding in torque mode
                        self.logger.debug(f"Continuing torque mode: {time_in_torque:.2f}s elapsed, {self.torque_pulse_duration - time_in_torque:.2f}s remaining")
                        self._set_holding_torque()
                    
                else:
                    # Non-opening command received while in torque mode
                    # IGNORE the command to prevent torque pumping
                    # Just maintain current torque hold without reapplying commands
                    self.logger.debug(f"Ignoring non-opening command ({position_pct:.1f}%) while in torque mode - preventing torque pumping")
                    # EARLY RETURN - skip all remaining command processing
                    return
            
            elif self.control_mode == 'backoff_torque':
                # In back-off torque mode: hold with 13% torque
                # In back-off mode: NEVER exit during continuous closing sequence
                # Only exit if there's a significant pause followed by new closing attempt
                # This prevents cycling during normal closing operations
                self.logger.debug(f"Backoff mode: maintaining 13% torque hold (cmd={position_pct:.1f}%, will not exit during continuous closing)")
                
                # NOTE: We intentionally do NOT exit backoff mode during closing
                # The user must issue an opening command to exit backoff mode
                # This provides stable holding without cycling
                
                # EARLY RETURN - skip all remaining command processing
                return
            
            # Position tracking is deterministic based on commands after calibration
            # Never reset position tracking - it follows command sequence
            if self.control_mode == 'position':
                self.expected_position_pct = position_pct  # Track command sequence deterministically
            
            # Update cached state
            self.current_position_pct = self.expected_position_pct
            self.current_effort_pct = effort_pct
            
            # Comprehensive logging - track complete command flow
            zero_pos = self.gripper.zero_positions[0] if self.gripper and self.gripper.zero_positions else 0
            
            # Input command analysis
            if position_pct <= 5.0:
                cmd_type = "CLOSE"
            elif position_pct >= 95.0:
                cmd_type = "OPEN"
            else:
                cmd_type = f"POSITION {position_pct:.1f}%"
            
            # Control decision analysis
            if self.control_mode == 'position':
                if is_closing:
                    control_action = "CLOSING (position mode)"
                elif is_opening:
                    control_action = "OPENING (position mode)"
                else:
                    control_action = "HOLDING (position mode)"
            elif self.control_mode == 'torque':
                control_action = f"HOLDING (torque mode, entry={self.torque_mode_entry_position:.1f}%)"
            elif self.control_mode == 'backoff_torque':
                control_action = f"HOLDING (backoff torque mode, entry={self.backoff_entry_position:.1f}%, 13% torque)"
            else:
                control_action = "UNKNOWN MODE"
            
            # Log complete flow
            self.logger.info(f"INPUT: {cmd_type} | TRACKED: {self.expected_position_pct:.1f}% | {control_action} | SERVO: pos={servo_pos}+{zero_pos}={servo_pos+zero_pos}, effort={self.last_effort_pct}%, current={avg_current:.0f}")
            
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
            # Read present load (address 40, 2 bytes) - same as characterization test
            load = self.gripper.servos[0].read_word(40)
            # Convert load to current-like value (0-2047, direction bit in 10th bit)
            if load > 1023:
                load = load - 1024  # Remove direction bit for magnitude
            return load
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
                self.gripper.move_with_torque_management(50, 30)
                time.sleep(1)
        except Exception as e:
            self.logger.error(f"Shutdown failed: {e}")
