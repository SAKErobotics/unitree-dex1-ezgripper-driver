"""
Clear Servo Error State

Clears any error flags on the servo and resets it to a safe state.
"""

import time
import sys
from libezgripper import create_connection

def clear_servo_errors(device="/dev/ttyUSB0"):
    """Clear servo error state"""
    print(f"Connecting to {device}...")
    
    try:
        connection = create_connection(dev_name=device, baudrate=57600)
        
        # Create servo object with error handling disabled temporarily
        from libezgripper.lib_robotis import Robotis_Servo
        
        # Try to create servo - may fail if in error state
        try:
            servo = Robotis_Servo(connection, 1)
            print("Servo connected successfully")
        except Exception as e:
            print(f"Initial connection failed (expected): {e}")
            print("Attempting to clear error state directly...")
            
            # Send instruction to clear error (Protocol 2.0: write 0 to register 70)
            # This is a low-level operation
            import struct
            # Protocol 2.0 packet format
            packet_base = [0xFF, 0xFF, 0xFD, 0x00, 1, 6, 0, 0x03, 70, 0, 0, 0]
            # Calculate CRC-16
            crc = 0
            for byte in packet_base:
                crc ^= byte
                for _ in range(8):
                    if crc & 1:
                        crc = (crc >> 1) ^ 0xA001
                    else:
                        crc = crc >> 1
            crc = crc & 0xFFFF
            msg = packet_base + [crc & 0xFF, (crc >> 8) & 0xFF]
            
            connection.write(bytes(msg))
            time.sleep(0.1)
            
            # Read response
            response = connection.read(6)
            print(f"Clear error response: {list(response)}")
            
            # Try to create servo again
            servo = Robotis_Servo(connection, 1)
            print("Servo connected after error clear")
        
        # Read current error state (Protocol 2.0: Hardware Error Status at 70)
        error = servo.read_address(70, 1)[0]
        print(f"Current error state: {error} (0x{error:02X})")
        
        # Disable torque mode FIRST (required before clearing error)
        print("Disabling torque mode...")
        servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control
        servo.write_address(64, [0])  # Protocol 2.0: Torque Enable = 0
        time.sleep(0.1)
        
        if error != 0:
            print("Clearing error state...")
            # Write 0 to hardware error status register (after torque disabled)
            servo.write_address(70, [0])  # Protocol 2.0: Hardware Error Status
            time.sleep(0.1)
            
            # Verify
            error = servo.read_address(70, 1)[0]
            print(f"Error state after clear: {error} (0x{error:02X})")
        
        # Set to safe current limit
        print("Setting safe current limit...")
        servo.write_word(38, 512)  # Protocol 2.0: Current Limit at 38 (50% limit)
        
        # Read position (Protocol 2.0: 4-byte position)
        pos_data = servo.read_address(132, 4)
        pos = pos_data[0] + (pos_data[1] << 8) + (pos_data[2] << 16) + (pos_data[3] << 24)
        if pos >= 2147483648:
            pos -= 4294967296
        print(f"Current position: {pos}")
        
        print("\nServo reset complete!")
        print("You can now run the characterization test.")
        
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    clear_servo_errors(device)
