#!/usr/bin/env python3
"""
Smart Servo Initialization

Reads servo EEPROM values before writing to prevent unnecessary wear.
Only updates values that don't match the desired configuration.
"""

import logging
from typing import Dict, List, Tuple


def smart_init_servo(servo, config) -> Dict[str, Tuple[int, int, bool]]:
    """
    Initialize servo with EEPROM-safe writes
    
    Reads current values and only writes if they differ from config.
    This prevents EEPROM wear from unnecessary writes.
    
    Args:
        servo: Robotis_Servo instance
        config: Config object with EEPROM settings
        
    Returns:
        Dict mapping setting name to (current_value, desired_value, updated)
    """
    logger = logging.getLogger(__name__)
    results = {}
    
    # Disable torque before writing EEPROM (required for Protocol 2.0)
    try:
        servo.write_address(config.reg_torque_enable, [0])
    except Exception as e:
        logger.warning(f"Could not disable torque: {e}")
    
    # EEPROM settings to check and update
    eeprom_settings = {
        'return_delay_time': (
            config.reg_return_delay_time,
            config.eeprom_return_delay_time,
            1  # 1 byte
        ),
        'status_return_level': (
            config.reg_status_return_level,
            config.eeprom_status_return_level,
            1  # 1 byte
        )
    }
    
    for setting_name, (register_addr, desired_value, num_bytes) in eeprom_settings.items():
        try:
            # Read current value
            if num_bytes == 1:
                current_value = servo.read_address(register_addr)[0]
            elif num_bytes == 2:
                data = servo.read_address(register_addr, 2)
                current_value = data[0] + (data[1] << 8)
            else:
                logger.warning(f"Unsupported byte count {num_bytes} for {setting_name}")
                continue
            
            # Check if update needed
            if current_value != desired_value:
                logger.info(f"Updating {setting_name}: {current_value} -> {desired_value}")
                
                # Write new value
                if num_bytes == 1:
                    servo.write_address(register_addr, [desired_value])
                elif num_bytes == 2:
                    servo.write_word(register_addr, desired_value)
                
                results[setting_name] = (current_value, desired_value, True)
            else:
                logger.debug(f"{setting_name} already set to {desired_value}")
                results[setting_name] = (current_value, desired_value, False)
                
        except Exception as e:
            logger.error(f"Failed to initialize {setting_name}: {e}")
            results[setting_name] = (None, desired_value, False)
    
    # Re-enable torque after EEPROM writes
    try:
        servo.write_address(config.reg_torque_enable, [1])
    except Exception as e:
        logger.warning(f"Could not re-enable torque: {e}")
    
    return results


def verify_eeprom_settings(servo, config) -> bool:
    """
    Verify EEPROM settings match configuration
    
    Args:
        servo: Robotis_Servo instance
        config: Config object
        
    Returns:
        bool: True if all settings match
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Check return delay time
        return_delay = servo.read_address(config.reg_return_delay_time)[0]
        if return_delay != config.eeprom_return_delay_time:
            logger.warning(f"Return delay time mismatch: {return_delay} != {config.eeprom_return_delay_time}")
            return False
        
        # Check status return level
        status_level = servo.read_address(config.reg_status_return_level)[0]
        if status_level != config.eeprom_status_return_level:
            logger.warning(f"Status return level mismatch: {status_level} != {config.eeprom_status_return_level}")
            return False
        
        logger.info("EEPROM settings verified successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to verify EEPROM settings: {e}")
        return False


def get_eeprom_info(servo, config) -> Dict[str, int]:
    """
    Read current EEPROM settings
    
    Args:
        servo: Robotis_Servo instance
        config: Config object
        
    Returns:
        Dict with current EEPROM values
    """
    info = {}
    
    try:
        info['return_delay_time'] = servo.read_address(config.reg_return_delay_time)[0]
        info['status_return_level'] = servo.read_address(config.reg_status_return_level)[0]
    except Exception as e:
        logging.error(f"Failed to read EEPROM info: {e}")
    
    return info


def log_eeprom_optimization(results: Dict[str, Tuple[int, int, bool]]):
    """
    Log EEPROM optimization results
    
    Args:
        results: Dict from smart_init_servo
    """
    logger = logging.getLogger(__name__)
    
    updated_count = sum(1 for _, _, updated in results.values() if updated)
    total_count = len(results)
    
    if updated_count == 0:
        logger.info(f"EEPROM optimization: All {total_count} settings already optimal (no writes needed)")
    else:
        logger.info(f"EEPROM optimization: Updated {updated_count}/{total_count} settings")
        
        for setting_name, (old_val, new_val, updated) in results.items():
            if updated:
                logger.info(f"  - {setting_name}: {old_val} -> {new_val}")
