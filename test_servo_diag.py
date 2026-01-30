#!/usr/bin/env python3
"""
Proper Servo Diagnostic
Check if we're actually talking to the servo at all
"""

import serial
import struct
import time
import sys

def calculate_crc(data):
    """Calculate CRC for Dynamixel Protocol 2.0"""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x01:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

def ping_servo(ser, servo_id):
    """Ping a servo and return response"""
    # Build ping packet
    packet = bytearray([0xFF, 0xFF, 0xFD, 0x00,  # Header
                       servo_id,  # ID
                       0x03, 0x00,  # Length (3)
                       0x01,  # Instruction (Ping)
                       0x00])  # Reserved
    
    # Add CRC
    crc = calculate_crc(packet[4:])
    packet.extend([crc & 0xFF, (crc >> 8) & 0xFF])
    
    print(f"Sending ping to ID {servo_id}: {packet.hex()}")
    
    ser.write(packet)
    time.sleep(0.01)
    response = ser.read(20)
    
    print(f"Response: {response.hex() if response else 'None'}")
    
    if response:
        if len(response) >= 8:
            if response[4] == 0x55:
                print(f"  ERROR packet received!")
                error_code = response[8] if len(response) > 8 else 0
                print(f"  Error code: {error_code}")
                return False, error_code
            elif response[4] == 0x01:
                print(f"  SUCCESS - Ping response from ID {response[5]}")
                return True, response[5]
    
    return False, None

def read_register(ser, servo_id, address, size=2):
    """Read a register from servo"""
    # Build read packet
    packet = bytearray([0xFF, 0xFF, 0xFD, 0x00,  # Header
                       servo_id,  # ID
                       0x07, 0x00,  # Length (7)
                       0x02,  # Instruction (Read)
                       address, 0x00,  # Address
                       size, 0x00,  # Size
                       0x00])  # Reserved
    
    # Add CRC
    crc = calculate_crc(packet[4:])
    packet.extend([crc & 0xFF, (crc >> 8) & 0xFF])
    
    print(f"\nReading register {address} (size {size}) from ID {servo_id}")
    print(f"Packet: {packet.hex()}")
    
    ser.write(packet)
    time.sleep(0.01)
    response = ser.read(20)
    
    print(f"Response: {response.hex() if response else 'None'}")
    
    if response and len(response) >= 11:
        if response[4] == 0x55:
            error_code = response[8]
            print(f"  ERROR: {error_code}")
            return None
        elif response[4] == 0x02:
            data_len = response[6]
            data = response[8:8+data_len]
            print(f"  Data: {data.hex()}")
            if size == 1:
                return data[0]
            elif size == 2:
                return data[0] | (data[1] << 8)
            elif size == 4:
                return data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24)
    
    return None

def main():
    device = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
    
    print("="*70)
    print("  SERVO DIAGNOSTIC")
    print("="*70)
    print(f"Device: {device}")
    
    try:
        # Try different baud rates
        baud_rates = [1000000, 57600, 115200, 2000000]
        
        for baud in baud_rates:
            print(f"\n--- Trying {baud} baud ---")
            
            ser = serial.Serial(device, baud, timeout=0.1)
            print(f"Serial port opened at {baud}")
            
            # Try pinging different IDs
            for servo_id in [1, 2, 3, 253]:  # 253 is broadcast
                success, result = ping_servo(ser, servo_id)
                if success:
                    print(f"\n✓ Found servo at ID {result}")
                    
                    # Read some basic registers
                    model = read_register(ser, result, 2, 2)  # Model number
                    firmware = read_register(ser, result, 6, 1)  # Firmware version
                    mode = read_register(ser, result, 11, 1)  # Operating mode
                    
                    print(f"\nServo {result} Info:")
                    print(f"  Model: {model}")
                    print(f"  Firmware: {firmware}")
                    print(f"  Operating Mode: {mode}")
                    
                    ser.close()
                    return
            
            ser.close()
        
        print("\n✗ No servo found at any baud rate or ID")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
