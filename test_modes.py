#!/usr/bin/env python3
"""Test different operating modes to understand Goal Current"""

from libezgripper.config import load_config
from libezgripper import create_connection
from libezgripper.lib_robotis import Robotis_Servo
import time

config = load_config()
print("Testing different operating modes...")

try:
    conn = create_connection('/dev/ttyUSB0', config.comm_baudrate)
    servo = Robotis_Servo(conn, 1)
    
    # Disable torque first
    servo.write_word(config.reg_torque_enable, 0)
    time.sleep(0.1)
    
    # Test different modes
    modes = [
        (0, "Velocity Control Mode"),
        (1, "Position Control Mode"), 
        (3, "Position Control Mode (Multi-turn)"),
        (4, "Extended Position Control Mode"),
        (5, "Current Control Mode")
    ]
    
    for mode_val, mode_name in modes:
        print(f"\n=== Testing {mode_name} ({mode_val}) ===")
        
        try:
            # Set mode
            servo.write_word(config.reg_operating_mode, mode_val)
            time.sleep(0.1)
            
            # Verify mode
            actual_mode = servo.read_word(config.reg_operating_mode)
            print(f"  Mode set: {actual_mode}")
            
            # Enable torque
            servo.write_word(config.reg_torque_enable, 1)
            time.sleep(0.1)
            
            # Try to set Goal Current
            try:
                servo.write_word(config.reg_goal_current, 100)
                print(f"  ✓ Goal Current accepted in {mode_name}")
            except Exception as e:
                print(f"  ✗ Goal Current failed in {mode_name}: {e}")
            
            # Disable torque before next mode
            servo.write_word(config.reg_torque_enable, 0)
            time.sleep(0.1)
            
        except Exception as e:
            print(f"  Error with {mode_name}: {e}")
    
    # Set back to Extended Position Control Mode
    print("\n=== Setting back to Extended Position Control Mode ===")
    servo.write_word(config.reg_operating_mode, 4)
    servo.write_word(config.reg_torque_enable, 1)
    
    print("Done!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
