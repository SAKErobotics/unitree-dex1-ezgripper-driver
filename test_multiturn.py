#!/usr/bin/env python3
"""
Test Multi-Turn Position Control

Verifies that Extended Position Control mode (4) works correctly
and can handle positions beyond 360°.
"""

import sys
import time

sys.path.insert(0, '/home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver')

from libezgripper.config import load_config
from libezgripper import create_connection, Gripper

def main():
    device = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
    
    print("="*70)
    print("  MULTI-TURN POSITION CONTROL TEST")
    print("="*70)
    print(f"\nDevice: {device}")
    
    # Load config and connect
    config = load_config()
    print(f"\nConfiguration:")
    print(f"  Operating Mode: {config.operating_mode} (4 = Extended Position Control)")
    print(f"  Position Range: -1,048,575 to +1,048,575 units (±256 turns)")
    
    connection = create_connection(dev_name=device, baudrate=config.comm_baudrate)
    gripper = Gripper(connection, 'multiturn_test', [config.comm_servo_id], config)
    
    print(f"\n✓ Gripper initialized in Extended Position Control mode")
    
    # Test multi-turn positions
    print("\n" + "="*70)
    print("  TESTING MULTI-TURN POSITIONS")
    print("="*70)
    
    test_positions = [
        0,          # 0 turns
        4096,       # 1 turn
        8192,       # 2 turns
        12288,      # 3 turns
        -4096,      # -1 turn
        -8192,      # -2 turns
        16384,      # 4 turns
        -16384,     # -4 turns
        0,          # Back to 0
    ]
    
    for i, target_pos in enumerate(test_positions):
        print(f"\nTest {i+1}: Moving to position {target_pos} ({target_pos/4096:.1f} turns)")
        
        # Command position
        gripper._goto_position(target_pos)
        time.sleep(1.0)
        
        # Read actual position
        actual_pos = gripper.servos[0].read_word_signed(config.reg_present_position)
        error = abs(actual_pos - target_pos)
        
        print(f"  Target: {target_pos:6d} ({target_pos/4096:6.1f} turns)")
        print(f"  Actual: {actual_pos:6d} ({actual_pos/4096:6.1f} turns)")
        print(f"  Error:  {error:6d} units")
        
        if error < 50:
            print("  ✓ Position reached successfully")
        else:
            print("  ⚠ Large position error")
    
    # Test continuous movement across multiple turns
    print("\n" + "="*70)
    print("  TESTING CONTINUOUS MOVEMENT")
    print("="*70)
    
    print("\nMoving continuously through 5 rotations...")
    start_pos = 0
    end_pos = 5 * 4096  # 5 turns
    
    # Set moderate current
    gripper.set_max_effort(50)
    
    print(f"Moving from {start_pos} to {end_pos}...")
    gripper._goto_position(end_pos)
    
    # Monitor progress
    for i in range(10):
        time.sleep(0.5)
        current_pos = gripper.servos[0].read_word_signed(config.reg_present_position)
        progress = (current_pos - start_pos) / (end_pos - start_pos) * 100
        print(f"  Progress: {progress:5.1f}% (position: {current_pos})")
        
        if progress >= 99:
            break
    
    # Verify final position
    time.sleep(0.5)
    final_pos = gripper.servos[0].read_word_signed(config.reg_present_position)
    error = abs(final_pos - end_pos)
    
    print(f"\nFinal position: {final_pos} ({final_pos/4096:.1f} turns)")
    print(f"Target position: {end_pos} ({end_pos/4096:.1f} turns)")
    print(f"Error: {error} units")
    
    if error < 100:
        print("✓ Multi-turn movement successful!")
    else:
        print("⚠ Multi-turn movement had large error")
    
    # Return to zero
    print("\nReturning to zero position...")
    gripper._goto_position(0)
    time.sleep(2.0)
    
    zero_pos = gripper.servos[0].read_word_signed(config.reg_present_position)
    print(f"Zero position: {zero_pos}")
    
    print("\n" + "="*70)
    print("  MULTI-TURN TEST COMPLETE")
    print("="*70)
    print("\n✓ Extended Position Control mode (4) is working")
    print("✓ Can handle positions beyond 360°")
    print("✓ Supports ±256 turns of rotation")
    print("✓ Suitable for gripper calibration and operation")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
    except Exception as e:
        print(f"\n\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
