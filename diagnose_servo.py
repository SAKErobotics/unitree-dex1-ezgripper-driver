#!/usr/bin/env python3
"""
Diagnose servo configuration - test all baudrate/protocol combinations
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

def test_config(device, baudrate, protocol, servo_id=1):
    """Test a specific baudrate/protocol combination"""
    try:
        ser = serial.Serial(device, baudrate, timeout=0.1)
        
        if protocol == 1:
            # Protocol 1.0 ping
            msg = [0xFF, 0xFF, servo_id, 2, 0x01]
            checksum = (~sum(msg[2:]))&0xFF
            msg.append(checksum)
        else:
            # Protocol 2.0 ping
            packet_base = [0xFF, 0xFF, 0xFD, 0x00, servo_id, 3, 0, 0x01]
            crc = calc_crc16(packet_base)
            msg = packet_base + [crc & 0xFF, (crc >> 8) & 0xFF]
        
        # Clear buffer
        ser.reset_input_buffer()
        
        # Send ping
        ser.write(bytes(msg))
        time.sleep(0.05)
        
        # Read response
        response = ser.read(100)
        ser.close()
        
        return len(response) > 0, list(response) if len(response) > 0 else None
        
    except Exception as e:
        return False, str(e)

def main():
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    
    print("="*70)
    print("Dynamixel Servo Configuration Diagnostic")
    print("="*70)
    print(f"Device: {device}\n")
    
    # Test common baudrates
    baudrates = [
        (1000000, "1 Mbps"),
        (57600, "57.6 kbps"),
        (115200, "115.2 kbps"),
        (500000, "500 kbps"),
    ]
    
    protocols = [1, 2]
    
    found_configs = []
    
    for baudrate, baud_name in baudrates:
        for protocol in protocols:
            proto_name = f"Protocol {protocol}.0"
            config_name = f"{proto_name} @ {baud_name}"
            
            print(f"Testing {config_name:30s}...", end=" ", flush=True)
            
            success, response = test_config(device, baudrate, protocol)
            
            if success:
                print(f"✓ FOUND! Response: {response[:10]}...")
                found_configs.append((baudrate, protocol, baud_name, proto_name))
            else:
                print("✗")
    
    print("\n" + "="*70)
    print("Results")
    print("="*70)
    
    if found_configs:
        print(f"\n✓ Found {len(found_configs)} working configuration(s):\n")
        for baudrate, protocol, baud_name, proto_name in found_configs:
            print(f"  • {proto_name} @ {baud_name}")
        
        # Determine what needs to be done
        target_found = any(b == 1000000 and p == 2 for b, p, _, _ in found_configs)
        
        print("\n" + "="*70)
        if target_found:
            print("✓ Servo is CORRECTLY configured for Protocol 2.0 @ 1 Mbps")
            print("  The code should work. Check for other issues.")
        else:
            print("⚠ Servo needs reconfiguration:")
            current = found_configs[0]
            print(f"  Current: {current[3]} @ {current[2]}")
            print(f"  Target:  Protocol 2.0 @ 1 Mbps")
            print("\nUse Dynamixel Wizard to:")
            if current[1] == 1:
                print("  1. Change Protocol Type to 2.0")
            if current[0] != 1000000:
                print("  2. Change Baud Rate to 1000000 (register value = 1)")
    else:
        print("\n✗ No working configuration found!")
        print("\nPossible issues:")
        print("  • Servo not powered")
        print("  • Wrong servo ID (trying ID 1)")
        print("  • USB2Dynamixel switch in wrong position")
        print("  • Cable connection problem")
        print("  • Servo using non-standard baudrate")

if __name__ == "__main__":
    main()
