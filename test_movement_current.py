"""
Test Movement Current During Position Control

Measure current during gripper movement from 100% open to 70% closed
at 100% effort to establish baseline movement current for resistance detection.
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

def test_movement_current(device="/dev/ttyUSB0"):
    """Test current during position movement"""
    print(f"Connecting to {device}...")
    connection = create_connection(dev_name=device, baudrate=57600)
    gripper = Gripper(connection, 'test_gripper', [1])
    servo = gripper.servos[0]
    
    print("\n" + "="*70)
    print("MOVEMENT CURRENT TEST")
    print("="*70)
    print("Testing current during position control movement")
    print("From 100% open to 70% closed at 100% effort")
    print("="*70)
    
    # Calibrate
    print("\nCalibrating...")
    gripper.calibrate()
    zero_position = gripper.zero_positions[0]
    print(f"Zero position: {zero_position}")
    
    # Release gripper
    print("\nReleasing gripper to open position...")
    servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control  # Disable torque mode
    time.sleep(3.0)
    
    # Move to 100% open
    print("\nMoving to 100% open...")
    gripper.set_max_effort(100)
    open_pos = gripper.scale(100, gripper.GRIP_MAX)
    servo.write_word(116,  # Protocol 2.0: Goal Position open_pos)
    time.sleep(2.0)
    
    # Read idle current at 100% open
    print("\nReading idle current at 100% open (5 samples)...")
    idle_currents = []
    for i in range(5):
        current = read_actual_current(servo)
        idle_currents.append(current)
        time.sleep(0.1)
    avg_idle = sum(idle_currents) / len(idle_currents)
    print(f"Idle current: {idle_currents}")
    print(f"Average idle: {avg_idle:.1f} mA")
    
    # Prepare for movement test
    print("\n" + "="*70)
    print("Starting movement test: 100% -> 70% at 100% effort")
    print("Collecting current samples as fast as possible during movement")
    print("="*70)
    
    # Command movement and immediately start reading current
    start_time = time.time()
    movement_currents = []
    movement_times = []
    
    # Set effort to 100%
    gripper.set_max_effort(100)
    
    # Command position to 70%
    target_pos = gripper.scale(70, gripper.GRIP_MAX)
    servo.write_word(116,  # Protocol 2.0: Goal Position target_pos)
    
    # Read current as fast as possible during movement
    print("\nCollecting current samples...")
    sample_count = 0
    while True:
        try:
            current = read_actual_current(servo)
            elapsed = time.time() - start_time
            movement_currents.append(current)
            movement_times.append(elapsed)
            sample_count += 1
            
            # Also read position to detect when movement stops
            position = servo.read_word_signed(36)
            
            # Stop after 2 seconds or when we've collected enough samples
            if elapsed > 2.0:
                break
                
        except Exception as e:
            print(f"Error reading current: {e}")
            break
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\n✅ Collected {sample_count} samples in {duration:.3f} seconds")
    print(f"   Sample rate: {sample_count/duration:.1f} Hz")
    
    # Read final position (may fail if servo in error state)
    try:
        final_position = gripper.get_position()
        print(f"   Final position: {final_position:.1f}%")
    except Exception as e:
        print(f"   Could not read final position (servo may be in error state): {e}")
    
    # Analyze current during movement
    print("\n" + "="*70)
    print("MOVEMENT CURRENT ANALYSIS")
    print("="*70)
    
    # Calculate statistics
    min_current = min(movement_currents)
    max_current = max(movement_currents)
    avg_current = sum(movement_currents) / len(movement_currents)
    
    # Calculate absolute values for magnitude comparison
    abs_currents = [abs(c) for c in movement_currents]
    min_abs = min(abs_currents)
    max_abs = max(abs_currents)
    avg_abs = sum(abs_currents) / len(abs_currents)
    
    print(f"\nCurrent Statistics (signed):")
    print(f"  Min: {min_current} mA")
    print(f"  Max: {max_current} mA")
    print(f"  Avg: {avg_current:.1f} mA")
    
    print(f"\nCurrent Statistics (magnitude):")
    print(f"  Min: {min_abs} mA")
    print(f"  Max: {max_abs} mA")
    print(f"  Avg: {avg_abs:.1f} mA")
    
    print(f"\nIdle current (at rest): {avg_idle:.1f} mA")
    print(f"Movement current (avg magnitude): {avg_abs:.1f} mA")
    print(f"Peak movement current: {max_abs} mA")
    
    # Show time series
    print(f"\nCurrent vs Time (first 20 samples):")
    print(f"{'Time (s)':<12} {'Current (mA)':<15} {'Magnitude':<15}")
    print("-" * 42)
    for i in range(min(20, len(movement_currents))):
        print(f"{movement_times[i]:<12.3f} {movement_currents[i]:<15} {abs(movement_currents[i]):<15}")
    
    if len(movement_currents) > 20:
        print(f"... ({len(movement_currents) - 20} more samples)")
    
    # Recommendation for threshold
    print("\n" + "="*70)
    print("RESISTANCE DETECTION THRESHOLD RECOMMENDATION")
    print("="*70)
    print(f"\nMovement current range: {min_abs} - {max_abs} mA (avg: {avg_abs:.1f} mA)")
    print(f"Suggested threshold: {int(max_abs * 1.5)} mA (1.5x peak movement current)")
    print(f"\nThis ensures resistance detection only triggers when current exceeds")
    print(f"normal movement current, avoiding false positives during free movement.")
    
    # Release gripper
    print("\n\nReleasing gripper...")
    servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control
    
    print("\nTest complete!")
    
    return {
        'idle_current': avg_idle,
        'movement_currents': movement_currents,
        'movement_times': movement_times,
        'avg_movement_current': avg_abs,
        'peak_movement_current': max_abs,
        'sample_count': sample_count,
        'duration': duration,
        'sample_rate': sample_count / duration
    }

if __name__ == "__main__":
    device = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    test_movement_current(device)
