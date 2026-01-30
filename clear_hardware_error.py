#!/usr/bin/env python3
"""
Clear hardware error on servo
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
    
    packet_len = 5 + len(data)
    plen_l = packet_len & 0xFF
    plen_h = (packet_len >> 8) & 0xFF
    
    packet_base = [0xFF, 0xFF, 0xFD, 0x00, servo_id, plen_l, plen_h, 0x03, addr_l, addr_h] + data
    crc = calc_crc16(packet_base)
    packet = packet_base + [crc & 0xFF, (crc >> 8) & 0xFF]
    
    print(f"  Sending: {packet}")
    ser.reset_input_buffer()
    ser.write(bytes(packet))
    time.sleep(0.1)
    
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
    time.sleep(0.1)
    
    response = ser.read(100)
    return list(response) if len(response) > 0 else None

def main():
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    
    print("="*70)
    print("Clear Servo Hardware Error")
    print("="*70)
    print(f"Device: {device}\n")
    
    try:
        ser = serial.Serial(device, 1000000, timeout=0.5)
        time.sleep(0.1)
        
        # Step 1: Read current error status
        print("Step 1: Read Hardware Error Status (register 70)")
        print("-"*70)
        response = read_command(ser, 1, 70, 1)
        if response and len(response) >= 10:
            hw_error = response[9] if len(response) > 9 else 0
            print(f"  Hardware Error Status: {hw_error} (0x{hw_error:02X})")
            print(f"  Binary: {bin(hw_error)}")
            errors = []
            if hw_error & 0x01: errors.append("Input Voltage")
            if hw_error & 0x04: errors.append("Overheating")
            if hw_error & 0x08: errors.append("Motor Encoder")
            if hw_error & 0x10: errors.append("Electrical Shock")
            if hw_error & 0x20: errors.append("Overload")
            if hw_error & 0x80: errors.append("Instruction")
            print(f"  Errors: {', '.join(errors) if errors else 'None'}")
        
        print()
        
        # Step 2: Disable torque first (required before clearing error)
        print("Step 2: Disable Torque (write 0 to register 64)")
        print("-"*70)
        response = write_command(ser, 1, 64, [0])
        if response:
            print(f"  Response: {response}")
            if len(response) >= 9:
                error = response[8]
                print(f"  Error: {error}")
        
        time.sleep(0.2)
        print()
        
        # Step 3: Set Operating Mode to Position Control (register 11 = 3)
        print("Step 3: Set Operating Mode to Position Control (register 11 = 3)")
        print("-"*70)
        response = write_command(ser, 1, 11, [3])
        if response:
            print(f"  Response: {response}")
            if len(response) >= 9:
                error = response[8]
                print(f"  Error: {error}")
        
        time.sleep(0.2)
        print()
        
        # Step 4: Clear hardware error (write 0 to register 70)
        print("Step 4: Clear Hardware Error Status (write 0 to register 70)")
        print("-"*70)
        response = write_command(ser, 1, 70, [0])
        if response:
            print(f"  Response: {response}")
            if len(response) >= 9:
                error = response[8]
                print(f"  Error: {error} ({'Success' if error == 0 else 'Failed'})")
        
        time.sleep(0.2)
        print()
        
        # Step 5: Verify error is cleared
        print("Step 5: Verify Hardware Error Status")
        print("-"*70)
        response = read_command(ser, 1, 70, 1)
        if response and len(response) >= 10:
            error_field = response[8]
            hw_error = response[9] if len(response) > 9 else 0
            print(f"  Error field: {error_field}")
            print(f"  Hardware Error Status: {hw_error} (0x{hw_error:02X})")
            if hw_error == 0:
                print("  ✓ Hardware error cleared!")
            else:
                print("  ✗ Hardware error still present")
        
        ser.close()
        
        print("\n" + "="*70)
        print("Done!")
        print("="*70)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
