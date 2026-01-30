#!/usr/bin/env python3
"""Simplest possible Protocol 2.0 read test"""

import sys
import time
import serial

def calc_crc16(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF

device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"

print("Simple Protocol 2.0 Read Test")
print("="*70)

ser = serial.Serial(device, 1000000, timeout=0.5)
time.sleep(0.1)

# Read ID register (address 7, 1 byte) - simplest possible read
print("\nReading ID register (address 7, 1 byte)...")
print("-"*70)

# Build packet exactly as per Protocol 2.0 spec
packet_base = [
    0xFF, 0xFF, 0xFD, 0x00,  # Header
    0x01,                     # ID
    0x07, 0x00,              # Length = 7 (inst + 4 params + 2 crc)
    0x02,                     # Instruction (READ)
    0x07, 0x00,              # Address = 7 (low, high)
    0x01, 0x00               # Length = 1 byte (low, high)
]

crc = calc_crc16(packet_base)
packet = packet_base + [crc & 0xFF, (crc >> 8) & 0xFF]

print(f"Sending: {packet}")
print(f"  Header: {packet[0:4]}")
print(f"  ID: {packet[4]}")
print(f"  Packet Length: {packet[5] + (packet[6] << 8)}")
print(f"  Instruction: 0x{packet[7]:02X} (READ)")
print(f"  Address: {packet[8] + (packet[9] << 8)}")
print(f"  Data Length: {packet[10] + (packet[11] << 8)}")
print(f"  CRC: 0x{packet[12]:02X}{packet[13]:02X}")

ser.reset_input_buffer()
ser.write(bytes(packet))
time.sleep(0.05)

response = ser.read(100)
print(f"\nReceived {len(response)} bytes: {list(response)}")

if len(response) >= 11:
    print(f"  Header: {list(response[0:4])}")
    print(f"  ID: {response[4]}")
    print(f"  Length: {response[5] + (response[6] << 8)}")
    print(f"  Instruction: 0x{response[7]:02X}")
    print(f"  Error: {response[8]} (0=OK, 3=Data Range Error)")
    if len(response) > 9:
        print(f"  Data: {list(response[9:-2])}")
        if response[8] == 0 and len(response) > 9:
            print(f"  ID value: {response[9]}")

ser.close()

print("\n" + "="*70)
print("If Error=3, the servo is rejecting the command.")
print("If Error=0, the command succeeded.")
