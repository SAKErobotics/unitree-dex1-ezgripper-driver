#!/usr/bin/env python3
"""
Simplified Error Handler for EZGripper

Provides error detection and reboot capability only.
No automatic recovery strategies - control algorithm decides response.
"""

import time
import logging
from enum import IntFlag


class HardwareError(IntFlag):
    """Hardware Error Status bits (Register 70)"""
    NONE = 0
    INPUT_VOLTAGE = 1       # Bit 0: Input voltage out of range
    OVERHEATING = 4         # Bit 2: Internal temperature exceeded limit
    MOTOR_ENCODER = 8       # Bit 3: Motor encoder malfunction
    ELECTRICAL_SHOCK = 16   # Bit 4: Electrical shock detected
    OVERLOAD = 32           # Bit 5: Persistent overload detected


def check_hardware_error(servo, config) -> tuple:
    """
    Check for hardware errors
    
    Args:
        servo: Robotis_Servo instance
        config: Config object with register addresses
        
    Returns:
        tuple: (error_code: int, description: str)
        error_code is None if communication fails
    """
    try:
        error_status = servo.read_address(config.reg_hardware_error)[0]
        
        if error_status == 0:
            return (0, "No errors")
        
        # Decode error bits
        errors = []
        if error_status & HardwareError.INPUT_VOLTAGE:
            errors.append("Input Voltage Error")
        if error_status & HardwareError.OVERHEATING:
            errors.append("Overheating Error")
        if error_status & HardwareError.MOTOR_ENCODER:
            errors.append("Motor Encoder Error")
        if error_status & HardwareError.ELECTRICAL_SHOCK:
            errors.append("Electrical Shock Error")
        if error_status & HardwareError.OVERLOAD:
            errors.append("Overload Error")
        
        description = ", ".join(errors) if errors else f"Unknown error (0x{error_status:02X})"
        return (error_status, description)
        
    except Exception as e:
        logging.error(f"Failed to check hardware errors: {e}")
        return (None, str(e))


def clear_error_via_reboot(servo) -> bool:
    """
    Clear hardware error by rebooting servo
    
    Args:
        servo: Robotis_Servo instance
        
    Returns:
        bool: True if reboot successful and error cleared
    """
    try:
        # Send reboot instruction via SDK
        from dynamixel_sdk import COMM_SUCCESS
        
        comm_result = servo.dyn.packetHandler.reboot(
            servo.dyn.portHandler, 
            servo.servo_id
        )
        
        # Wait for servo to reboot
        time.sleep(2.0)
        
        # Verify servo responds
        model_num, comm_result, error = servo.dyn.packetHandler.ping(
            servo.dyn.portHandler,
            servo.servo_id
        )
        
        if comm_result != COMM_SUCCESS:
            logging.error("Servo not responding after reboot")
            return False
        
        logging.info(f"Servo {servo.servo_id} rebooted successfully")
        return True
        
    except Exception as e:
        logging.error(f"Reboot failed: {e}")
        return False


def log_error(error_code: int, description: str, context: dict, logger: logging.Logger = None):
    """
    Log error with context
    
    Args:
        error_code: Hardware error code
        description: Error description
        context: Dictionary with additional context (temp, current, position, etc.)
        logger: Logger instance (uses root logger if None)
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    log_msg = f"Hardware Error 0x{error_code:02X}: {description}"
    
    if context:
        context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        log_msg += f" | Context: {context_str}"
    
    logger.error(log_msg)
