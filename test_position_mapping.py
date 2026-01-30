"""
Test Position Mapping

Calibrate the gripper, then command positions from 0% to 100% in 10% increments
and record the actual servo position at each step.
"""

import time
import sys
from libezgripper import create_connection, Gripper

def test_position_mapping(device="/dev/ttyUSB0"):
    """Map commanded percentages to actual servo positions"""
    print(f"Connecting to {device}...")
    connection = create_connection(dev_name=device, baudrate=57600)
    gripper = Gripper(connection, 'test_gripper', [1])
    servo = gripper.servos[0]
    
    # Calibrate
    print("\nCalibrating...")
    gripper.calibrate()
    zero_position = gripper.zero_positions[0]
    print(f"Calibrated zero position: {zero_position}")
    
    print("\n" + "="*70)
    print("Position Mapping: Commanded % -> Actual Servo Position")
    print("="*70)
    print(f"{'Cmd %':<10} {'Target':<12} {'Actual Pos':<15} {'Delta from Zero':<15}")
    print("-" * 70)
    
    # Test each percentage from 0 to 100 in 10% increments
    for pct in range(0, 101, 10):
        # Calculate target position using gripper's scale function
        target = gripper.scale(pct, gripper.GRIP_MAX)
        
        # Command position with 100% effort
        servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control  # Disable torque mode
        servo.write_word(38,  # Protocol 2.0: Current Limit 1023)    # 100% effort
        servo.write_word(116,  # Protocol 2.0: Goal Position zero_position + target)  # Use _goto_position logic
        
        # Wait for movement
        time.sleep(1.5)
        
        # Read actual position
        actual_pos = servo.read_word_signed(36)
        delta = actual_pos - zero_position
        
        print(f"{pct}%{'':<7} {target:<12} {actual_pos:<15} {delta:<15}")
    
    # Calculate range
    print("\n" + "="*70)
    print("Range Analysis")
    print("="*70)
    
    # Go to 0% and measure
    target_0 = gripper.scale(0, gripper.GRIP_MAX)
    servo.write_word(116,  # Protocol 2.0: Goal Position zero_position + target_0)
    time.sleep(1.5)
    pos_0 = servo.read_word_signed(36)
    
    # Go to 100% and measure
    target_100 = gripper.scale(100, gripper.GRIP_MAX)
    servo.write_word(116,  # Protocol 2.0: Goal Position zero_position + target_100)
    time.sleep(1.5)
    pos_100 = servo.read_word_signed(36)
    
    actual_range = pos_100 - pos_0
    
    print(f"\nZero position (calibrated):  {zero_position}")
    print(f"Position at 0%:              {pos_0} (delta: {pos_0 - zero_position})")
    print(f"Position at 100%:            {pos_100} (delta: {pos_100 - zero_position})")
    print(f"Actual range (100% - 0%):    {actual_range} servo units")
    print(f"GRIP_MAX (scale constant):   {gripper.GRIP_MAX}")
    
    # Calculate 10% offset
    offset_actual = int(actual_range * 0.10)
    offset_gripmax = int(gripper.GRIP_MAX * 0.10)
    
    print(f"\n10% of actual range:         {offset_actual} servo units")
    print(f"10% of GRIP_MAX:             {offset_gripmax} servo units")
    
    if abs(offset_actual - offset_gripmax) > 20:
        print(f"\n⚠️  Difference: {abs(offset_actual - offset_gripmax)} units")
        print(f"Should use {offset_actual} units for 10% offset")
    else:
        print(f"\n✅ GRIP_MAX-based offset is accurate (difference: {abs(offset_actual - offset_gripmax)} units)")
    
    print(f"\nFor shifted zero approach:")
    print(f"  Shifted zero = {zero_position} - {offset_actual} = {zero_position - offset_actual}")
    print(f"  Then commanding 10% reaches: {zero_position - offset_actual} + {offset_actual} = {zero_position} (true zero)")
    print(f"  And commanding 20% reaches: {zero_position - offset_actual} + {2*offset_actual} = {zero_position + offset_actual} (10% beyond)")

if __name__ == "__main__":
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    test_position_mapping(device)
