#!/usr/bin/env python3
"""
Scan for servo IDs at Protocol 2.0 @ 1 Mbps
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

def ping_servo(ser, servo_id):
    """Send Protocol 2.0 ping to specific ID"""
    # Protocol 2.0 ping packet
    packet_base = [0xFF, 0xFF, 0xFD, 0x00, servo_id, 3, 0, 0x01]
    crc = calc_crc16(packet_base)
    msg = packet_base + [crc & 0xFF, (crc >> 8) & 0xFF]
    
    # Clear buffer
    ser.reset_input_buffer()
    
    # Send ping
    ser.write(bytes(msg))
    time.sleep(0.01)
    
    # Read response
    response = ser.read(100)
    return len(response) > 0, list(response) if len(response) > 0 else None

def main():
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    baudrate = 1000000
    
    print("="*70)
    print("Scanning for Dynamixel Servos")
    print("="*70)
    print(f"Device: {device}")
    print(f"Baudrate: {baudrate} (1 Mbps)")
    print(f"Protocol: 2.0")
    print()
    
    try:
        ser = serial.Serial(device, baudrate, timeout=0.1)
        
        found_servos = []
        
        print("Scanning IDs 0-253...")
        for servo_id in range(254):
            if servo_id % 50 == 0:
                print(f"  Checking ID {servo_id}...", flush=True)
            
            success, response = ping_servo(ser, servo_id)
            
            if success:
                print(f"\n✓ Found servo at ID {servo_id}!")
                print(f"  Response: {response[:20]}...")
                found_servos.append(servo_id)
        
        ser.close()
        
        print("\n" + "="*70)
        print("Scan Results")
        print("="*70)
        
        if found_servos:
            print(f"\n✓ Found {len(found_servos)} servo(s):")
            for servo_id in found_servos:
                print(f"  • ID {servo_id}")
        else:
            print("\n✗ No servos found!")
            print("\nTroubleshooting:")
            print("  1. Check servo is powered (LED should be on)")
            print("  2. Check USB2Dynamixel switch position")
            print("  3. Verify cable connections")
            print("  4. Try running: sudo chmod 666 /dev/ttyUSB0")
            print("  5. Servo may be at different baudrate")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
