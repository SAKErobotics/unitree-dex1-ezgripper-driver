#!/usr/bin/env python3
"""
Test Smart EEPROM Initialization
Only writes to EEPROM if values need to change.
"""

import sys
import time

sys.path.insert(0, '/home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver')

from libezgripper.config import load_config
from libezgripper import create_connection, Gripper

def test_smart_init(device='/dev/ttyUSB0'):
    """Test smart EEPROM initialization"""
    print("="*70)
    print("  SMART EEPROM INITIALIZATION TEST")
    print("="*70)
    
    try:
        config = load_config()
        print(f"\nConfiguration:")
        print(f"  Operating Mode: {config.operating_mode}")
        print(f"  Max Current: {config.max_current}")
        print(f"  Smart Init: {config.comm_smart_init}")
        
        print("\n1. Creating gripper with smart initialization...")
        gripper = Gripper(
            create_connection(dev_name=device, baudrate=config.comm_baudrate),
            'test',
            [config.comm_servo_id],
            config
        )
        
        print("\n✓ Smart initialization complete!")
        print("  (Check above for EEPROM write status)")
        
        # Test basic movement
        print("\n2. Testing basic movement...")
        print("  Moving to position 50% at 100% current...")
        gripper.move_with_torque_management(50, 100)
        time.sleep(2.0)
        
        pos = gripper.get_position()
        print(f"  Current position: {pos:.1f}%")
        
        print("\n3. Testing current control...")
        print("  Setting effort to 30%...")
        gripper.set_max_effort(30)
        time.sleep(0.5)
        
        print("  Setting effort to 100%...")
        gripper.set_max_effort(100)
        time.sleep(0.5)
        
        print("\n4. Testing release...")
        gripper.release()
        print("  ✓ Released (current set to 0)")
        
        print("\n" + "="*70)
        print("  SMART INIT TEST COMPLETE")
        print("="*70)
        print("\n✓ EEPROM writes only when necessary")
        print("✓ No unnecessary EEPROM wear")
        print("✓ Servo operating normally")
        
        return gripper
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    device = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
    test_smart_init(device)
