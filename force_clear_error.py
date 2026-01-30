#!/usr/bin/env python3
"""Force clear hardware error - ignore error responses during clear"""

import sys
import time
from dynamixel_sdk import *

ADDR_TORQUE_ENABLE = 64
ADDR_HARDWARE_ERROR = 70
ADDR_OPERATING_MODE = 11
PROTOCOL_VERSION = 2.0
DXL_ID = 1
BAUDRATE = 1000000
DEVICENAME = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'

print("="*70)
print("Force Clear Hardware Error")
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

# Read current error (will show error but we can still read the value)
print("Current Hardware Error Status:")
hw_error, _, _ = packetHandler.read1ByteTxRx(portHandler, DXL_ID, ADDR_HARDWARE_ERROR)
print(f"  Register 70 = {hw_error} (0x{hw_error:02X})")
if hw_error & 32:
    print("  Bit 5 (32): Overload Error")
print()

# Strategy: Send multiple clear commands, ignoring error responses
print("Attempting to clear error (sending multiple commands)...")
print("-"*70)

for attempt in range(5):
    print(f"Attempt {attempt + 1}:")
    
    # Disable torque
    packetHandler.write1ByteTxRx(portHandler, DXL_ID, ADDR_TORQUE_ENABLE, 0)
    time.sleep(0.1)
    
    # Write 0 to error register
    packetHandler.write1ByteTxRx(portHandler, DXL_ID, ADDR_HARDWARE_ERROR, 0)
    time.sleep(0.1)
    
    # Check if cleared
    hw_error, comm_result, dxl_error = packetHandler.read1ByteTxRx(portHandler, DXL_ID, ADDR_HARDWARE_ERROR)
    
    if comm_result == COMM_SUCCESS and dxl_error == 0 and hw_error == 0:
        print(f"  ✓ Error cleared! Register 70 = {hw_error}")
        break
    else:
        print(f"  Register 70 = {hw_error}, still has error flag")
        time.sleep(0.5)
else:
    print("\n✗ Could not clear error after 5 attempts")
    print("\nThe Dynamixel firmware may require:")
    print("  1. Power cycle the servo")
    print("  2. Use Dynamixel Wizard's 'Reboot' function")
    print("  3. Check for actual hardware issues")
    portHandler.closePort()
    sys.exit(1)

print()

# Re-enable torque
print("Re-enabling torque...")
comm_result, dxl_error = packetHandler.write1ByteTxRx(portHandler, DXL_ID, ADDR_TORQUE_ENABLE, 1)
if comm_result == COMM_SUCCESS and dxl_error == 0:
    print("✓ Torque enabled")
else:
    print(f"⚠ Torque enable had issues but continuing...")

print()

# Final verification
print("Final verification:")
print("-"*70)
hw_error, comm_result, dxl_error = packetHandler.read1ByteTxRx(portHandler, DXL_ID, ADDR_HARDWARE_ERROR)
print(f"Hardware Error Status: {hw_error}")
print(f"Communication: {packetHandler.getTxRxResult(comm_result)}")
if dxl_error != 0:
    print(f"Dynamixel error: {packetHandler.getRxPacketError(dxl_error)}")
else:
    print("✓ No errors - servo is ready!")

# Test reading position to confirm servo is operational
print("\nTesting servo communication:")
position, comm_result, dxl_error = packetHandler.read4ByteTxRx(portHandler, DXL_ID, 132)
if comm_result == COMM_SUCCESS and dxl_error == 0:
    if position >= 2147483648:
        position -= 4294967296
    print(f"✓ Present Position: {position}")
else:
    print(f"✗ Failed to read position")

portHandler.closePort()

print("\n" + "="*70)
print("Done!")
print("="*70)
