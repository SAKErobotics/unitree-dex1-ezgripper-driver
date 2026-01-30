"""
Verify Current vs Effort Relationship

Test if higher effort actually produces higher current when pressing.
Command the same position (15% = pressing against itself) with different effort levels.
"""

import time
import sys
from libezgripper import create_connection, Gripper

def read_actual_current(servo):
    """Read actual motor current from servo"""
    current_raw = servo.read_word(126)  # Protocol 2.0: Present Current
    if current_raw > 32767:
        current_ma = current_raw - 65536
    else:
        current_ma = current_raw
    return current_ma

def test_current_vs_effort(device="/dev/ttyUSB0"):
    """Test current at same position with different efforts"""
    print(f"Connecting to {device}...")
    connection = create_connection(dev_name=device, baudrate=57600)
    gripper = Gripper(connection, 'test_gripper', [1])
    servo = gripper.servos[0]
    
    # Calibrate
    print("\nCalibrating...")
    gripper.calibrate()
    zero_position = gripper.zero_positions[0]
    print(f"Zero position: {zero_position}")
    
    # Shift zero by -10%
    shift_amount = int(gripper.GRIP_MAX * 0.10)
    shifted_zero = zero_position - shift_amount
    gripper.zero_positions[0] = shifted_zero
    print(f"Shifted zero: {shifted_zero} (shift: -{shift_amount})")
    print(f"This makes 10% = true zero, 15% = pressing")
    
    # Release
    print("\nReleasing gripper...")
    servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control
    time.sleep(2.0)
    
    # Test position: 15% (should be pressing against itself)
    test_position = gripper.scale(15, gripper.GRIP_MAX)
    print(f"\nTest position: 15% = {test_position} servo units")
    print(f"This should press fingers together (beyond true zero)")
    
    print("\n" + "="*70)
    print("Testing different effort levels at same position (15%)")
    print("="*70)
    print(f"{'Effort %':<12} {'Position':<12} {'Current (mA)':<15} {'Load':<10}")
    print("-" * 70)
    
    effort_levels = [20, 40, 60, 80, 100]
    
    for effort in effort_levels:
        # Release first
        servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control
        time.sleep(2.0)
        
        # Set effort and command position
        torque_limit = gripper.scale(effort, gripper.TORQUE_MAX)
        servo.write_word(38,  # Protocol 2.0: Current Limit torque_limit)
        servo.write_word(116,  # Protocol 2.0: Goal Position test_position)
        
        # Wait for position to stabilize
        time.sleep(1.5)
        
        # Read position
        actual_pos = servo.read_word_signed(36)
        
        # Wait a bit more for current to stabilize
        time.sleep(0.5)
        
        # Read current (5 samples)
        currents = []
        for i in range(5):
            current = read_actual_current(servo)
            currents.append(current)
            time.sleep(0.05)
        avg_current = sum(currents) / len(currents)
        
        # Read load
        load = servo.read_word(126)  # Protocol 2.0: Present Current (was Load)
        
        print(f"{effort}%{'':<9} {actual_pos:<12} {avg_current:<15.1f} {load:<10}")
        print(f"{'':12} Samples: {currents}")
    
    print("\n" + "="*70)
    print("Analysis:")
    print("If higher effort produces LOWER current, something is wrong!")
    print("Expected: Higher effort → Higher current (more force)")
    print("="*70)

if __name__ == "__main__":
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    test_current_vs_effort(device)
