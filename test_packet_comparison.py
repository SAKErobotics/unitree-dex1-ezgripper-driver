#!/usr/bin/env python3
"""Compare our packet format with Dynamixel SDK expectations"""

import sys
sys.path.insert(0, '/home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver')

def calc_crc16(data):
    """Calculate CRC-16 for Protocol 2.0"""
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
print("Protocol 2.0 Packet Format Analysis")
print("="*70)

# According to Dynamixel SDK documentation:
# READ Instruction Packet:
# [0xFF][0xFF][0xFD][0x00][ID][LEN_L][LEN_H][INST][PARAM 1]...[PARAM N][CRC_L][CRC_H]
# 
# For READ:
# - INST = 0x02
# - PARAM 1 = Starting address (Low byte)
# - PARAM 2 = Starting address (High byte)  
# - PARAM 3 = Data length (Low byte)
# - PARAM 4 = Data length (High byte)
# - LEN = Length of (Instruction + Parameters + CRC) = 1 + 4 + 2 = 7

print("\nREAD Present Position (register 132, 4 bytes):")
print("-"*70)

# Our current implementation
address = 132
length = 4

addr_l = address & 0xFF
addr_h = (address >> 8) & 0xFF
len_l = length & 0xFF
len_h = (length >> 8) & 0xFF

# Packet length = instruction(1) + params(4) + crc(2) = 7
packet_len = 7
plen_l = packet_len & 0xFF
plen_h = (packet_len >> 8) & 0xFF

packet_base = [0xFF, 0xFF, 0xFD, 0x00, 1, plen_l, plen_h, 0x02, addr_l, addr_h, len_l, len_h]
crc = calc_crc16(packet_base)
packet = packet_base + [crc & 0xFF, (crc >> 8) & 0xFF]

print(f"Our packet: {packet}")
print(f"Breakdown:")
print(f"  [0xFF, 0xFF, 0xFD, 0x00] - Header")
print(f"  [0x{packet[4]:02X}] - ID = {packet[4]}")
print(f"  [0x{packet[5]:02X}, 0x{packet[6]:02X}] - Length = {packet[5] + (packet[6] << 8)}")
print(f"  [0x{packet[7]:02X}] - Instruction (READ)")
print(f"  [0x{packet[8]:02X}, 0x{packet[9]:02X}] - Address = {packet[8] + (packet[9] << 8)}")
print(f"  [0x{packet[10]:02X}, 0x{packet[11]:02X}] - Length = {packet[10] + (packet[11] << 8)}")
print(f"  [0x{packet[12]:02X}, 0x{packet[13]:02X}] - CRC")

print("\nExpected Status Packet (if successful):")
print("-"*70)
print("  [0xFF, 0xFF, 0xFD, 0x00] - Header")
print("  [0x01] - ID")
print("  [LEN_L, LEN_H] - Length = 4 (params) + 4 (CRC + Inst + Err) = 8")
print("  [0x55] - Instruction (STATUS = 0x55)")
print("  [0x00] - Error (0 = no error)")
print("  [DATA...] - 4 bytes of position data")
print("  [CRC_L, CRC_H] - CRC")

print("\nActual response we're getting:")
print("-"*70)
print("  [255, 255, 253, 0, 1, 4, 0, 85, 3, 171, 12]")
print("  Length = 4 (only inst + err + crc, NO data)")
print("  Error = 3 (Data Range Error)")
print("  This means the servo rejected our READ command as invalid!")

print("\n" + "="*70)
print("DIAGNOSIS:")
print("="*70)
print("The servo is rejecting our READ command with Error 3.")
print("This suggests the packet format or parameters are incorrect.")
print("\nPossible issues:")
print("1. Address 132 might not be readable in current operating mode")
print("2. Requesting 4 bytes might be invalid for this register")
print("3. Packet structure might not match Protocol 2.0 spec exactly")
print("\nLet's check the Dynamixel e-Manual for MX-64(2.0) register details...")
