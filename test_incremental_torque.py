"""
Incremental Torque Test

No calibration. Start with 5% torque, wait for position to stop (10 stable readings),
record current, then incrementally increase torque by 10% and record current after 0.5s.
"""

import time
import sys
from libezgripper import create_connection, Gripper

def read_actual_current(servo):
    """
    Read actual motor current from servo
    
    MX-64 Protocol 2.0: Register 126 (Current)
    Formula: I = (4.5mA) * (CURRENT - 2048)
    """
    current_raw = servo.read_word(126)  # Protocol 2.0: Present Current
    # Convert using MX-64 formula: I = 4.5mA * (CURRENT - 2048)
    current_ma = int(4.5 * (current_raw - 2048))
    return current_ma

def wait_for_position_stable(servo, num_stable=10, tolerance=5, check_interval=0.1):
    """
    Wait for position to stop changing (10 consecutive stable readings)
    
    Args:
        servo: Servo object
        num_stable: Number of consecutive stable readings required
        tolerance: Position change tolerance in servo units
        check_interval: Time between position checks in seconds
        
    Returns:
        Final stable position
    """
    stable_count = 0
    prev_position = servo.read_word_signed(36)
    
    while stable_count < num_stable:
        time.sleep(check_interval)
        current_position = servo.read_word_signed(36)
        
        if abs(current_position - prev_position) <= tolerance:
            stable_count += 1
        else:
            stable_count = 0  # Reset if position changed
        
        prev_position = current_position
    
    return prev_position

def test_incremental_torque(device="/dev/ttyUSB0"):
    """Test torque mode with incremental force increases"""
    print(f"Connecting to {device}...")
    connection = create_connection(dev_name=device, baudrate=57600)
    gripper = Gripper(connection, 'test_gripper', [1])
    servo = gripper.servos[0]
    
    print("\n" + "="*70)
    print("INCREMENTAL TORQUE TEST")
    print("="*70)
    print("Starting at 5% torque, incrementing by 10% each step")
    print("No calibration - gripper will close from current position")
    print("="*70)
    
    # Start with 5% torque
    initial_torque = 5
    torque_increment = 10
    max_torque = 65  # Reduced from 75 to avoid overload
    
    print(f"\nStep 1: Closing with {initial_torque}% torque...")
    
    # Set initial torque limit
    torque_limit = gripper.scale(initial_torque, gripper.TORQUE_MAX)
    servo.write_word(38,  # Protocol 2.0: Current Limit torque_limit)
    
    # Enable torque mode
    servo.write_address(11, [0])  # Protocol 2.0: Operating Mode = Current Control
    
    # Set goal torque (1024 + value for CW/closing direction)
    goal_torque = 1024 + torque_limit
    servo.write_word(102,  # Protocol 2.0: Goal Current goal_torque)
    
    print(f"Waiting for position to stabilize (10 consecutive stable readings)...")
    final_position = wait_for_position_stable(servo, num_stable=10, tolerance=5, check_interval=0.1)
    print(f"Position stabilized at: {final_position}")
    
    # Read initial current
    print(f"Reading current (5 samples)...")
    currents = []
    for i in range(5):
        current = read_actual_current(servo)
        currents.append(current)
        time.sleep(0.05)
    avg_current = sum(currents) / len(currents)
    
    # Read load
    load = servo.read_word(126)  # Protocol 2.0: Present Current (was Load)
    if load >= 1024:
        signed_load = load - 1024
    else:
        signed_load = -(1024 - load)
    
    print(f"\nInitial Results:")
    print(f"  Torque: {initial_torque}%")
    print(f"  Position: {final_position}")
    print(f"  Load: {load} (signed: {signed_load})")
    print(f"  Current: {currents}")
    print(f"  Average current: {avg_current:.1f} mA")
    
    # Store results
    results = [{
        'torque': initial_torque,
        'position': final_position,
        'load': load,
        'signed_load': signed_load,
        'currents': currents,
        'avg_current': avg_current
    }]
    
    # Incrementally increase torque
    print("\n" + "="*70)
    print("Incrementing torque and recording current")
    print("="*70)
    print(f"{'Torque %':<12} {'Position':<12} {'Load':<10} {'Avg Current (mA)':<20}")
    print("-" * 70)
    print(f"{initial_torque}%{'':<9} {final_position:<12} {load:<10} {avg_current:<20.1f}")
    
    current_torque = initial_torque
    
    while current_torque < max_torque:
        current_torque += torque_increment
        
        # Set new torque limit
        torque_limit = gripper.scale(current_torque, gripper.TORQUE_MAX)
        servo.write_word(38,  # Protocol 2.0: Current Limit torque_limit)
        
        # Update goal torque
        goal_torque = 1024 + torque_limit
        servo.write_word(102,  # Protocol 2.0: Goal Current goal_torque)
        
        # Wait 0.5s for force to adjust
        time.sleep(0.5)
        
        # Read current
        currents = []
        for i in range(5):
            current = read_actual_current(servo)
            currents.append(current)
            time.sleep(0.05)
        avg_current = sum(currents) / len(currents)
        
        # Read position and load
        position = servo.read_word_signed(36)
        load = servo.read_word(126)  # Protocol 2.0: Present Current (was Load)
        if load >= 1024:
            signed_load = load - 1024
        else:
            signed_load = -(1024 - load)
        
        print(f"{current_torque}%{'':<9} {position:<12} {load:<10} {avg_current:<20.1f}")
        
        results.append({
            'torque': current_torque,
            'position': position,
            'load': load,
            'signed_load': signed_load,
            'currents': currents,
            'avg_current': avg_current
        })
    
    # Analysis
    print("\n" + "="*70)
    print("ANALYSIS")
    print("="*70)
    
    print("\nCurrent vs Torque:")
    for r in results:
        print(f"  {r['torque']:3}% torque → {r['avg_current']:7.1f} mA  (samples: {r['currents']})")
    
    # Check if current increases with torque
    print("\nExpected: Current should INCREASE as torque increases")
    increasing = all(results[i]['avg_current'] <= results[i+1]['avg_current'] for i in range(len(results)-1))
    if increasing:
        print("✅ Current increases with torque (as expected)")
    else:
        print("⚠️  Current does NOT consistently increase with torque")
    
    # Disable torque mode
    print("\nDisabling torque mode...")
    servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control
    
    print("\nTest complete!")

if __name__ == "__main__":
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    test_incremental_torque(device)
