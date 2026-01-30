"""
Measure Actual Gripper Range

Calibrate the gripper and then move through full 0-100% range multiple times
to measure the actual servo positions at each percentage.
"""

import time
import sys
from libezgripper import create_connection, Gripper

def measure_gripper_range(device="/dev/ttyUSB0"):
    """Measure actual servo range by moving through 0-100%"""
    print(f"Connecting to {device}...")
    connection = create_connection(dev_name=device, baudrate=57600)
    gripper = Gripper(connection, 'test_gripper', [1])
    servo = gripper.servos[0]
    
    # Calibrate
    print("\nCalibrating...")
    gripper.calibrate()
    zero_position = gripper.zero_positions[0]
    print(f"Zero position (calibrated closed): {zero_position}")
    
    # Test positions
    test_percentages = [0, 25, 50, 75, 100]
    
    print("\n" + "="*70)
    print("Measuring actual servo positions at different percentages")
    print("="*70)
    
    # Run through the range twice to verify consistency
    for cycle in range(2):
        print(f"\nCycle {cycle + 1}:")
        print(f"{'Percentage':<12} {'Target Pos':<12} {'Actual Pos':<12} {'Difference':<12}")
        print("-" * 50)
        
        for pct in test_percentages:
            # Calculate target position
            target_position = gripper.scale(pct, gripper.GRIP_MAX)
            
            # Move to position with 100% effort
            servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control  # Disable torque mode
            servo.write_word(38,  # Protocol 2.0: Current Limit 1023)    # 100% effort
            servo.write_word(116,  # Protocol 2.0: Goal Position target_position)
            
            # Wait for movement
            time.sleep(2.0)
            
            # Read actual position
            actual_position = servo.read_word_signed(36)
            difference = actual_position - zero_position
            
            print(f"{pct}%{'':<9} {target_position:<12} {actual_position:<12} {difference:<12}")
    
    # Calculate range
    print("\n" + "="*70)
    print("Range Calculation")
    print("="*70)
    
    # Move to 0% and measure
    servo.write_word(38,  # Protocol 2.0: Current Limit 1023)
    servo.write_word(116,  # Protocol 2.0: Goal Position gripper.scale(0, gripper.GRIP_MAX))
    time.sleep(2.0)
    pos_0 = servo.read_word_signed(36)
    
    # Move to 100% and measure
    servo.write_word(116,  # Protocol 2.0: Goal Position gripper.scale(100, gripper.GRIP_MAX))
    time.sleep(2.0)
    pos_100 = servo.read_word_signed(36)
    
    actual_range = pos_100 - pos_0
    
    print(f"\nPosition at 0%:   {pos_0}")
    print(f"Position at 100%: {pos_100}")
    print(f"Actual range:     {actual_range} servo units")
    print(f"GRIP_MAX:         {gripper.GRIP_MAX} (internal scale)")
    
    # Calculate 10% offset
    offset_10pct = int(actual_range * 0.10)
    offset_gripmax = int(gripper.GRIP_MAX * 0.10)
    
    print(f"\n10% of actual range:  {offset_10pct} servo units")
    print(f"10% of GRIP_MAX:      {offset_gripmax} servo units")
    
    if abs(offset_10pct - offset_gripmax) > 10:
        print(f"\n⚠️  Significant difference! Should use {offset_10pct} units for 10% offset")
    else:
        print(f"\n✅ GRIP_MAX-based offset ({offset_gripmax}) is close to actual range offset ({offset_10pct})")
    
    print(f"\nFor shifted zero approach:")
    print(f"  Shifted zero = {pos_0} - {offset_10pct} = {pos_0 - offset_10pct}")
    print(f"  This makes commanding 10% reach position {pos_0} (true zero)")
    print(f"  And commanding 20% reach position {pos_0 + offset_10pct} (10% beyond true zero)")

if __name__ == "__main__":
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    measure_gripper_range(device)
