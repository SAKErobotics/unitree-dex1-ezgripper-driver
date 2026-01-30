#!/usr/bin/env python3
"""Try to escape from the 100% limit"""

from libezgripper.config import load_config
from libezgripper import create_connection
from libezgripper.ezgripper_base import Gripper
import time

config = load_config()
print("Trying to escape from 100% limit...")

try:
    conn = create_connection('/dev/ttyUSB0', config.comm_baudrate)
    gripper = Gripper(conn, 'left', [1], config)
    
    # Try different positions to escape
    positions = [50, 20, 0, 80, 10, 90, 5]
    
    for pos in positions:
        print(f"\nTrying position {pos}...")
        gripper._goto_position(pos)
        time.sleep(1)
        
        try:
            current = gripper.get_position()
            print(f"  Current position: {current}%")
            if current < 95:
                print(f"  ✓ Escaped from limit! Now at {current}%")
                break
        except Exception as e:
            print(f"  Error reading position: {e}")
            continue
    
    print("\nDone!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
