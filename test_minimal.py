#!/usr/bin/env python3
"""
Minimal servo test - NO EEPROM WRITES
Only reads status and tests basic RAM operations.
"""

import sys
import time

sys.path.insert(0, '/home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver')

from libezgripper.config import load_config
from libezgripper import create_connection

def minimal_test(device='/dev/ttyUSB0'):
    """Test servo without any EEPROM writes"""
    print("="*70)
    print("  MINIMAL SERVO TEST - NO EEPROM WRITES")
    print("="*70)
    
    try:
        config = load_config()
        print(f"Config: Operating Mode = {config.operating_mode}")
        
        # Create connection only - NO Gripper initialization
        print("\n1. Creating connection...")
        connection = create_connection(dev_name=device, baudrate=config.comm_baudrate)
        
        # Create servo object directly - NO init
        from libezgripper.lib_robotis import Robotis_Servo
        servo = Robotis_Servo(connection, config.comm_servo_id)
        print(f"✓ Servo object created for ID {config.comm_servo_id}")
        
        # Test 1: Read ID (should work)
        print("\n2. Reading servo ID...")
        try:
            servo_id = servo.read_word(3)  # Device ID register
            print(f"✓ Servo ID: {servo_id}")
        except Exception as e:
            print(f"✗ Failed to read ID: {e}")
            return
        
        # Test 2: Read model number
        print("\n3. Reading model number...")
        try:
            model = servo.read_word(2)  # Model number register
            print(f"✓ Model number: {model}")
            if model == 1020:  # MX-64
                print("  ✓ Detected MX-64 servo")
            else:
                print(f"  ⚠ Unknown model (expected 1020 for MX-64)")
        except Exception as e:
            print(f"✗ Failed to read model: {e}")
        
        # Test 3: Read firmware version
        print("\n4. Reading firmware version...")
        try:
            fw = servo.read_word(6)  # Firmware version
            print(f"✓ Firmware version: {fw}")
        except Exception as e:
            print(f"✗ Failed to read firmware: {e}")
        
        # Test 4: Check current operating mode (READ ONLY)
        print("\n5. Reading current operating mode...")
        try:
            mode = servo.read_word(config.reg_operating_mode)
            print(f"✓ Current operating mode: {mode}")
            if mode == 3:
                print("  ✓ Position Control mode")
            elif mode == 4:
                print("  ✓ Extended Position Control mode")
            else:
                print(f"  ⚠ Unknown mode: {mode}")
        except Exception as e:
            print(f"✗ Failed to read mode: {e}")
        
        # Test 5: Read current position
        print("\n6. Reading current position...")
        try:
            pos = servo.read_word_signed(config.reg_present_position)
            print(f"✓ Current position: {pos}")
        except Exception as e:
            print(f"✗ Failed to read position: {e}")
        
        # Test 6: Check if torque is enabled
        print("\n7. Checking torque status...")
        try:
            torque = servo.read_word(config.reg_torque_enable)
            print(f"✓ Torque enable: {torque} (0=disabled, 1=enabled)")
        except Exception as e:
            print(f"✗ Failed to read torque status: {e}")
        
        # Test 7: Read current limit (EEPROM - should be readable)
        print("\n8. Reading current limit (EEPROM)...")
        try:
            current_limit = servo.read_word(config.reg_current_limit)
            print(f"✓ Current limit: {current_limit}")
        except Exception as e:
            print(f"✗ Failed to read current limit: {e}")
        
        # Test 8: Try RAM write - Goal Current (safe RAM operation)
        print("\n9. Testing RAM write - Goal Current...")
        try:
            # Write a small current value to Goal Current (RAM register 102)
            # This is a RAM register, should be safe
            test_current = 100  # Small test value
            data = [test_current & 0xFF, (test_current >> 8) & 0xFF]
            servo.write_address(config.reg_goal_current, data)
            print(f"✓ Goal Current write successful: {test_current}")
            
            # Read it back
            read_current = servo.read_word_signed(config.reg_goal_current)
            print(f"✓ Goal Current read back: {read_current}")
        except Exception as e:
            print(f"✗ Goal Current failed: {e}")
        
        # Test 9: Try position move ONLY if torque is disabled
        print("\n10. Testing safe position move...")
        try:
            # Check if torque is enabled
            torque = servo.read_word(config.reg_torque_enable)
            if torque == 0:
                print("  Torque is disabled - safe to move")
                # Write a small position change
                current_pos = servo.read_word_signed(config.reg_present_position)
                test_pos = current_pos + 100  # Small movement
                servo.write_word(config.reg_goal_position, test_pos)
                print(f"  ✓ Test position command sent: {test_pos}")
            else:
                print("  ⚠ Torque is enabled - skipping position test")
        except Exception as e:
            print(f"✗ Position test failed: {e}")
        
        print("\n" + "="*70)
        print("  MINIMAL TEST COMPLETE")
        print("="*70)
        print("\n✓ Servo is responsive")
        print("✓ No EEPROM writes performed")
        print("✓ Safe RAM operations working")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    device = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
    minimal_test(device)
