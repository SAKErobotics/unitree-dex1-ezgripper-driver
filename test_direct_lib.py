#!/usr/bin/env python3
"""
Test using lib_robotis directly without Gripper wrapper
"""

import sys
from libezgripper.lib_robotis import USB2Dynamixel_Device, Robotis_Servo

def main():
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    
    print("="*70)
    print("Direct lib_robotis Test")
    print("="*70)
    print(f"Device: {device}\n")
    
    try:
        # Create connection
        print("Creating connection...")
        connection = USB2Dynamixel_Device(device, 1000000)
        print("✓ Connection created\n")
        
        # Create servo WITHOUT automatic ID verification
        print("Creating servo object...")
        servo = Robotis_Servo.__new__(Robotis_Servo)
        servo.dyn = connection
        servo.servo_id = 1
        servo.retry_count = 3
        print("✓ Servo object created\n")
        
        # Now try to communicate
        print("Test 1: Read Hardware Error Status (register 70)")
        print("-"*70)
        try:
            data = servo.read_address(70, 1)
            print(f"  ✓ Hardware Error Status: {data[0]} (0x{data[0]:02X})")
        except Exception as e:
            print(f"  ✗ Error: {e}")
        
        print()
        
        print("Test 2: Read Present Position (register 132)")
        print("-"*70)
        try:
            data = servo.read_address(132, 4)
            position = data[0] + (data[1] << 8) + (data[2] << 16) + (data[3] << 24)
            if position >= 2147483648:
                position -= 4294967296
            print(f"  ✓ Position: {position}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
        
        print()
        
        print("Test 3: Read Present Current (register 126)")
        print("-"*70)
        try:
            data = servo.read_address(126, 2)
            current_raw = data[0] + (data[1] << 8)
            current_ma = int(4.5 * (current_raw - 2048))
            print(f"  ✓ Current (raw): {current_raw}")
            print(f"  ✓ Current (mA): {current_ma}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
        
        print()
        
        print("Test 4: Write Goal Position (move to position 2048)")
        print("-"*70)
        try:
            # Write 2048 as 4-byte value
            pos = 2048
            data = [pos & 0xFF, (pos >> 8) & 0xFF, (pos >> 16) & 0xFF, (pos >> 24) & 0xFF]
            servo.write_address(116, data)  # Goal Position at 116
            print(f"  ✓ Wrote goal position: {pos}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
        
        print("\n" + "="*70)
        print("Test complete!")
        print("="*70)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
