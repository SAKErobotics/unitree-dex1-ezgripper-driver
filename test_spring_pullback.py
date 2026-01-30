"""
Test Spring Pullback

Close gripper to 20% open position and release torque to see if springs pull back.
"""

import time
import sys
from libezgripper import create_connection, Gripper

def test_spring_pullback(device="/dev/ttyUSB0"):
    """Test if springs pull back when torque is released at 20% position"""
    print(f"Connecting to {device}...")
    connection = create_connection(dev_name=device, baudrate=57600)
    gripper = Gripper(connection, 'test_gripper', [1])
    servo = gripper.servos[0]
    
    print("\nCalibrating...")
    gripper.calibrate()
    actual_zero = gripper.zero_positions[0]
    print(f"Actual zero position: {actual_zero}")
    
    # Shift zero by 10%
    shift_amount = int(gripper.GRIP_MAX * 0.10)
    shifted_zero = actual_zero + shift_amount
    gripper.zero_positions[0] = shifted_zero
    print(f"Shifted zero position: {shifted_zero} (shift: {shift_amount})")
    
    # Move to 20% open position with 100% effort
    print("\nMoving to 20% open position with 100% effort...")
    position_20 = gripper.scale(20, gripper.GRIP_MAX)
    servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control  # Disable torque mode
    servo.write_word(38,  # Protocol 2.0: Current Limit 1023)    # 100% effort
    servo.write_word(116,  # Protocol 2.0: Goal Position position_20)
    time.sleep(2.0)
    
    # Read position
    pos_before = servo.read_word_signed(36)
    print(f"Position before release: {pos_before}")
    
    # Release torque (disable torque mode)
    print("\nReleasing torque (disabling torque mode)...")
    servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control  # Disable torque mode
    
    # Wait and check if position changes (spring pullback)
    print("Waiting 5 seconds to check for spring pullback...")
    for i in range(5):
        time.sleep(1.0)
        pos = servo.read_word_signed(36)
        print(f"  {i+1}s: Position = {pos} (change: {pos - pos_before})")
    
    pos_after = servo.read_word_signed(36)
    pullback = pos_after - pos_before
    
    print(f"\nResults:")
    print(f"  Position before release: {pos_before}")
    print(f"  Position after 5s: {pos_after}")
    print(f"  Spring pullback: {pullback} units")
    
    if abs(pullback) > 10:
        print(f"  ⚠️ Significant spring pullback detected!")
    else:
        print(f"  ✅ Minimal spring pullback")

if __name__ == "__main__":
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    test_spring_pullback(device)
