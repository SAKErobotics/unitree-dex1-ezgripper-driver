"""
Simple Position Test

Test steady-state current at specific positions without movement distortion.

Methodology:
1. Calibrate
2. Release (springs open gripper)
3. Set 10% offset in zero position
4. Move to 20% open with 100% effort, wait 2s, record current, release
5. Move to 25% open with 100% effort, wait 2s, record current, release
"""

import time
import sys
from libezgripper import create_connection, Gripper

def read_actual_current(servo):
    """Read actual motor current from servo"""
    current_raw = servo.read_word(126)  # Protocol 2.0: Present Current
    
    # Convert to signed value
    if current_raw > 32767:
        current_ma = current_raw - 65536
    else:
        current_ma = current_raw
    
    return current_ma

def read_stable_current(servo, num_readings=5, delay_between=0.1):
    """Read multiple current samples and return all values plus average"""
    readings = []
    for i in range(num_readings):
        current = read_actual_current(servo)
        readings.append(current)
        if i < num_readings - 1:
            time.sleep(delay_between)
    
    avg_current = sum(readings) / len(readings)
    return readings, avg_current

def test_simple_positions(device="/dev/ttyUSB0"):
    """Test steady-state current at 20% and 25% positions"""
    print(f"Connecting to {device}...")
    connection = create_connection(dev_name=device, baudrate=57600)
    gripper = Gripper(connection, 'test_gripper', [1])
    servo = gripper.servos[0]
    
    # Step 1: Calibrate
    print("\nStep 1: Calibrating...")
    gripper.calibrate()
    actual_zero = gripper.zero_positions[0]
    print(f"  Actual zero position: {actual_zero}")
    
    # Step 2: Release (springs open gripper)
    print("\nStep 2: Releasing gripper (disabling torque mode)...")
    servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control  # Disable torque mode
    time.sleep(2.0)
    pos_after_release = servo.read_word_signed(36)
    print(f"  Position after release: {pos_after_release}")
    
    # Step 3: Set 10% offset in zero position (subtract to make 0% = 10% before true zero)
    shift_amount = int(gripper.GRIP_MAX * 0.10)
    shifted_zero = actual_zero - shift_amount
    gripper.zero_positions[0] = shifted_zero
    print(f"\nStep 3: Setting -10% offset in zero position")
    print(f"  Shifted zero: {shifted_zero} (was {actual_zero}, shift: -{shift_amount})")
    print(f"  Now 0% = 10% before true zero, 10% = at true zero, 20% = 10% beyond (pressing)")
    
    # Test positions
    test_positions = [20, 25]
    
    for pos_pct in test_positions:
        print(f"\n{'='*70}")
        print(f"Testing at {pos_pct}% open position")
        print(f"{'='*70}")
        
        # Move to position with 100% effort
        target_position = gripper.scale(pos_pct, gripper.GRIP_MAX)
        print(f"Moving to {pos_pct}% open with 100% effort...")
        servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control  # Disable torque mode
        servo.write_word(38,  # Protocol 2.0: Current Limit 1023)    # 100% effort
        servo.write_word(116,  # Protocol 2.0: Goal Position target_position)
        
        # Wait 2 seconds for stabilization
        print(f"Waiting 2 seconds for stabilization...")
        time.sleep(2.0)
        
        # Record current
        print(f"Recording current (5 readings)...")
        current_readings, avg_current = read_stable_current(servo, num_readings=5, delay_between=0.1)
        
        # Read position and load
        actual_position = servo.read_word_signed(36)
        load = servo.read_word(126)  # Protocol 2.0: Present Current (was Load)
        
        # Convert load to signed value
        if load >= 1024:
            signed_load = load - 1024
        else:
            signed_load = -(1024 - load)
        
        print(f"\nResults for {pos_pct}% position:")
        print(f"  Target position: {target_position}")
        print(f"  Actual position: {actual_position}")
        print(f"  Load: {load} (signed: {signed_load})")
        print(f"  Current readings (mA): {current_readings}")
        print(f"  Average current: {avg_current:.1f} mA")
        
        # Release
        print(f"\nReleasing gripper (disabling torque mode)...")
        servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control
        time.sleep(2.0)
    
    print(f"\n{'='*70}")
    print("Test complete!")
    print(f"{'='*70}")

if __name__ == "__main__":
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    test_simple_positions(device)
