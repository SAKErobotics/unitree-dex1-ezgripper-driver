#!/usr/bin/env python3
"""
Enhancement proposal for EZGripper DDS Driver - Error Recovery Interface

This file proposes adding error recovery capabilities to the DDS interface
to handle Dynamixel overload errors and other hardware error conditions.

Based on Dynamixel MX-64 Protocol 2.0 documentation:
1. Hardware Error Status (Address 70) indicates error conditions
2. Shutdown (Address 63) configures error responses  
3. Torque Enable (Address 64) is cleared on shutdown errors
4. Reboot instruction (0x08) is required to recover from shutdown errors

The solution adds a new DDS command type for error recovery operations.
"""

from dataclasses import dataclass
from enum import IntEnum
import time
import logging

class ErrorRecoveryCommand(IntEnum):
    """Error recovery commands that can be sent via DDS tau field"""
    NO_OP = 0                   # No operation
    CLEAR_ERROR = 1             # Clear error status register
    TORQUE_CYCLE = 2            # Turn torque off, wait, then on
    REBOOT_SERVO = 3            # Send Reboot instruction (0x08)
    FULL_RECOVERY = 4           # Complete recovery sequence

@dataclass
class ErrorStatus:
    """Hardware error status from Dynamixel"""
    error_bits: int             # Raw error status from Hardware Error Status (70)
    overload_error: bool        # Bit 1: Overload error detected
    overheating_error: bool     # Bit 2: Overheating error detected  
    voltage_error: bool         # Bit 0: Input voltage error
    hardware_error: bool        # Bit 7: Hardware error alert
    servo_in_shutdown: bool     # Torque Enable cleared due to error
    timestamp: float            # Time when error was detected

