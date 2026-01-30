#!/usr/bin/env python3
"""
Test raw Protocol 2.0 communication to debug packet format
"""

import serial
import time
import sys

def calc_crc16(data):
    """Calculate CRC-16 for Protocol 2.0"""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc = crc >> 1
    return crc & 0xFFFF

def send_read_command(ser, servo_id, address, length):
    """Send Protocol 2.0 read command"""
    # Protocol 2.0 READ: [0xFF, 0xFF, 0xFD, 0x00, ID, LEN_L, LEN_H, INST, ADDR_L, ADDR_H, LEN_L, LEN_H, CRC_L, CRC_H]
    # Instruction 0x02 = READ
    
    addr_l = address & 0xFF
    addr_h = (address >> 8) & 0xFF
    len_l = length & 0xFF
    len_h = (length >> 8) & 0xFF
    
    # Packet length = instruction(1) + params(4) + crc(2) = 7
    packet_len = 7
    plen_l = packet_len & 0xFF
    plen_h = (packet_len >> 8) & 0xFF
    
    packet_base = [0xFF, 0xFF, 0xFD, 0x00, servo_id, plen_l, plen_h, 0x02, addr_l, addr_h, len_l, len_h]
    crc = calc_crc16(packet_base)
    packet = packet_base + [crc & 0xFF, (crc >> 8) & 0xFF]
    
    print(f"Sending READ command:")
    print(f"  Address: {address}, Length: {length}")
    print(f"  Packet: {packet}")
    
    ser.reset_input_buffer()
    ser.write(bytes(packet))
    time.sleep(0.05)
    
    response = ser.read(100)
    return list(response) if len(response) > 0 else None

def main():
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    
    print("="*70)
    print("Raw Protocol 2.0 Communication Test")
    print("="*70)
    print(f"Device: {device}")
    print(f"Baudrate: 1000000 (1 Mbps)\n")
    
    try:
        ser = serial.Serial(device, 1000000, timeout=0.5)
        time.sleep(0.1)
        
        # Test 1: Read ID register (address 7, 1 byte)
        print("Test 1: Read ID register (address 7)")
        print("-"*70)
        response = send_read_command(ser, 1, 7, 1)
        if response:
            print(f"✓ Response received ({len(response)} bytes): {response}")
            if len(response) >= 11:
                # Parse response: [0xFF, 0xFF, 0xFD, 0x00, ID, LEN_L, LEN_H, INST, ERR, PARAM..., CRC_L, CRC_H]
                print(f"  Header: {response[0:4]}")
                print(f"  ID: {response[4]}")
                print(f"  Length: {response[5] + (response[6] << 8)}")
                print(f"  Instruction: {response[7]}")
                print(f"  Error: {response[8]}")
                if len(response) > 9:
                    print(f"  Data: {response[9:-2]}")
                print(f"  CRC: {response[-2:]}")
        else:
            print("✗ No response")
        
        print()
        
        # Test 2: Read Present Position (address 132, 4 bytes)
        print("Test 2: Read Present Position (address 132)")
        print("-"*70)
        response = send_read_command(ser, 1, 132, 4)
        if response:
            print(f"✓ Response received ({len(response)} bytes): {response}")
            if len(response) >= 13:
                print(f"  Header: {response[0:4]}")
                print(f"  ID: {response[4]}")
                print(f"  Error: {response[8]}")
                pos_bytes = response[9:13]
                position = pos_bytes[0] + (pos_bytes[1] << 8) + (pos_bytes[2] << 16) + (pos_bytes[3] << 24)
                if position >= 2147483648:
                    position -= 4294967296
                print(f"  Position (raw): {position}")
        else:
            print("✗ No response")
        
        print()
        
        # Test 3: Read Present Current (address 126, 2 bytes)
        print("Test 3: Read Present Current (address 126)")
        print("-"*70)
        response = send_read_command(ser, 1, 126, 2)
        if response:
            print(f"✓ Response received ({len(response)} bytes): {response}")
            if len(response) >= 11:
                print(f"  Header: {response[0:4]}")
                print(f"  ID: {response[4]}")
                print(f"  Error: {response[8]}")
                current_bytes = response[9:11]
                current_raw = current_bytes[0] + (current_bytes[1] << 8)
                current_ma = int(4.5 * (current_raw - 2048))
                print(f"  Current (raw): {current_raw}")
                print(f"  Current (mA): {current_ma}")
        else:
            print("✗ No response")
        
        ser.close()
        
        print("\n" + "="*70)
        print("Test complete")
        print("="*70)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
