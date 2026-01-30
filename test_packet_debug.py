#!/usr/bin/env python3
"""Debug: Compare library packet vs raw packet byte-by-byte"""

import sys
sys.path.insert(0, '/home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver')
from libezgripper import lib_robotis

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

print("="*70)
print("Packet Format Debug - Library vs Raw")
print("="*70)

# What the library would build for reading register 132 (Present Position), 4 bytes
address = 132
nBytes = 4

# Library's read_address method builds this instruction
addr_l = address & 0xFF
addr_h = (address >> 8) & 0xFF
len_l = nBytes & 0xFF
len_h = (nBytes >> 8) & 0xFF
instruction = [0x02, addr_l, addr_h, len_l, len_h]

# Library's send_instruction builds the full packet
length = len(instruction) + 3  # instruction + params + CRC(2)
len_l = length & 0xFF
len_h = (length >> 8) & 0xFF
packet_base = [0xFF, 0xFF, 0xFD, 0x00, 1, len_l, len_h] + instruction

# Calculate CRC using library's method
servo_id = 1
dyn = lib_robotis.USB2Dynamixel_Device('/dev/ttyUSB0', 1000000)
servo = lib_robotis.Robotis_Servo(dyn, servo_id)
crc = servo._Robotis_Servo__calc_crc(packet_base)
crc_l = crc & 0xFF
crc_h = (crc >> 8) & 0xFF
library_packet = packet_base + [crc_l, crc_h]

print("\nLibrary packet:")
print(f"  {library_packet}")
print(f"  Length: {len(library_packet)} bytes")

# Raw test packet
addr_l = 132 & 0xFF
addr_h = (132 >> 8) & 0xFF
len_l = 4 & 0xFF
len_h = (4 >> 8) & 0xFF
packet_len = 7
plen_l = packet_len & 0xFF
plen_h = (packet_len >> 8) & 0xFF
raw_packet_base = [0xFF, 0xFF, 0xFD, 0x00, 1, plen_l, plen_h, 0x02, addr_l, addr_h, len_l, len_h]
raw_crc = calc_crc16(raw_packet_base)
raw_packet = raw_packet_base + [raw_crc & 0xFF, (raw_crc >> 8) & 0xFF]

print("\nRaw test packet:")
print(f"  {raw_packet}")
print(f"  Length: {len(raw_packet)} bytes")

print("\nComparison:")
print("-"*70)
if library_packet == raw_packet:
    print("✓ Packets are IDENTICAL")
else:
    print("✗ Packets are DIFFERENT")
    print("\nByte-by-byte comparison:")
    for i in range(max(len(library_packet), len(raw_packet))):
        lib_byte = library_packet[i] if i < len(library_packet) else "N/A"
        raw_byte = raw_packet[i] if i < len(raw_packet) else "N/A"
        match = "✓" if lib_byte == raw_byte else "✗"
        print(f"  [{i:2d}] Library: {lib_byte:3} (0x{lib_byte:02X} if isinstance(lib_byte, int) else 'N/A') | Raw: {raw_byte:3} (0x{raw_byte:02X}) {match}")

print("\n" + "="*70)
