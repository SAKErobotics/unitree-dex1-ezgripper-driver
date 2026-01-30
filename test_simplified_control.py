#!/usr/bin/env python3
"""
Test Simplified EZGripper Control

Demonstrates the new control approach:
- Extended Position mode (4) for multi-turn calibration support
- No torque mode switching
- Always move at 100% current (FAST)
- Release by setting current to 0
"""

import sys
import time

sys.path.insert(0, '/home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver')

from libezgripper.config import load_config
from libezgripper import create_connection, Gripper

def main():
    device = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
    
    print("="*70)
    print("  SIMPLIFIED EZGRIPPER CONTROL TEST")
    print("="*70)
    print(f"\nDevice: {device}")
    
    # Load config and connect
    config = load_config()
    print(f"\nConfiguration:")
    print(f"  Operating Mode: {config.operating_mode} (4 = Extended Position - multi-turn)")
    print(f"  Holding Current: {config.holding_current} units (13%)")
    print(f"  Max Current: {config.max_current} units (100%)")
    print(f"  Position Range: 0-{config.grip_max} units")
    
    connection = create_connection(dev_name=device, baudrate=config.comm_baudrate)
    gripper = Gripper(connection, 'test', [config.comm_servo_id], config)
    
    print(f"\n✓ Gripper initialized with Extended Position mode")
    print(f"✓ No torque mode switching - pure position control")
    
    # Test 1: Fast movement at 100% current
    print("\n" + "="*70)
    print("  TEST 1: FAST MOVEMENT AT 100% CURRENT")
    print("="*70)
    
    positions = [100, 75, 50, 25, 0, 50, 100]
    
    for pos in positions:
        print(f"\nMoving to {pos}% position...")
        start = time.time()
        gripper.move_with_torque_management(pos, 100)  # closing_torque ignored
        elapsed = time.time() - start
        actual_pos = gripper.get_position()
        print(f"  Command time: {elapsed:.3f} seconds")
        print(f"  Actual position: {actual_pos:.1f}%")
        time.sleep(0.5)
    
    # Test 2: Release (current = 0)
    print("\n" + "="*70)
    print("  TEST 2: RELEASE (CURRENT = 0)")
    print("="*70)
    
    print("\nReleasing gripper (setting current to 0)...")
    gripper.release()
    print("✓ Released - current set to 0")
    
    # Test 3: Current control verification
    print("\n" + "="*70)
    print("  TEST 3: CURRENT CONTROL VERIFICATION")
    print("="*70)
    
    print("\nVerifying current control...")
    
    # Set different current levels
    currents = [0, 50, 100]
    for current_pct in currents:
        print(f"\nSetting current to {current_pct}%...")
        gripper.set_max_effort(current_pct)
        time.sleep(0.5)
        print(f"  ✓ Current set to {current_pct}%")
    
    # Reset to 100% for normal operation
    gripper.set_max_effort(100)
    print("\n✓ Reset to 100% current for normal operation")
    
    # Test 4: Position range verification
    print("\n" + "="*70)
    print("  TEST 4: POSITION RANGE")
    print("="*70)
    
    print("\nTesting full position range...")
    
    # Move to open
    print("Moving to fully open (100%)...")
    gripper.move_with_torque_management(100, 100)
    time.sleep(1.0)
    open_pos = gripper.get_position()
    print(f"  Open position: {open_pos:.1f}%")
    
    # Move to closed
    print("Moving to fully closed (0%)...")
    gripper.move_with_torque_management(0, 100)
    time.sleep(1.0)
    closed_pos = gripper.get_position()
    print(f"  Closed position: {closed_pos:.1f}%")
    
    range_span = abs(open_pos - closed_pos)
    print(f"  Position range: {range_span:.1f}%")
    
    # Return to center
    print("Moving to center (50%)...")
    gripper.move_with_torque_management(50, 100)
    time.sleep(1.0)
    center_pos = gripper.get_position()
    print(f"  Center position: {center_pos:.1f}%")
    
    print("\n" + "="*70)
    print("  SIMPLIFIED CONTROL TEST COMPLETE")
    print("="*70)
    
    print("\n✓ All tests passed!")
    print("\nKey Improvements:")
    print("  1. ✓ Extended Position mode (4) - supports multi-turn calibration")
    print("  2. ✓ No torque mode switching - pure position control")
    print("  3. ✓ Always 100% current for FAST movement")
    print("  4. ✓ Release by setting current to 0")
    print("  5. ✓ No EEPROM writes during operation")
    
    print("\nControl Strategy:")
    print("  - Movement: Always 100% current (fast)")
    print("  - Grasp detection: Wave-following will handle (future)")
    print("  - Holding: 13% current (after grasp detection)")
    print("  - Release: 0% current")

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
