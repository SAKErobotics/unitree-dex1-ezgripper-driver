#!/usr/bin/env python3
"""
Calibrate gripper and save to config file for driver to load
"""
import json
import os
import time
from libezgripper import create_connection, create_gripper
import serial.tools.list_ports

# Configuration
device = '/dev/ttyUSB0'
config_file = '/tmp/ezgripper_device_config.json'

print("=" * 60)
print("EZGRIPPER CALIBRATION WITH CONFIG SAVE")
print("=" * 60)

# Get serial number
print(f"\n1. Reading serial number from {device}...")
serial_number = 'unknown'
try:
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if port.device == device:
            serial_number = port.serial_number if port.serial_number else 'unknown'
            print(f"   Serial number: {serial_number}")
            break
except Exception as e:
    print(f"   Warning: Could not read serial number: {e}")

# Connect and calibrate
print(f"\n2. Connecting to gripper...")
connection = create_connection(device, baudrate=1000000)
time.sleep(1)

gripper = create_gripper(connection, 'calibration', [1])

print(f"\n3. Running calibration...")
gripper.calibrate()

zero_position = gripper.zero_positions[0]
print(f"\n✅ Calibration complete!")
print(f"   Zero position (raw): {zero_position}")

# Convert to positive offset for position calculation
# Position calc does: servo_position = raw - zero_offset
# We want: closed (raw=3736) → servo_position=0
# So: zero_offset = 3736 (positive)
calibration_offset = abs(zero_position)
print(f"   Calibration offset (for config): {calibration_offset}")

# Save to config file
print(f"\n4. Saving calibration to {config_file}...")
try:
    # Load existing config
    config = {}
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
    
    # Initialize calibration dict if needed
    if 'calibration' not in config:
        config['calibration'] = {}
    
    # Save calibration by serial number (positive value)
    config['calibration'][serial_number] = calibration_offset
    
    # Write back
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"   ✅ Saved calibration for serial {serial_number}")
    print(f"\nConfig file contents:")
    print(json.dumps(config, indent=2))
    
except Exception as e:
    print(f"   ❌ Failed to save calibration: {e}")

print("\n" + "=" * 60)
print("Calibration saved! You can now start the driver.")
print("=" * 60)
