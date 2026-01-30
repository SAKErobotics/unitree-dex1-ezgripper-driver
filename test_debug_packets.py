#!/usr/bin/env python3
"""Debug packet format - compare library vs raw"""

import sys
import time
import serial

sys.path.insert(0, '/home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver')
from libezgripper import lib_robotis

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

def main():
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    
    print("="*70)
    print("Packet Format Debug")
    print("="*70)
    print(f"Device: {device}\n")
    
    # Create library connection
    print("Creating library connection...")
    dyn = lib_robotis.USB2Dynamixel_Device(device, 1000000)
    servo = lib_robotis.Robotis_Servo(dyn, 1)
    
    # Build READ packet using library method
    print("\nLibrary READ packet for register 132 (Present Position), 4 bytes:")
    print("-"*70)
    
    # Manually construct what the library would send
    address = 132
    nBytes = 4
    
    addr_l = address & 0xFF
    addr_h = (address >> 8) & 0xFF
    len_l = nBytes & 0xFF
    len_h = (nBytes >> 8) & 0xFF
    
    instruction = [0x02, addr_l, addr_h, len_l, len_h]
    length = len(instruction) + 3  # instruction + params + CRC(2)
    len_l = length & 0xFF
    len_h = (length >> 8) & 0xFF
    
    packet_base = [0xFF, 0xFF, 0xFD, 0x00, 1, len_l, len_h] + instruction
    crc = servo._Robotis_Servo__calc_crc(packet_base)
    crc_l = crc & 0xFF
    crc_h = (crc >> 8) & 0xFF
    packet = packet_base + [crc_l, crc_h]
    
    print(f"Packet: {packet}")
    print(f"Length: {len(packet)} bytes")
    print(f"Breakdown:")
    print(f"  Header: {packet[0:4]}")
    print(f"  ID: {packet[4]}")
    print(f"  Length: {packet[5:7]} = {packet[5] + (packet[6] << 8)}")
    print(f"  Instruction: {packet[7]} (0x02 = READ)")
    print(f"  Address: {packet[8:10]} = {packet[8] + (packet[9] << 8)}")
    print(f"  Data Length: {packet[10:12]} = {packet[10] + (packet[11] << 8)}")
    print(f"  CRC: {packet[12:14]}")
    
    # Build raw packet for comparison
    print("\nRaw test READ packet for register 132, 4 bytes:")
    print("-"*70)
    
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
    
    print(f"Packet: {raw_packet}")
    print(f"Length: {len(raw_packet)} bytes")
    print(f"Breakdown:")
    print(f"  Header: {raw_packet[0:4]}")
    print(f"  ID: {raw_packet[4]}")
    print(f"  Length: {raw_packet[5:7]} = {raw_packet[5] + (raw_packet[6] << 8)}")
    print(f"  Instruction: {raw_packet[7]} (0x02 = READ)")
    print(f"  Address: {raw_packet[8:10]} = {raw_packet[8] + (raw_packet[9] << 8)}")
    print(f"  Data Length: {raw_packet[10:12]} = {raw_packet[10] + (raw_packet[11] << 8)}")
    print(f"  CRC: {raw_packet[12:14]}")
    
    print("\nComparison:")
    print("-"*70)
    if packet == raw_packet:
        print("✓ Packets are IDENTICAL")
    else:
        print("✗ Packets are DIFFERENT")
        for i in range(max(len(packet), len(raw_packet))):
            lib_byte = packet[i] if i < len(packet) else "N/A"
            raw_byte = raw_packet[i] if i < len(raw_packet) else "N/A"
            match = "✓" if lib_byte == raw_byte else "✗"
            print(f"  Byte {i}: Library={lib_byte}, Raw={raw_byte} {match}")
    
    # Now test sending the raw packet directly
    print("\nTesting raw packet send/receive:")
    print("-"*70)
    
    try:
        ser = serial.Serial(device, 1000000, timeout=0.5)
        time.sleep(0.1)
        
        ser.reset_input_buffer()
        ser.write(bytes(raw_packet))
        time.sleep(0.05)
        
        response = ser.read(100)
        if len(response) > 0:
            print(f"✓ Response received ({len(response)} bytes): {list(response)}")
        else:
            print("✗ No response received")
        
        ser.close()
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    main()
