#!/usr/bin/env python3
"""Test tiny servo movement (30 units out of 4096) without calibration"""

from libezgripper.config import load_config
from libezgripper import create_connection
from libezgripper.lib_robotis import Robotis_Servo
import time

config = load_config()
print("Testing tiny movement (30 units) without calibration...")

try:
    # Connect directly without creating Gripper object (no initialization)
    conn = create_connection('/dev/ttyUSB0', config.comm_baudrate)
    servo = Robotis_Servo(conn, 1)
    
    # Read current raw position
    raw_pos = servo.read_word_signed(config.reg_present_position)
    print(f"Starting raw position: {raw_pos}")
    
    # Test tiny movements back and forth
    for i in range(10):
        print(f"\nCycle {i+1}/10")
        
        # Move +30 units
        target = raw_pos + 30
        print(f"  Moving to {target} (+30)...")
        servo.write_word(config.reg_goal_position, target)
        time.sleep(0.5)
        
        try:
            new_pos = servo.read_word_signed(config.reg_present_position)
            print(f"  Position: {new_pos} (moved {new_pos - raw_pos})")
        except Exception as e:
            print(f"  Error reading: {e}")
            new_pos = raw_pos
        
        # Move -30 units from original
        target = raw_pos - 30
        print(f"  Moving to {target} (-30)...")
        servo.write_word(config.reg_goal_position, target)
        time.sleep(0.5)
        
        try:
            new_pos2 = servo.read_word_signed(config.reg_present_position)
            print(f"  Position: {new_pos2} (moved {new_pos2 - raw_pos})")
            
            # Check if movement happened
            if abs(new_pos - new_pos2) > 10:
                print(f"  ✓ Movement detected: {abs(new_pos - new_pos2)} units")
            else:
                print(f"  ✗ Little movement: {abs(new_pos - new_pos2)} units")
        except Exception as e:
            print(f"  Error reading: {e}")
    
    print("\nTest complete!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
