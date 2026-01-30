#!/usr/bin/env python3
"""Test servo movement with torque check"""

from libezgripper.config import load_config
from libezgripper import create_connection
from libezgripper.lib_robotis import Robotis_Servo
import time

config = load_config()
print("Testing servo movement with torque check...")

try:
    conn = create_connection('/dev/ttyUSB0', config.comm_baudrate)
    servo = Robotis_Servo(conn, 1)
    
    # Check torque status
    torque = servo.read_byte(config.reg_torque_enable)
    print(f"Torque enabled: {torque}")
    
    if torque != 1:
        print("Enabling torque...")
        servo.write_byte(config.reg_torque_enable, 1)
        time.sleep(0.5)
    
    # Check current limit
    current_limit = servo.read_word(config.reg_current_limit)
    print(f"Current limit: {current_limit}")
    
    # Try a larger movement to see if we're at a limit
    raw_pos = servo.read_word_signed(config.reg_present_position)
    print(f"Starting position: {raw_pos}")
    
    # Try moving in both directions
    test_moves = [
        (raw_pos + 500, "+500"),
        (raw_pos - 500, "-500"),
        (raw_pos + 1000, "+1000"),
        (raw_pos - 1000, "-1000"),
        (2000, "absolute 2000"),
        (1000, "absolute 1000")
    ]
    
    for target, desc in test_moves:
        print(f"\nTrying move to {target} ({desc})...")
        servo.write_word(config.reg_goal_position, target)
        time.sleep(1)
        
        try:
            new_pos = servo.read_word_signed(config.reg_present_position)
            movement = new_pos - raw_pos
            print(f"  Position: {new_pos} (moved {movement})")
            
            if abs(movement) > 50:
                print(f"  ✓ Significant movement!")
                raw_pos = new_pos
            else:
                print(f"  ✗ Little movement")
                
        except Exception as e:
            print(f"  Error: {e}")
    
    print("\nDone!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
