#!/usr/bin/env python3
"""
Enable torque and test reading servo state
"""

import serial
import time
import sys

def calc_crc16(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc = crc >> 1
    return crc & 0xFFFF

def write_command(ser, servo_id, address, data):
    """Send Protocol 2.0 write command"""
    addr_l = address & 0xFF
    addr_h = (address >> 8) & 0xFF
    
    packet_len = 5 + len(data)  # inst(1) + addr(2) + data + crc(2)
    plen_l = packet_len & 0xFF
    plen_h = (packet_len >> 8) & 0xFF
    
    packet_base = [0xFF, 0xFF, 0xFD, 0x00, servo_id, plen_l, plen_h, 0x03, addr_l, addr_h] + data
    crc = calc_crc16(packet_base)
    packet = packet_base + [crc & 0xFF, (crc >> 8) & 0xFF]
    
    ser.reset_input_buffer()
    ser.write(bytes(packet))
    time.sleep(0.05)
    
    response = ser.read(100)
    return list(response) if len(response) > 0 else None

def read_command(ser, servo_id, address, length):
    """Send Protocol 2.0 read command"""
    addr_l = address & 0xFF
    addr_h = (address >> 8) & 0xFF
    len_l = length & 0xFF
    len_h = (length >> 8) & 0xFF
    
    packet_len = 7
    plen_l = packet_len & 0xFF
    plen_h = (packet_len >> 8) & 0xFF
    
    packet_base = [0xFF, 0xFF, 0xFD, 0x00, servo_id, plen_l, plen_h, 0x02, addr_l, addr_h, len_l, len_h]
    crc = calc_crc16(packet_base)
    packet = packet_base + [crc & 0xFF, (crc >> 8) & 0xFF]
    
    ser.reset_input_buffer()
    ser.write(bytes(packet))
    time.sleep(0.05)
    
    response = ser.read(100)
    return list(response) if len(response) > 0 else None

def main():
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    
    print("="*70)
    print("Enable Torque and Read Servo State")
    print("="*70)
    print(f"Device: {device}\n")
    
    try:
        ser = serial.Serial(device, 1000000, timeout=0.5)
        time.sleep(0.1)
        
        # Step 1: Read Hardware Error Status (address 70)
        print("Step 1: Read Hardware Error Status (register 70)")
        print("-"*70)
        response = read_command(ser, 1, 70, 1)
        if response and len(response) >= 10:
            error_status = response[8]
            hw_error = response[9] if len(response) > 9 else 0
            print(f"  Error field: {error_status}")
            print(f"  Hardware Error Status: {hw_error}")
        
        print()
        
        # Step 2: Enable Torque (write 1 to register 64)
        print("Step 2: Enable Torque (write 1 to register 64)")
        print("-"*70)
        response = write_command(ser, 1, 64, [1])
        if response:
            print(f"  Response: {response}")
            if len(response) >= 9:
                error = response[8]
                print(f"  Error: {error} ({'Success' if error == 0 else 'Error'})")
        
        time.sleep(0.2)
        print()
        
        # Step 3: Read Present Position
        print("Step 3: Read Present Position (register 132)")
        print("-"*70)
        response = read_command(ser, 1, 132, 4)
        if response:
            print(f"  Response ({len(response)} bytes): {response}")
            if len(response) >= 13:
                error = response[8]
                print(f"  Error: {error}")
                if error == 0:
                    pos_bytes = response[9:13]
                    position = pos_bytes[0] + (pos_bytes[1] << 8) + (pos_bytes[2] << 16) + (pos_bytes[3] << 24)
                    if position >= 2147483648:
                        position -= 4294967296
                    print(f"  ✓ Position: {position}")
        
        print()
        
        # Step 4: Read Present Current
        print("Step 4: Read Present Current (register 126)")
        print("-"*70)
        response = read_command(ser, 1, 126, 2)
        if response:
            print(f"  Response ({len(response)} bytes): {response}")
            if len(response) >= 11:
                error = response[8]
                print(f"  Error: {error}")
                if error == 0:
                    current_bytes = response[9:11]
                    current_raw = current_bytes[0] + (current_bytes[1] << 8)
                    current_ma = int(4.5 * (current_raw - 2048))
                    print(f"  ✓ Current (raw): {current_raw}")
                    print(f"  ✓ Current (mA): {current_ma}")
        
        ser.close()
        
        print("\n" + "="*70)
        print("Test complete!")
        print("="*70)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
