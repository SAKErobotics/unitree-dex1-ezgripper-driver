#!/usr/bin/env python3
"""
Direct servo test - bypasses all driver logic
Tests if servo responds to direct commands
"""

from libezgripper import create_connection, create_gripper, load_config
import time

print("=" * 60)
print("DIRECT SERVO TEST")
print("=" * 60)

# Connect to gripper
print("\n1. Connecting to gripper...")
connection = create_connection('/dev/ttyUSB0')
config = load_config()
gripper = create_gripper(connection, "test", [1], config)

print("\n2. Current position:")
sensor_data = gripper.bulk_read_sensor_data()
print(f"   Position: {sensor_data['position']:.1f}%")
print(f"   Current: {sensor_data['current']} mA")

print("\n3. Sending command to 50% with 80% effort...")
gripper.goto_position(50.0, 80.0)
time.sleep(2)

print("\n4. Reading new position...")
sensor_data = gripper.bulk_read_sensor_data()
print(f"   Position: {sensor_data['position']:.1f}%")
print(f"   Current: {sensor_data['current']} mA")

print("\n5. Sending command to 20% with 80% effort...")
gripper.goto_position(20.0, 80.0)
time.sleep(2)

print("\n6. Reading final position...")
sensor_data = gripper.bulk_read_sensor_data()
print(f"   Position: {sensor_data['position']:.1f}%")
print(f"   Current: {sensor_data['current']} mA")

print("\n✅ Test complete")
print("=" * 60)
