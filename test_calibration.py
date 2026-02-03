#!/usr/bin/env python3
"""Test calibration with detailed monitoring of collision detection"""

import sys
import time
sys.path.insert(0, 'libezgripper')
from lib_robotis import create_connection
from libezgripper import create_gripper
from libezgripper.config import load_config

print("=" * 60)
print("Calibration Monitoring Test")
print("=" * 60)

# Connect to servo
print("\n1. Connecting to servo...")
connection = create_connection(dev_name='/dev/ttyUSB0', baudrate=1000000)
time.sleep(1.0)  # Wait for servo to be ready

config = load_config()
gripper = create_gripper(connection, 'test_gripper', [1], config)

print("\n2. Starting calibration with detailed monitoring...")
print("   Watch for:")
print("   - Current readings during closing")
print("   - Position stagnation detection")
print("   - Collision detection trigger")
print("   - Time to detect collision")
print("   - Immediate goto position 50")
print()

start_time = time.time()

# Run calibration
success = gripper.calibrate()

end_time = time.time()
calibration_time = end_time - start_time

print("\n" + "=" * 60)
print("Calibration Results:")
print(f"  Success: {success}")
print(f"  Total time: {calibration_time:.2f} seconds")
print(f"  Zero position: {gripper.zero_positions[0]}")
print("=" * 60)
