#!/usr/bin/python

#####################################################################
# Software License Agreement (BSD License)
#
# Copyright (c) 2024, SAKE Robotics
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the copyright holder nor the names of its
#      contributors may be used to endorse or promote products derived from
#      this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
##

"""
Error Management Module for EZGripper

Provides centralized error detection, classification, and recovery
for Dynamixel MX-64 servos using Protocol 2.0.
"""

import time
import logging
from enum import IntFlag, auto


class HardwareError(IntFlag):
    """
    Hardware Error Status bits (Register 70)
    
    Based on Dynamixel Protocol 2.0 MX-64 specification.
    """
    NONE = 0
    INPUT_VOLTAGE = 1       # Bit 0: Input voltage out of range
    OVERHEATING = 4         # Bit 2: Internal temperature exceeded limit
    MOTOR_ENCODER = 8       # Bit 3: Motor encoder malfunction
    ELECTRICAL_SHOCK = 16   # Bit 4: Electrical shock detected
    OVERLOAD = 32           # Bit 5: Persistent overload detected


class ErrorSeverity:
    """Error severity levels for prioritization"""
    INFO = 0        # Informational, no action needed
    WARNING = 1     # Warning, monitor but continue
    ERROR = 2       # Error, attempt recovery
    CRITICAL = 3    # Critical, stop operation


