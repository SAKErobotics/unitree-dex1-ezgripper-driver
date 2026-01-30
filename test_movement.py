#!/usr/bin/env python3
"""Test servo movement back and forth without calibration"""

from libezgripper.config import load_config
from libezgripper import create_connection
from libezgripper.ezgripper_base import Gripper
import time

config = load_config()
print("Testing servo movement without calibration...")
print(f"Initial position: {config.calibration_position}")
print(f"Current limit: {config.calibration_current}")

try:
    conn = create_connection('/dev/ttyUSB0', config.comm_baudrate)
    gripper = Gripper(conn, 'left', [1], config)
    
    # Get initial position
    pos = gripper.get_position()
    print(f"Starting position: {pos}%")
    
    # Move back and forth 10 times
    for i in range(10):
        print(f"\nCycle {i+1}/10")
        
        # Move to position 30
        print("  Moving to position 30...")
        gripper._goto_position(30)
        time.sleep(0.5)
        pos1 = gripper.get_position()
        print(f"  Position after move to 30: {pos1}%")
        
        # Move to position 0
        print("  Moving to position 0...")
        gripper._goto_position(0)
        time.sleep(0.5)
        pos2 = gripper.get_position()
        print(f"  Position after move to 0: {pos2}%")
        
        # Check if movement happened
        if abs(pos1 - pos2) > 5:
            print(f"  ✓ Movement detected: {abs(pos1 - pos2):.1f}% difference")
        else:
            print(f"  ✗ Little or no movement: {abs(pos1 - pos2):.1f}% difference")
    
    print("\nTest complete!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
