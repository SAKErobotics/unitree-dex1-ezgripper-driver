#!/usr/bin/env python3
"""Test first connection to servo - minimal code to isolate error 128"""

import sys
import time
sys.path.insert(0, 'libezgripper')
from lib_robotis import USB2Dynamixel_Device, Robotis_Servo

print("=" * 60)
print("Testing First Connection to Servo")
print("=" * 60)

print("\n1. Opening USB connection...")
dev = USB2Dynamixel_Device('/dev/ttyUSB0', 1000000)
print("   ✅ USB device opened")

print("\n2. Creating servo object...")
servo = Robotis_Servo(dev, 1)
print("   ✅ Servo object created")

print("\n3. Waiting 1 second before first operation...")
time.sleep(1.0)

print("\n4. Attempting first read (register 0 - Model Number)...")
try:
    model = servo.read_word(0)
    print(f"   ✅ SUCCESS: Model = {model}")
except Exception as e:
    print(f"   ❌ FAILED: {e}")
    print("\n5. Trying again after another 1 second delay...")
    time.sleep(1.0)
    try:
        model = servo.read_word(0)
        print(f"   ✅ SUCCESS on retry: Model = {model}")
    except Exception as e2:
        print(f"   ❌ FAILED again: {e2}")
        sys.exit(1)

print("\n6. Reading torque enable (register 64)...")
try:
    torque = servo.read_word(64)
    print(f"   ✅ Torque enable: {torque}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

print("\n7. Reading current limit (register 38)...")
try:
    current_limit = servo.read_word(38)
    print(f"   ✅ Current limit: {current_limit}")
except Exception as e:
    print(f"   ❌ Failed: {e}")

print("\n" + "=" * 60)
print("Test complete")
print("=" * 60)