class ErrorManager:
    """
    Centralized error management for EZGripper servos
    
    Features:
    - Hardware error detection and classification
    - Automatic error recovery strategies
    - Error logging and statistics
    - Configurable recovery policies
    """
    
    # Register addresses (Protocol 2.0)
    ADDR_HARDWARE_ERROR = 70
    ADDR_TORQUE_ENABLE = 64
    ADDR_PRESENT_TEMPERATURE = 146
    ADDR_PRESENT_VOLTAGE = 144
    
    def __init__(self, servo, auto_recover=True, max_recovery_attempts=3):
        """
        Initialize error manager for a servo
        
        Args:
            servo: Robotis_Servo instance to manage
            auto_recover: Enable automatic error recovery
            max_recovery_attempts: Maximum recovery attempts per error
        """
        self.servo = servo
        self.auto_recover = auto_recover
        self.max_recovery_attempts = max_recovery_attempts
        
        # Error tracking
        self.error_count = 0
        self.recovery_attempts = {}
        self.last_error = None
        self.last_error_time = None
        
        # Logging
        self.logger = logging.getLogger(f'ErrorManager.Servo{servo.servo_id}')
        
    def check_hardware_errors(self):
        """
        Check for hardware errors and return status
        
        Returns:
            tuple: (error_code, error_description, severity)
        """
        try:
            error_status = self.servo.read_address(self.ADDR_HARDWARE_ERROR)[0]
            
            if error_status == 0:
                return (HardwareError.NONE, "No errors", ErrorSeverity.INFO)
            
            # Classify error
            errors = []
            severity = ErrorSeverity.WARNING
            
            if error_status & HardwareError.INPUT_VOLTAGE:
                errors.append("Input Voltage Error")
                severity = max(severity, ErrorSeverity.ERROR)
            
            if error_status & HardwareError.OVERHEATING:
                errors.append("Overheating Error")
                severity = max(severity, ErrorSeverity.CRITICAL)
            
            if error_status & HardwareError.MOTOR_ENCODER:
                errors.append("Motor Encoder Error")
                severity = max(severity, ErrorSeverity.CRITICAL)
            
            if error_status & HardwareError.ELECTRICAL_SHOCK:
                errors.append("Electrical Shock Error")
                severity = max(severity, ErrorSeverity.CRITICAL)
            
            if error_status & HardwareError.OVERLOAD:
                errors.append("Overload Error")
                severity = max(severity, ErrorSeverity.ERROR)
            
            description = ", ".join(errors)
            self.last_error = error_status
            self.last_error_time = time.time()
            self.error_count += 1
            
            self.logger.warning(f"Hardware error detected: {description} (0x{error_status:02X})")
            
            return (error_status, description, severity)
            
        except Exception as e:
            self.logger.error(f"Failed to check hardware errors: {e}")
            return (None, str(e), ErrorSeverity.ERROR)
    
    def clear_hardware_error(self):
        """
        Clear hardware error status
        
        Returns:
            bool: True if successfully cleared
        """
        try:
            self.logger.info("Clearing hardware error status...")
            
            # Disable torque first
            self.servo.write_address(self.ADDR_TORQUE_ENABLE, [0])
            time.sleep(0.1)
            
            # Clear error by writing 0 to Hardware Error Status
            self.servo.write_address(self.ADDR_HARDWARE_ERROR, [0])
            time.sleep(0.1)
            
            # Verify cleared
            error_status = self.servo.read_address(self.ADDR_HARDWARE_ERROR)[0]
            
            if error_status == 0:
                self.logger.info("Hardware error cleared successfully")
                return True
            else:
                self.logger.error(f"Failed to clear error, status still: 0x{error_status:02X}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to clear hardware error: {e}")
            return False
    
    def recover_from_overload(self):
        """
        Recover from overload error
        
        Strategy:
        1. Disable torque
        2. Wait for motor to cool/settle
        3. Clear error
        4. Re-enable torque with reduced current limit
        
        Returns:
            bool: True if recovery successful
        """
        try:
            self.logger.info("Attempting overload recovery...")
            
            # Disable torque
            self.servo.write_address(self.ADDR_TORQUE_ENABLE, [0])
            time.sleep(0.5)  # Wait for motor to settle
            
            # Clear error
            if not self.clear_hardware_error():
                return False
            
            # Reduce current limit to 70% to prevent immediate re-overload
            current_limit = int(1941 * 0.7)  # 70% of max
            self.servo.write_word(38, current_limit)
            self.logger.info(f"Reduced current limit to {current_limit} (70%)")
            
            # Re-enable torque
            self.servo.write_address(self.ADDR_TORQUE_ENABLE, [1])
            time.sleep(0.1)
            
            # Verify recovery
            error_status = self.servo.read_address(self.ADDR_HARDWARE_ERROR)[0]
            if error_status == 0:
                self.logger.info("Overload recovery successful")
                return True
            else:
                self.logger.error("Overload recovery failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Overload recovery failed: {e}")
            return False
    
    def recover_from_voltage_error(self):
        """
        Recover from voltage error
        
        Strategy:
        1. Check current voltage
        2. If voltage is now in range, clear error
        3. Otherwise, log critical error and disable servo
        
        Returns:
            bool: True if recovery successful
        """
        try:
            self.logger.info("Attempting voltage error recovery...")
            
            # Read current voltage
            voltage_raw = self.servo.read_address(self.ADDR_PRESENT_VOLTAGE, 2)
            voltage = (voltage_raw[0] + (voltage_raw[1] << 8)) * 0.1  # Convert to volts
            
            self.logger.info(f"Current voltage: {voltage:.1f}V")
            
            # Check if voltage is in acceptable range (9.5V - 16.0V for MX-64)
            if 9.5 <= voltage <= 16.0:
                self.logger.info("Voltage is now in range, clearing error")
                return self.clear_hardware_error()
            else:
                self.logger.critical(f"Voltage out of range: {voltage:.1f}V - cannot recover")
                # Disable torque for safety
                self.servo.write_address(self.ADDR_TORQUE_ENABLE, [0])
                return False
                
        except Exception as e:
            self.logger.error(f"Voltage error recovery failed: {e}")
            return False
    
    def recover_from_overheating(self):
        """
        Recover from overheating error
        
        Strategy:
        1. Disable torque immediately
        2. Wait for cooling
        3. Check temperature
        4. Clear error if temperature is acceptable
        
        Returns:
            bool: True if recovery successful
        """
        try:
            self.logger.warning("Attempting overheating recovery...")
            
            # Disable torque immediately
            self.servo.write_address(self.ADDR_TORQUE_ENABLE, [0])
            
            # Wait for cooling
            cooling_time = 30  # seconds
            self.logger.info(f"Waiting {cooling_time}s for motor to cool...")
            time.sleep(cooling_time)
            
            # Check temperature
            temp = self.servo.read_address(self.ADDR_PRESENT_TEMPERATURE)[0]
            self.logger.info(f"Current temperature: {temp}°C")
            
            # If temperature is below 70°C, attempt recovery
            if temp < 70:
                self.logger.info("Temperature acceptable, clearing error")
                if self.clear_hardware_error():
                    # Re-enable torque with reduced current
                    current_limit = int(1941 * 0.5)  # 50% of max
                    self.servo.write_word(38, current_limit)
                    self.servo.write_address(self.ADDR_TORQUE_ENABLE, [1])
                    self.logger.info("Overheating recovery successful (reduced to 50% current)")
                    return True
            else:
                self.logger.critical(f"Temperature still too high: {temp}°C")
                return False
                
        except Exception as e:
            self.logger.error(f"Overheating recovery failed: {e}")
            return False
    
    def attempt_recovery(self, error_code):
        """
        Attempt automatic recovery based on error type
        
        Args:
            error_code: Hardware error status code
            
        Returns:
            bool: True if recovery successful
        """
        if not self.auto_recover:
            self.logger.info("Auto-recovery disabled")
            return False
        
        # Handle None or invalid error codes
        if error_code is None:
            self.logger.error("Cannot recover from None error code (communication failure)")
            return False
        
        # Check recovery attempt limit
        if error_code not in self.recovery_attempts:
            self.recovery_attempts[error_code] = 0
        
        if self.recovery_attempts[error_code] >= self.max_recovery_attempts:
            self.logger.error(f"Max recovery attempts ({self.max_recovery_attempts}) reached for error 0x{error_code:02X}")
            return False
        
        self.recovery_attempts[error_code] += 1
        self.logger.info(f"Recovery attempt {self.recovery_attempts[error_code]}/{self.max_recovery_attempts}")
        
        # Select recovery strategy based on error type
        if error_code & HardwareError.OVERLOAD:
            return self.recover_from_overload()
        
        elif error_code & HardwareError.INPUT_VOLTAGE:
            return self.recover_from_voltage_error()
        
        elif error_code & HardwareError.OVERHEATING:
            return self.recover_from_overheating()
        
        elif error_code & (HardwareError.MOTOR_ENCODER | HardwareError.ELECTRICAL_SHOCK):
            # Critical hardware errors - just try clearing once
            self.logger.critical("Critical hardware error - attempting single clear")
            return self.clear_hardware_error()
        
        else:
            # Unknown error - try generic clear
            self.logger.warning("Unknown error type - attempting generic clear")
            return self.clear_hardware_error()
    
    def get_error_statistics(self):
        """
        Get error statistics
        
        Returns:
            dict: Error statistics
        """
        return {
            'total_errors': self.error_count,
            'last_error': self.last_error,
            'last_error_time': self.last_error_time,
            'recovery_attempts': dict(self.recovery_attempts)
        }
    
    def reset_statistics(self):
        """Reset error statistics"""
        self.error_count = 0
        self.recovery_attempts.clear()
        self.last_error = None
        self.last_error_time = None
        self.logger.info("Error statistics reset")


def create_error_manager(servo, **kwargs):
    """
    Factory function to create error manager
    
    Args:
        servo: Robotis_Servo instance
        **kwargs: Additional arguments for ErrorManager
        
    Returns:
        ErrorManager instance
    """
    return ErrorManager(servo, **kwargs)
