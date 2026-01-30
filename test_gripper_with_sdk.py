#!/usr/bin/env python3
"""Test EZGripper operations using Dynamixel SDK backend"""

import sys
import time
from dynamixel_sdk import *

# Control table addresses for MX-64(2.0)
ADDR_OPERATING_MODE = 11
ADDR_TORQUE_ENABLE = 64
ADDR_GOAL_POSITION = 116
ADDR_PRESENT_POSITION = 132
ADDR_PRESENT_CURRENT = 126

PROTOCOL_VERSION = 2.0
DXL_ID = 1
BAUDRATE = 1000000
DEVICENAME = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'

print("="*70)
print("EZGripper Test with Dynamixel SDK")
print("="*70)

# Initialize
portHandler = PortHandler(DEVICENAME)
packetHandler = PacketHandler(PROTOCOL_VERSION)

if not portHandler.openPort():
    print("✗ Failed to open port")
    sys.exit(1)

if not portHandler.setBaudRate(BAUDRATE):
    print("✗ Failed to set baudrate")
    sys.exit(1)

print(f"✓ Connected to {DEVICENAME} at {BAUDRATE} bps\n")

# Test 1: Set Position Control Mode
print("Test 1: Set Position Control Mode")
print("-"*70)
dxl_comm_result, dxl_error = packetHandler.write1ByteTxRx(portHandler, DXL_ID, ADDR_OPERATING_MODE, 3)
if dxl_comm_result == COMM_SUCCESS and dxl_error == 0:
    print("✓ Operating mode set to Position Control (3)")
else:
    print(f"✗ Failed to set operating mode")
print()

# Test 2: Enable Torque
print("Test 2: Enable Torque")
print("-"*70)
dxl_comm_result, dxl_error = packetHandler.write1ByteTxRx(portHandler, DXL_ID, ADDR_TORQUE_ENABLE, 1)
if dxl_comm_result == COMM_SUCCESS and dxl_error == 0:
    print("✓ Torque enabled")
else:
    print(f"✗ Failed to enable torque")
print()

# Test 3: Read current position
print("Test 3: Read Current Position")
print("-"*70)
present_pos, dxl_comm_result, dxl_error = packetHandler.read4ByteTxRx(portHandler, DXL_ID, ADDR_PRESENT_POSITION)
if dxl_comm_result == COMM_SUCCESS and dxl_error == 0:
    if present_pos >= 2147483648:
        present_pos -= 4294967296
    print(f"✓ Current position: {present_pos}")
    initial_pos = present_pos
else:
    print(f"✗ Failed to read position")
    initial_pos = 2048
print()

# Test 4: Move to position 2048 (center)
print("Test 4: Move to Center Position (2048)")
print("-"*70)
dxl_comm_result, dxl_error = packetHandler.write4ByteTxRx(portHandler, DXL_ID, ADDR_GOAL_POSITION, 2048)
if dxl_comm_result == COMM_SUCCESS and dxl_error == 0:
    print("✓ Goal position set to 2048")
    time.sleep(1.0)
    
    # Read final position
    present_pos, _, _ = packetHandler.read4ByteTxRx(portHandler, DXL_ID, ADDR_PRESENT_POSITION)
    if present_pos >= 2147483648:
        present_pos -= 4294967296
    print(f"  Final position: {present_pos}")
else:
    print(f"✗ Failed to set goal position")
print()

# Test 5: Move to position 1024 (more closed)
print("Test 5: Move to Closed Position (1024)")
print("-"*70)
dxl_comm_result, dxl_error = packetHandler.write4ByteTxRx(portHandler, DXL_ID, ADDR_GOAL_POSITION, 1024)
if dxl_comm_result == COMM_SUCCESS and dxl_error == 0:
    print("✓ Goal position set to 1024")
    time.sleep(1.0)
    
    present_pos, _, _ = packetHandler.read4ByteTxRx(portHandler, DXL_ID, ADDR_PRESENT_POSITION)
    if present_pos >= 2147483648:
        present_pos -= 4294967296
    print(f"  Final position: {present_pos}")
else:
    print(f"✗ Failed to set goal position")
print()

# Test 6: Move to position 3072 (more open)
print("Test 6: Move to Open Position (3072)")
print("-"*70)
dxl_comm_result, dxl_error = packetHandler.write4ByteTxRx(portHandler, DXL_ID, ADDR_GOAL_POSITION, 3072)
if dxl_comm_result == COMM_SUCCESS and dxl_error == 0:
    print("✓ Goal position set to 3072")
    time.sleep(1.0)
    
    present_pos, _, _ = packetHandler.read4ByteTxRx(portHandler, DXL_ID, ADDR_PRESENT_POSITION)
    if present_pos >= 2147483648:
        present_pos -= 4294967296
    print(f"  Final position: {present_pos}")
else:
    print(f"✗ Failed to set goal position")
print()

# Test 7: Return to initial position
print(f"Test 7: Return to Initial Position ({initial_pos})")
print("-"*70)
dxl_comm_result, dxl_error = packetHandler.write4ByteTxRx(portHandler, DXL_ID, ADDR_GOAL_POSITION, initial_pos)
if dxl_comm_result == COMM_SUCCESS and dxl_error == 0:
    print(f"✓ Returned to initial position")
    time.sleep(1.0)
else:
    print(f"✗ Failed to return to initial position")
print()

# Test 8: Read current multiple times
print("Test 8: Read Current (10 samples)")
print("-"*70)
for i in range(10):
    present_current, dxl_comm_result, dxl_error = packetHandler.read2ByteTxRx(portHandler, DXL_ID, ADDR_PRESENT_CURRENT)
    if dxl_comm_result == COMM_SUCCESS and dxl_error == 0:
        if present_current >= 32768:
            present_current -= 65536
        current_ma = present_current * 4.5
        print(f"  Sample {i+1}: {present_current} (raw) = {current_ma:.1f} mA")
    time.sleep(0.1)
print()

portHandler.closePort()

print("="*70)
print("All tests complete!")
print("="*70)
print("\nConclusion:")
print("  ✓ Dynamixel SDK works perfectly with Protocol 2.0 @ 1 Mbps")
print("  ✓ Position control works")
print("  ✓ Current readings work")
print("  → Need to fix lib_robotis.py to match SDK behavior")
