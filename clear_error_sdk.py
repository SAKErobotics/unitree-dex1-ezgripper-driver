#!/usr/bin/env python3
"""Clear hardware error using Dynamixel SDK"""

import sys
import time
from dynamixel_sdk import *

ADDR_TORQUE_ENABLE = 64
ADDR_HARDWARE_ERROR = 70
PROTOCOL_VERSION = 2.0
DXL_ID = 1
BAUDRATE = 1000000
DEVICENAME = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'

print("="*70)
print("Clear Hardware Error with Dynamixel SDK")
print("="*70)

portHandler = PortHandler(DEVICENAME)
packetHandler = PacketHandler(PROTOCOL_VERSION)

if not portHandler.openPort():
    print("✗ Failed to open port")
    sys.exit(1)

if not portHandler.setBaudRate(BAUDRATE):
    print("✗ Failed to set baudrate")
    sys.exit(1)

print(f"✓ Connected to {DEVICENAME} at {BAUDRATE} bps\n")

# Step 1: Try to read current error status (will fail if error is active)
print("Step 1: Check current error status")
print("-"*70)
hw_error, comm_result, dxl_error = packetHandler.read1ByteTxRx(portHandler, DXL_ID, ADDR_HARDWARE_ERROR)
print(f"Communication result: {packetHandler.getTxRxResult(comm_result)}")
if dxl_error != 0:
    print(f"Dynamixel error: {packetHandler.getRxPacketError(dxl_error)}")
print(f"Hardware Error Status: {hw_error if comm_result == COMM_SUCCESS else 'Cannot read (error active)'}")
print()

# Step 2: Disable torque (required to clear error)
print("Step 2: Disable torque")
print("-"*70)
comm_result, dxl_error = packetHandler.write1ByteTxRx(portHandler, DXL_ID, ADDR_TORQUE_ENABLE, 0)
if comm_result == COMM_SUCCESS:
    print("✓ Torque disabled")
else:
    print(f"Communication: {packetHandler.getTxRxResult(comm_result)}")
if dxl_error != 0:
    print(f"Dynamixel error: {packetHandler.getRxPacketError(dxl_error)}")
time.sleep(0.2)
print()

# Step 3: Clear hardware error by writing 0
print("Step 3: Clear hardware error (write 0 to register 70)")
print("-"*70)
comm_result, dxl_error = packetHandler.write1ByteTxRx(portHandler, DXL_ID, ADDR_HARDWARE_ERROR, 0)
if comm_result == COMM_SUCCESS:
    print("✓ Write command sent")
else:
    print(f"✗ Communication failed: {packetHandler.getTxRxResult(comm_result)}")
if dxl_error != 0:
    print(f"Dynamixel error: {packetHandler.getRxPacketError(dxl_error)}")
time.sleep(0.2)
print()

# Step 4: Verify error is cleared
print("Step 4: Verify error cleared")
print("-"*70)
hw_error, comm_result, dxl_error = packetHandler.read1ByteTxRx(portHandler, DXL_ID, ADDR_HARDWARE_ERROR)
if comm_result == COMM_SUCCESS and dxl_error == 0:
    if hw_error == 0:
        print(f"✓ Hardware Error Status: {hw_error} (CLEARED)")
    else:
        print(f"✗ Hardware Error Status: {hw_error} (NOT CLEARED)")
        print(f"   Error bits: {bin(hw_error)}")
else:
    print(f"✗ Failed to verify: {packetHandler.getTxRxResult(comm_result)}")
    if dxl_error != 0:
        print(f"   Dynamixel error: {packetHandler.getRxPacketError(dxl_error)}")
print()

# Step 5: Re-enable torque
print("Step 5: Re-enable torque")
print("-"*70)
comm_result, dxl_error = packetHandler.write1ByteTxRx(portHandler, DXL_ID, ADDR_TORQUE_ENABLE, 1)
if comm_result == COMM_SUCCESS and dxl_error == 0:
    print("✓ Torque re-enabled")
else:
    print(f"Communication: {packetHandler.getTxRxResult(comm_result)}")
    if dxl_error != 0:
        print(f"Dynamixel error: {packetHandler.getRxPacketError(dxl_error)}")
print()

portHandler.closePort()

print("="*70)
print("Done!")
print("="*70)