class ErrorRecoveryHandler:
    """Handles Dynamixel error detection and recovery"""
    
    def __init__(self, logger):
        self.logger = logger
        self.last_error_status = None
        self.recovery_in_progress = False
        self.recovery_start_time = None
        self.recovery_timeout = 10.0  # Max time for recovery operation
        
        # Dynamixel Protocol 2.0 register addresses
        self.HARDWARE_ERROR_STATUS = 70
        self.TORQUE_ENABLE = 64
        self.SHUTDOWN = 63
        
        # Error bit masks (from MX-64 documentation)
        self.ERROR_OVERLOAD = 0x02      # Bit 1
        self.ERROR_OVERHEATING = 0x04   # Bit 2
        self.ERROR_VOLTAGE = 0x01       # Bit 0
        self.ERROR_ALERT = 0x80         # Bit 7
        
    def read_error_status(self, servo) -> ErrorStatus:
        """Read hardware error status from servo"""
        try:
            # Read Hardware Error Status register (Address 70)
            error_data = servo.read_address(self.HARDWARE_ERROR_STATUS, 2)
            if error_data and len(error_data) >= 2:
                error_bits = error_data[0] | (error_data[1] << 8)
            else:
                error_bits = 0
                
            # Read Torque Enable to check if servo is in shutdown
            torque_data = servo.read_address(self.TORQUE_ENABLE, 1)
            torque_enabled = torque_data[0] == 1 if torque_data else False
            
            # Create error status
            status = ErrorStatus(
                error_bits=error_bits,
                overload_error=bool(error_bits & self.ERROR_OVERLOAD),
                overheating_error=bool(error_bits & self.ERROR_OVERHEATING),
                voltage_error=bool(error_bits & self.ERROR_VOLTAGE),
                hardware_error=bool(error_bits & self.ERROR_ALERT),
                servo_in_shutdown=not torque_enabled,
                timestamp=time.time()
            )
            
            self.last_error_status = status
            return status
            
        except Exception as e:
            self.logger.error(f"Failed to read error status: {e}")
            return ErrorStatus(
                error_bits=0,
                overload_error=False,
                overheating_error=False,
                voltage_error=False,
                hardware_error=False,
                servo_in_shutdown=False,
                timestamp=time.time()
            )
    
    def has_error(self, status: ErrorStatus = None) -> bool:
        """Check if there are any error conditions"""
        if status is None:
            status = self.last_error_status
            
        if status is None:
            return False
            
        return (status.overload_error or 
                status.overheating_error or
                status.voltage_error or
                status.hardware_error or
                status.servo_in_shutdown)
    
    def execute_recovery(self, servo, command: ErrorRecoveryCommand) -> bool:
        """Execute error recovery command"""
        if self.recovery_in_progress:
            self.logger.warning("Recovery already in progress, ignoring new command")
            return False
            
        self.recovery_in_progress = True
        self.recovery_start_time = time.time()
        
        try:
            self.logger.info(f"Starting error recovery: {command.name}")
            
            if command == ErrorRecoveryCommand.NO_OP:
                return True
                
            elif command == ErrorRecoveryCommand.CLEAR_ERRORS:
                return self._clear_errors(servo)
                
            elif command == ErrorRecoveryCommand.TORQUE_CYCLE:
                return self._torque_cycle(servo)
                
            elif command == ErrorRecoveryCommand.REBOOT_SERVO:
                return self._reboot_servo(servo)
                
            elif command == ErrorRecoveryCommand.FULL_RECOVERY:
                return self._full_recovery(servo)
                
            else:
                self.logger.error(f"Unknown recovery command: {command}")
                return False
                
        except Exception as e:
            self.logger.error(f"Recovery failed: {e}")
            return False
        finally:
            self.recovery_in_progress = False
            self.recovery_start_time = None
    
    def _clear_errors(self, servo) -> bool:
        """Clear hardware error status"""
        try:
            # Write 0 to Hardware Error Status to clear errors
            servo.write_address(self.HARDWARE_ERROR_STATUS, [0, 0])
            time.sleep(0.1)
            self.logger.info("Hardware error status cleared")
            return True
        except Exception as e:
            self.logger.error(f"Failed to clear errors: {e}")
            return False
    
    def _torque_cycle(self, servo) -> bool:
        """Turn torque off, wait, then on"""
        try:
            # Turn torque off
            servo.write_address(self.TORQUE_ENABLE, [0])
            time.sleep(0.5)
            
            # Turn torque back on
            servo.write_address(self.TORQUE_ENABLE, [1])
            time.sleep(0.1)
            
            self.logger.info("Torque cycle completed")
            return True
        except Exception as e:
            self.logger.error(f"Torque cycle failed: {e}")
            return False
    
    def _reboot_servo(self, servo) -> bool:
        """Send Reboot instruction (Protocol 2.0)"""
        try:
            # Method 1: Use libezgripper reboot if available
            if hasattr(servo, 'reboot'):
                servo.reboot()
            else:
                # Method 2: Direct Protocol 2.0 Reboot instruction
                # This sends instruction 0x08 to the servo
                servo.write_address(0x08, [1])
            
            time.sleep(1.0)  # Wait for reboot to complete
            self.logger.info("Servo reboot completed")
            return True
        except Exception as e:
            self.logger.error(f"Servo reboot failed: {e}")
            return False
    
    def _full_recovery(self, servo) -> bool:
        """Complete recovery sequence"""
        self.logger.info("Starting full recovery sequence")
        
        # Step 1: Clear error status
        if not self._clear_errors(servo):
            self.logger.warning("Error clear failed, continuing")
        
        # Step 2: Torque cycle
        if not self._torque_cycle(servo):
            self.logger.warning("Torque cycle failed, continuing")
        
        # Step 3: Reboot if still in shutdown
        status = self.read_error_status(servo)
        if status.servo_in_shutdown:
            if not self._reboot_servo(servo):
                self.logger.error("Reboot failed in full recovery")
                return False
        
        # Step 4: Verify recovery
        time.sleep(0.5)
        status = self.read_error_status(servo)
        if not self.has_error(status):
            self.logger.info("Full recovery successful")
            return True
        else:
            self.logger.error("Full recovery failed - errors still present")
            return False

"""
Integration into DDS Interface:

1. Add ErrorRecoveryCommand to the motor command DDS message structure
2. Add error status fields to the motor state DDS message structure
3. Implement error recovery handler in the driver
4. Add monitoring loop to detect errors automatically
5. Add command handler to process recovery commands

DDS Message Enhancement:

MotorCmds_ should include:
- error_recovery_cmd: uint8 (ErrorRecoveryCommand enum)

MotorStates_ should include:
- hardware_error_status: uint16
- overload_error: bool
- overheating_error: bool
- voltage_error: bool
- servo_in_shutdown: bool
- recovery_in_progress: bool

Usage:
- Send error recovery command via DDS to recover from overload
- Monitor error status in DDS state messages
- Automatic error detection and logging
"""
