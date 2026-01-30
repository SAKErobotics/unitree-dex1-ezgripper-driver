#!/usr/bin/env python3
"""Enable torque and verify servo is ready"""

import sys
import time
import serial

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

def send_read_command(ser, servo_id, address, length):
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

def send_write_command(ser, servo_id, address, data):
    """Send Protocol 2.0 write command"""
    addr_l = address & 0xFF
    addr_h = (address >> 8) & 0xFF
    
    packet_len = 3 + len(data) + 2  # inst + addr(2) + data + crc(2)
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

def main():
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    
    print("="*70)
    print("Enable Torque and Verify Servo")
    print("="*70)
    print(f"Device: {device}\n")
    
    try:
        ser = serial.Serial(device, 1000000, timeout=0.5)
        time.sleep(0.1)
        
        # Read Hardware Error Status (register 70)
        print("Step 1: Check Hardware Error Status (register 70)")
        print("-"*70)
        response = send_read_command(ser, 1, 70, 1)
        if response and len(response) >= 10:
            error_status = response[8]
            hw_error = response[9] if len(response) > 9 else 0
            print(f"Error byte: {error_status}")
            print(f"Hardware Error Status: {hw_error}")
            if hw_error != 0:
                print(f"⚠ Hardware error detected: {hw_error}")
                print("  Bit 0 (1): Input Voltage Error")
                print("  Bit 2 (4): Overheating Error")
                print("  Bit 3 (8): Motor Encoder Error")
                print("  Bit 4 (16): Electrical Shock Error")
                print("  Bit 5 (32): Overload Error")
            else:
                print("✓ No hardware errors")
        print()
        
        # Read Torque Enable (register 64)
        print("Step 2: Check Torque Enable (register 64)")
        print("-"*70)
        response = send_read_command(ser, 1, 64, 1)
        if response and len(response) >= 10:
            error_status = response[8]
            torque_enable = response[9] if len(response) > 9 else 0
            print(f"Error byte: {error_status}")
            print(f"Torque Enable: {torque_enable}")
            if torque_enable == 0:
                print("⚠ Torque is DISABLED")
            else:
                print("✓ Torque is ENABLED")
        print()
        
        # Enable Torque if disabled
        print("Step 3: Enable Torque (write 1 to register 64)")
        print("-"*70)
        response = send_write_command(ser, 1, 64, [1])
        if response and len(response) >= 9:
            error_status = response[8]
            print(f"Error byte: {error_status}")
            if error_status == 0:
                print("✓ Torque enabled successfully")
            else:
                print(f"✗ Error enabling torque: {error_status}")
        print()
        
        # Verify Torque Enable
        print("Step 4: Verify Torque Enable")
        print("-"*70)
        response = send_read_command(ser, 1, 64, 1)
        if response and len(response) >= 10:
            error_status = response[8]
            torque_enable = response[9] if len(response) > 9 else 0
            print(f"Error byte: {error_status}")
            print(f"Torque Enable: {torque_enable}")
            if torque_enable == 1 and error_status == 0:
                print("✓ Torque is now ENABLED and ready")
            else:
                print(f"✗ Issue: torque={torque_enable}, error={error_status}")
        print()
        
        # Test reading position
        print("Step 5: Test reading Present Position (register 132)")
        print("-"*70)
        response = send_read_command(ser, 1, 132, 4)
        if response and len(response) >= 13:
            error_status = response[8]
            print(f"Error byte: {error_status}")
            if error_status == 0:
                pos_bytes = response[9:13]
                position = pos_bytes[0] + (pos_bytes[1] << 8) + (pos_bytes[2] << 16) + (pos_bytes[3] << 24)
                if position >= 2147483648:
                    position -= 4294967296
                print(f"✓ Position read successfully: {position}")
            else:
                print(f"✗ Error reading position: {error_status}")
        
        ser.close()
        
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    main()
