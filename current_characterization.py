#!/usr/bin/env python3
"""
Current Characterization Test for EZGripper

Tests current patterns during:
1. Fast movements (no resistance)
2. Slow movements (no resistance) 
3. Actual resistance (gripping object)
4. Tendon slack at full open/close
"""

import time
import logging
import sys
import os

# Add lib path
sys.path.append('.')

from libezgripper import create_connection, Gripper
from libezgripper.ezgripper_base import set_torque_mode

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def read_current(servo):
    """Read current/load from servo"""
    try:
        load = servo.read_word(40)  # Present Load register (40)
        # Convert load to current-like value (0-2047, direction bit in 10th bit)
        if load > 1023:
            load = load - 1024  # Remove direction bit for magnitude
        return load
    except:
        return 0

def calibrate_gripper(gripper):
    """Calibrate gripper to find true closed position"""
    print("\n=== GRIPPER CALIBRATION ===")
    print("Running calibration to find true closed position...")
    
    try:
        # Run calibration
        gripper.calibrate()
        
        # Read the calibrated zero position
        zero_pos = gripper.zero_positions[0] if gripper.zero_positions else 0
        actual_pos = gripper.get_position()
        
        print(f"Calibration complete!")
        print(f"Zero position: {zero_pos}")
        print(f"Current position after calibration: {actual_pos:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"Calibration failed: {e}")
        return False

def test_movement_patterns(gripper):
    """Test different movement patterns and log current"""
    
    print("\n=== CURRENT CHARACTERIZATION TEST ===\n")
    
    # Start with calibration
    if not calibrate_gripper(gripper):
        print("Calibration failed, aborting test")
        return
    
    # Test 1: Fast closing from full open
    print("Test 1: Fast closing from 100% to 0%")
    positions = [100, 80, 60, 40, 20, 0]
    
    for target_pos in positions:
        print(f"\nMoving to {target_pos}%...")
        
        # Read current before movement
        start_current = read_current(gripper.servos[0])
        
        # Send command
        gripper.goto_position(target_pos, 100)
        
        # Monitor current during movement
        current_samples = []
        for i in range(10):  # Sample for 1 second
            current = read_current(gripper.servos[0])
            current_samples.append(current)
            time.sleep(0.1)
        
        # Read actual position
        actual_pos = gripper.get_position()
        
        print(f"  Start current: {start_current}")
        print(f"  Peak current: {max(current_samples)}")
        print(f"  Avg current: {sum(current_samples)/len(current_samples):.1f}")
        print(f"  Actual position: {actual_pos:.1f}%")
        print(f"  Current pattern: {current_samples}")
        
        time.sleep(1)  # Pause between movements
    
    # Test 2: Slow closing
    print("\n\nTest 2: Slow closing from 100% to 0% (step by step)")
    gripper.goto_position(100, 100)  # Ensure fully open
    time.sleep(2)
    
    for target_pos in range(100, -1, -5):
        print(f"Moving to {target_pos}%...")
        
        start_current = read_current(gripper.servos[0])
        gripper.goto_position(target_pos, 100)
        
        # Quick sample
        time.sleep(0.3)
        peak_current = read_current(gripper.servos[0])
        actual_pos = gripper.get_position()
        
        print(f"  Current: {start_current} → {peak_current}, Position: {actual_pos:.1f}%")
        
        if peak_current > 500:
            print(f"  *** HIGH CURRENT DETECTED: {peak_current} ***")
    
    # Test 3: Hold at different positions
    print("\n\nTest 3: Hold current at different positions")
    test_positions = [0, 25, 50, 75, 100]
    
    for pos in test_positions:
        print(f"\nHolding at {pos}%...")
        gripper.goto_position(pos, 100)
        time.sleep(2)  # Let it settle
        
        # Sample holding current
        hold_currents = []
        for i in range(5):
            current = read_current(gripper.servos[0])
            hold_currents.append(current)
            time.sleep(0.2)
        
        avg_hold = sum(hold_currents)/len(hold_currents)
        actual_pos = gripper.get_position()
        
        print(f"  Hold current: {avg_hold:.1f}, Actual: {actual_pos:.1f}%")
    
    # Test 4: Continuous high load detection
    print("\n\nTest 4: Continuous high load detection")
    gripper.goto_position(50, 100)
    time.sleep(1)
    
    high_load_count = 0
    for i in range(20):
        # Small movement back and forth
        target = 45 if i % 2 == 0 else 55
        print(f"\nSmall move to {target}%...")
        
        start_current = read_current(gripper.servos[0])
        gripper.goto_position(target, 100)
        
        time.sleep(0.2)
        peak_current = read_current(gripper.servos[0])
        
        print(f"  Initial current: {start_current} → {peak_current}")
        
        # If current is high, take 5 sequential readings
        if peak_current > 100:
            high_load_count += 1
            print(f"  *** HIGH LOAD DETECTED ({peak_current}) - Taking 5 sequential readings ***")
            
            sequential_currents = []
            for j in range(5):
                time.sleep(0.1)
                current = read_current(gripper.servos[0])
                sequential_currents.append(current)
                print(f"    Reading {j+1}: {current}")
            
            avg_sequential = sum(sequential_currents) / len(sequential_currents)
            min_sequential = min(sequential_currents)
            max_sequential = max(sequential_currents)
            
            print(f"  Sequential analysis: avg={avg_sequential:.1f}, min={min_sequential}, max={max_sequential}")
            
            # Check if it's truly continuous high load
            if min_sequential > 100:
                print(f"  *** CONFIRMED CONTINUOUS HIGH LOAD ***")
            else:
                print(f"  *** Intermittent high load (not continuous) ***")
        else:
            print(f"  Normal load (below threshold)")
    
    print(f"\nSummary: {high_load_count} high load events detected out of 20 movements")
    
    print("\n=== CHARACTERIZATION COMPLETE ===")

def main():
    # Connect to gripper
    try:
        print("Connecting to gripper...")
        connection = create_connection('/dev/ttyUSB0', 57600)
        gripper = Gripper(connection, 'test_gripper', [1])
        
        print(f"Connected. Initial position: {gripper.get_position():.1f}%")
        
        # Run tests (starts with calibration)
        test_movement_patterns(gripper)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
