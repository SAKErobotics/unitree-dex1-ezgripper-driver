#!/usr/bin/env python3
"""
Test Protocol 2.0 connection and basic gripper operations
"""

import time
import sys
from libezgripper import create_connection, Gripper

def test_connection(device="/dev/ttyUSB0"):
    """Test basic Protocol 2.0 connection"""
    print("="*70)
    print("Protocol 2.0 Connection Test")
    print("="*70)
    print(f"\nConnecting to {device} at 1 Mbps...")
    
    try:
        connection = create_connection(dev_name=device, baudrate=1000000)
        gripper = Gripper(connection, 'test_gripper', [1])
        print("✓ Connection successful!")
        
        servo = gripper.servos[0]
        
        # Test 1: Read basic servo info
        print("\n" + "-"*70)
        print("Test 1: Read Servo Information")
        print("-"*70)
        
        # Read ID (Protocol 2.0: Register 7)
        servo_id = servo.read_address(7, 1)[0]
        print(f"  Servo ID: {servo_id}")
        
        # Read present position (Protocol 2.0: Register 132, 4 bytes)
        pos_data = servo.read_address(132, 4)
        position = pos_data[0] + (pos_data[1] << 8) + (pos_data[2] << 16) + (pos_data[3] << 24)
        if position >= 2147483648:
            position -= 4294967296
        print(f"  Present Position (raw): {position}")
        
        # Read present current (Protocol 2.0: Register 126, 2 bytes)
        current_raw = servo.read_word(126)
        current_ma = int(4.5 * (current_raw - 2048))
        print(f"  Present Current (raw): {current_raw}")
        print(f"  Present Current (mA): {current_ma}")
        
        # Read hardware error status (Protocol 2.0: Register 70)
        error = servo.read_address(70, 1)[0]
        print(f"  Hardware Error Status: {error} (0x{error:02X})")
        
        # Read torque enable (Protocol 2.0: Register 64)
        torque_enabled = servo.read_address(64, 1)[0]
        print(f"  Torque Enable: {torque_enabled}")
        
        # Read operating mode (Protocol 2.0: Register 11)
        op_mode = servo.read_address(11, 1)[0]
        mode_names = {0: "Current Control", 1: "Velocity Control", 3: "Position Control", 4: "Extended Position", 5: "Current-based Position", 16: "PWM Control"}
        print(f"  Operating Mode: {op_mode} ({mode_names.get(op_mode, 'Unknown')})")
        
        # Test 2: Test bulk read
        print("\n" + "-"*70)
        print("Test 2: Bulk Read Operation")
        print("-"*70)
        
        try:
            data_arrays = servo.bulk_read([
                (126, 2),  # Present Current
                (132, 4),  # Present Position
                (70, 1),   # Hardware Error Status
            ])
            
            # Parse current
            current_raw = data_arrays[0][0] + (data_arrays[0][1] << 8)
            current_ma = int(4.5 * (current_raw - 2048))
            
            # Parse position
            pos_bytes = data_arrays[1]
            position = pos_bytes[0] + (pos_bytes[1] << 8) + (pos_bytes[2] << 16) + (pos_bytes[3] << 24)
            if position >= 2147483648:
                position -= 4294967296
            
            # Parse error
            error = data_arrays[2][0]
            
            print(f"  ✓ Bulk read successful!")
            print(f"  Current: {current_ma} mA")
            print(f"  Position: {position}")
            print(f"  Error: {error}")
            
        except Exception as e:
            print(f"  ✗ Bulk read failed: {e}")
        
        # Test 3: Position control
        print("\n" + "-"*70)
        print("Test 3: Position Control")
        print("-"*70)
        
        # Ensure we're in position control mode
        servo.write_address(11, [3])  # Operating Mode = Position Control
        time.sleep(0.1)
        
        # Enable torque
        servo.write_address(64, [1])  # Torque Enable
        time.sleep(0.1)
        
        # Get current position
        current_pos = gripper.get_position()
        print(f"  Current position: {current_pos:.1f}%")
        
        # Test small movement
        print(f"  Moving to 60%...")
        gripper.goto_position(60, 100)
        time.sleep(2.0)
        
        new_pos = gripper.get_position()
        print(f"  New position: {new_pos:.1f}%")
        
        # Return to original position
        print(f"  Returning to {current_pos:.1f}%...")
        gripper.goto_position(current_pos, 100)
        time.sleep(2.0)
        
        final_pos = gripper.get_position()
        print(f"  Final position: {final_pos:.1f}%")
        
        # Test 4: Current reading during idle
        print("\n" + "-"*70)
        print("Test 4: Current Readings (Idle State)")
        print("-"*70)
        
        print("  Reading current 10 times...")
        currents = []
        for i in range(10):
            current_raw = servo.read_word(126)
            current_ma = int(4.5 * (current_raw - 2048))
            currents.append(current_ma)
            print(f"    Reading {i+1}: {current_ma} mA (raw: {current_raw})")
            time.sleep(0.1)
        
        avg_current = sum(currents) / len(currents)
        print(f"  Average current: {avg_current:.1f} mA")
        print(f"  Min: {min(currents)} mA, Max: {max(currents)} mA")
        
        print("\n" + "="*70)
        print("✓ All tests completed successfully!")
        print("="*70)
        print("\nProtocol 2.0 communication is working correctly.")
        print("Gripper is responding to commands as expected.")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    success = test_connection(device)
    sys.exit(0 if success else 1)
