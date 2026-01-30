#!/usr/bin/env python3
"""Test Protocol 2.0 communication using official Dynamixel SDK"""

import sys
from dynamixel_sdk import *

# Control table addresses for MX-64(2.0)
ADDR_TORQUE_ENABLE = 64
ADDR_HARDWARE_ERROR = 70
ADDR_GOAL_POSITION = 116
ADDR_PRESENT_POSITION = 132
ADDR_PRESENT_CURRENT = 126

# Protocol version
PROTOCOL_VERSION = 2.0

# Default settings
DXL_ID = 1
BAUDRATE = 1000000
DEVICENAME = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'

print("="*70)
print("Dynamixel SDK Protocol 2.0 Test")
print("="*70)
print(f"Device: {DEVICENAME}")
print(f"Baudrate: {BAUDRATE}")
print(f"ID: {DXL_ID}\n")

# Initialize PortHandler and PacketHandler
portHandler = PortHandler(DEVICENAME)
packetHandler = PacketHandler(PROTOCOL_VERSION)

# Open port
if portHandler.openPort():
    print("✓ Port opened successfully")
else:
    print("✗ Failed to open port")
    sys.exit(1)

# Set baudrate
if portHandler.setBaudRate(BAUDRATE):
    print(f"✓ Baudrate set to {BAUDRATE}")
else:
    print("✗ Failed to set baudrate")
    sys.exit(1)

print()

# Test 1: Read Hardware Error Status
print("Test 1: Read Hardware Error Status (register 70)")
print("-"*70)
hw_error, dxl_comm_result, dxl_error = packetHandler.read1ByteTxRx(portHandler, DXL_ID, ADDR_HARDWARE_ERROR)
if dxl_comm_result != COMM_SUCCESS:
    print(f"✗ Communication failed: {packetHandler.getTxRxResult(dxl_comm_result)}")
elif dxl_error != 0:
    print(f"✗ Dynamixel error: {packetHandler.getRxPacketError(dxl_error)}")
else:
    print(f"✓ Hardware Error Status: {hw_error}")
    if hw_error == 0:
        print("  No hardware errors")
    else:
        print(f"  Error bits: {bin(hw_error)}")
print()

# Test 2: Read Torque Enable
print("Test 2: Read Torque Enable (register 64)")
print("-"*70)
torque_enable, dxl_comm_result, dxl_error = packetHandler.read1ByteTxRx(portHandler, DXL_ID, ADDR_TORQUE_ENABLE)
if dxl_comm_result != COMM_SUCCESS:
    print(f"✗ Communication failed: {packetHandler.getTxRxResult(dxl_comm_result)}")
elif dxl_error != 0:
    print(f"✗ Dynamixel error: {packetHandler.getRxPacketError(dxl_error)}")
else:
    print(f"✓ Torque Enable: {torque_enable} ({'ON' if torque_enable else 'OFF'})")
print()

# Test 3: Read Present Position
print("Test 3: Read Present Position (register 132)")
print("-"*70)
present_position, dxl_comm_result, dxl_error = packetHandler.read4ByteTxRx(portHandler, DXL_ID, ADDR_PRESENT_POSITION)
if dxl_comm_result != COMM_SUCCESS:
    print(f"✗ Communication failed: {packetHandler.getTxRxResult(dxl_comm_result)}")
elif dxl_error != 0:
    print(f"✗ Dynamixel error: {packetHandler.getRxPacketError(dxl_error)}")
else:
    # Handle signed 32-bit integer
    if present_position >= 2147483648:
        present_position -= 4294967296
    print(f"✓ Present Position: {present_position}")
print()

# Test 4: Read Present Current
print("Test 4: Read Present Current (register 126)")
print("-"*70)
present_current, dxl_comm_result, dxl_error = packetHandler.read2ByteTxRx(portHandler, DXL_ID, ADDR_PRESENT_CURRENT)
if dxl_comm_result != COMM_SUCCESS:
    print(f"✗ Communication failed: {packetHandler.getTxRxResult(dxl_comm_result)}")
elif dxl_error != 0:
    print(f"✗ Dynamixel error: {packetHandler.getRxPacketError(dxl_error)}")
else:
    # Handle signed 16-bit integer
    if present_current >= 32768:
        present_current -= 65536
    current_ma = present_current * 4.5
    print(f"✓ Present Current: {present_current} (raw) = {current_ma:.1f} mA")
print()

# Test 5: Write Goal Position (if torque enabled)
if torque_enable == 1:
    print("Test 5: Write Goal Position (move to 2048)")
    print("-"*70)
    dxl_comm_result, dxl_error = packetHandler.write4ByteTxRx(portHandler, DXL_ID, ADDR_GOAL_POSITION, 2048)
    if dxl_comm_result != COMM_SUCCESS:
        print(f"✗ Communication failed: {packetHandler.getTxRxResult(dxl_comm_result)}")
    elif dxl_error != 0:
        print(f"✗ Dynamixel error: {packetHandler.getRxPacketError(dxl_error)}")
    else:
        print(f"✓ Goal position set to 2048")
    print()

# Close port
portHandler.closePort()
print("="*70)
print("Test complete!")
print("="*70)
