#!/usr/bin/env python3
"""Test direct servo control without zero position offset"""

from libezgripper.config import load_config
from libezgripper import create_connection
from libezgripper.lib_robotis import Robotis_Servo
import time

config = load_config()
print("Testing direct servo control (no zero position offset)...")

try:
    conn = create_connection('/dev/ttyUSB0', config.comm_baudrate)
    servo = Robotis_Servo(conn, 1)
    
    # Read current raw position
    raw_pos = servo.read_word_signed(config.reg_present_position)
    print(f"Current raw position: {raw_pos}")
    
    # Try moving to different raw positions
    # The servo range is typically 0-4095
    test_positions = [2000, 1000, 3000, 500, 3500]
    
    for pos in test_positions:
        print(f"\nTrying raw position {pos}...")
        try:
            servo.write_word(config.reg_goal_position, pos)
            time.sleep(1)
            
            new_pos = servo.read_word_signed(config.reg_present_position)
            print(f"  New raw position: {new_pos}")
            print(f"  Movement: {new_pos - raw_pos}")
            
            if abs(new_pos - raw_pos) > 10:
                print(f"  ✓ Servo moved!")
                raw_pos = new_pos
            else:
                print(f"  ✗ No significant movement")
                
        except Exception as e:
            print(f"  Error: {e}")
    
    print("\nDone!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
