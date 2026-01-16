#!/usr/bin/env python3
"""
Run EZGripper hardware calibration to set position reference points
"""

import sys
import time
from libezgripper import create_connection, Gripper

print("🔧 EZGripper Hardware Calibration")
print("=" * 60)

# Connect to gripper
print("\n1. Connecting to gripper...")
conn = create_connection('socket://192.168.0.131:4000')
gripper = Gripper(conn, 'gripper', [1])
print(f"✅ Connected, current position: {gripper.get_position():.1f}%")

# Move to relaxed position first
print("\n2. Moving to relaxed position (50%)...")
gripper.goto_position(50.0, 30.0)
time.sleep(2)
print(f"✅ At relaxed position: {gripper.get_position():.1f}%")

# Run calibration
print("\n3. Running hardware calibration...")
print("   This will move the gripper through its full range")
print("   to establish position reference points...")
gripper.calibrate()
time.sleep(3)
print(f"✅ Calibration complete")

# Verify calibration
print("\n4. Verifying calibration...")

print("   Testing 0% (closed)...")
gripper.goto_position(0.0, 40.0)
time.sleep(2)
pos_0 = gripper.get_position()
print(f"   Position at 0%: {pos_0:.1f}%")

print("   Testing 50% (mid)...")
gripper.goto_position(50.0, 40.0)
time.sleep(2)
pos_50 = gripper.get_position()
print(f"   Position at 50%: {pos_50:.1f}%")

print("   Testing 100% (open)...")
gripper.goto_position(100.0, 40.0)
time.sleep(2)
pos_100 = gripper.get_position()
print(f"   Position at 100%: {pos_100:.1f}%")

# Return to neutral
print("\n5. Returning to neutral position...")
gripper.goto_position(50.0, 30.0)
time.sleep(1)

# Release
gripper.release()

print("\n" + "=" * 60)
print("✅ CALIBRATION COMPLETE")
print("=" * 60)
print(f"Position accuracy:")
print(f"  0%: {pos_0:.1f}% (should be ~0%)")
print(f"  50%: {pos_50:.1f}% (should be ~50%)")
print(f"  100%: {pos_100:.1f}% (should be ~100%)")

if abs(pos_0) < 5 and abs(pos_50 - 50) < 5 and abs(pos_100 - 100) < 5:
    print("\n✅ Calibration successful - positions accurate!")
else:
    print("\n⚠️  Calibration may need adjustment - check positions")
