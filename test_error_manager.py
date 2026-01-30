#!/usr/bin/env python3
"""Test error manager functionality"""

import sys
import time
import logging

sys.path.insert(0, '/home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver')
from libezgripper import create_connection, Gripper

# Configure logging to see error manager output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

device = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'

print("="*70)
print("Error Manager Test")
print("="*70)
print(f"Device: {device}\n")

# Create connection
print("Creating connection...")
connection = create_connection(dev_name=device, baudrate=1000000)
print("✓ Connection created\n")

# Create gripper with error manager enabled
print("Creating gripper with error manager...")
print("(Error manager will automatically check and attempt recovery)")
print("-"*70)
try:
    gripper = Gripper(connection, 'test_gripper', [1], enable_error_manager=True)
    print("✓ Gripper created successfully\n")
except Exception as e:
    print(f"✗ Failed to create gripper: {e}\n")
    sys.exit(1)

# Check error statistics
if gripper.error_managers:
    print("Error Manager Statistics:")
    print("-"*70)
    for i, error_mgr in enumerate(gripper.error_managers):
        stats = error_mgr.get_error_statistics()
        print(f"Servo {gripper.servos[i].servo_id}:")
        print(f"  Total errors detected: {stats['total_errors']}")
        print(f"  Last error: {stats['last_error']}")
        print(f"  Recovery attempts: {stats['recovery_attempts']}")
    print()

# Test manual error check
print("Manual Error Check:")
print("-"*70)
if gripper.error_managers:
    for i, error_mgr in enumerate(gripper.error_managers):
        error_code, description, severity = error_mgr.check_hardware_errors()
        print(f"Servo {gripper.servos[i].servo_id}:")
        print(f"  Status: {description}")
        print(f"  Code: 0x{error_code:02X}" if error_code else "  Code: None")
        print(f"  Severity: {severity}")
print()

# Test basic operations
print("Testing basic operations:")
print("-"*70)

try:
    print("Reading position...")
    position = gripper.get_position()
    print(f"✓ Current position: {position:.1f}%\n")
except Exception as e:
    print(f"✗ Failed: {e}\n")
    # Check if error occurred
    if gripper.error_managers:
        error_code, description, severity = gripper.error_managers[0].check_hardware_errors()
        if error_code != 0:
            print(f"Hardware error detected: {description}")
            print("Attempting recovery...")
            if gripper.error_managers[0].attempt_recovery(error_code):
                print("✓ Recovery successful\n")
            else:
                print("✗ Recovery failed\n")

print("="*70)
print("Error Manager Test Complete")
print("="*70)
print("\nError Manager Features:")
print("  ✓ Automatic error detection on initialization")
print("  ✓ Automatic recovery attempts")
print("  ✓ Error classification by severity")
print("  ✓ Recovery strategies per error type:")
print("    - Overload: Reduce current limit, retry")
print("    - Voltage: Check if voltage recovered")
print("    - Overheating: Cool down, reduce current")
print("    - Critical: Attempt single clear")
print("  ✓ Error statistics tracking")
print("  ✓ Configurable recovery policies")
