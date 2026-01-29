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
            
            # Send instruction to clear error (write 0 to register 18)
            # This is a low-level operation
            import struct
            msg = [0xFF, 0xFF, 1, 4, 0x03, 18, 0, 0]  # Write 0 to error register
            checksum = (~sum(msg[2:]))&0xFF
            msg.append(checksum)
            
            connection.write(bytes(msg))
            time.sleep(0.1)
            
            # Read response
            response = connection.read(6)
            print(f"Clear error response: {list(response)}")
            
            # Try to create servo again
            servo = Robotis_Servo(connection, 1)
            print("Servo connected after error clear")
        
        # Read current error state
        error = servo.read_address(18, 1)[0]
        print(f"Current error state: {error} (0x{error:02X})")
        
        # Disable torque mode FIRST (required before clearing error)
        print("Disabling torque mode...")
        servo.write_address(70, [0])  # Disable torque control mode
        servo.write_address(24, [0])  # Disable torque enable
        time.sleep(0.1)
        
        if error != 0:
            print("Clearing error state...")
            # Write 0 to error register (after torque disabled)
            servo.write_address(18, [0])
            time.sleep(0.1)
            
            # Verify
            error = servo.read_address(18, 1)[0]
            print(f"Error state after clear: {error} (0x{error:02X})")
        
        # Set to safe position mode
        print("Setting safe torque limit...")
        servo.write_word(34, 512)  # 50% torque limit
        
        # Read position
        pos = servo.read_word_signed(36)
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
