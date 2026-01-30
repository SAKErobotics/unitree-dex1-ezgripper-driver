#!/usr/bin/env python3
"""Reboot servo to clear hardware error"""

import sys
import time
from dynamixel_sdk import *

ADDR_HARDWARE_ERROR = 70
ADDR_TORQUE_ENABLE = 64
PROTOCOL_VERSION = 2.0
DXL_ID = 1
BAUDRATE = 1000000
DEVICENAME = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'

print("="*70)
print("Reboot Servo to Clear Hardware Error")
print("="*70)

portHandler = PortHandler(DEVICENAME)
packetHandler = PacketHandler(PROTOCOL_VERSION)

if not portHandler.openPort():
    print("✗ Failed to open port")
    sys.exit(1)

if not portHandler.setBaudRate(BAUDRATE):
    print("✗ Failed to set baudrate")
    sys.exit(1)

print(f"✓ Connected\n")

# Check current error
print("Current status:")
hw_error, _, _ = packetHandler.read1ByteTxRx(portHandler, DXL_ID, ADDR_HARDWARE_ERROR)
print(f"  Hardware Error Status: {hw_error} (0x{hw_error:02X})")
print()

# Send REBOOT instruction (0x08)
print("Sending REBOOT instruction...")
print("-"*70)
comm_result = packetHandler.reboot(portHandler, DXL_ID)
print(f"Communication result: {packetHandler.getTxRxResult(comm_result)}")

if comm_result == COMM_SUCCESS:
    print("✓ Reboot command sent successfully")
else:
    print("✗ Reboot command failed")

# Wait for servo to reboot
print("\nWaiting 2 seconds for servo to reboot...")
time.sleep(2.0)

# Reconnect and verify
print("\nVerifying after reboot:")
print("-"*70)

# Try to ping the servo
model_num, comm_result, dxl_error = packetHandler.ping(portHandler, DXL_ID)
if comm_result == COMM_SUCCESS:
    print(f"✓ Servo responding (Model: {model_num})")
else:
    print(f"✗ Servo not responding: {packetHandler.getTxRxResult(comm_result)}")

# Check error status
hw_error, comm_result, dxl_error = packetHandler.read1ByteTxRx(portHandler, DXL_ID, ADDR_HARDWARE_ERROR)
if comm_result == COMM_SUCCESS:
    print(f"Hardware Error Status: {hw_error}")
    if hw_error == 0:
        print("✓ Error cleared!")
    else:
        print(f"✗ Error still present: 0x{hw_error:02X}")
        if hw_error & 32:
            print("  Bit 5: Overload Error")
    
    if dxl_error == 0:
        print("✓ No Dynamixel errors")
    else:
        print(f"Dynamixel error: {packetHandler.getRxPacketError(dxl_error)}")
else:
    print(f"✗ Cannot read error status: {packetHandler.getTxRxResult(comm_result)}")

# Test basic operation
print("\nTesting basic operation:")
print("-"*70)
position, comm_result, dxl_error = packetHandler.read4ByteTxRx(portHandler, DXL_ID, 132)
if comm_result == COMM_SUCCESS and dxl_error == 0:
    if position >= 2147483648:
        position -= 4294967296
    print(f"✓ Present Position: {position}")
    print("✓ Servo is operational!")
else:
    print(f"✗ Failed to read position")
    print(f"  Communication: {packetHandler.getTxRxResult(comm_result)}")
    if dxl_error != 0:
        print(f"  Dynamixel error: {packetHandler.getRxPacketError(dxl_error)}")

portHandler.closePort()

print("\n" + "="*70)
print("Done!")
print("="*70)
