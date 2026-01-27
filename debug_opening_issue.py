#!/usr/bin/env python3
"""
Debug Torque Mode Opening Issue

Debug script to identify why the gripper isn't opening properly
after getting stuck in torque mode.
"""

import time
import logging
from hardware_controller import EZGripperHardwareController

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("debug_opening")

def debug_opening_issue():
    """Debug the opening issue in torque mode"""
    
    print("🔧 TORQUE MODE OPENING DEBUG")
    print("=" * 50)
    
    try:
        # Initialize hardware controller
        controller = EZGripperHardwareController("/dev/ttyUSB0", "left")
        
        print("1. Current state analysis...")
        print(f"   Control mode: {controller.control_mode}")
        print(f"   Current position: {controller.gripper.get_position():.1f}%")
        print(f"   Expected position: {controller.expected_position_pct:.1f}%")
        print(f"   Torque mode entry: {controller.torque_mode_entry_position}")
        print(f"   Resistance detected: {controller.resistance_detected}")
        
        print("\n2. Manual mode reset...")
        print("   Forcing back to position mode...")
        controller.control_mode = 'position'
        controller.resistance_detected = False
        controller.torque_mode_start_time = None
        controller.backoff_entry_position = None
        controller.backoff_mode_start_time = None
        
        print(f"   New control mode: {controller.control_mode}")
        
        print("\n3. Testing opening command...")
        print("   Sending 100% open command...")
        controller.execute_command(100.0, 100.0)
        time.sleep(3)
        
        print(f"   Position after open: {controller.gripper.get_position():.1f}%")
        
        # Test if we can close and reopen properly
        print("\n4. Testing close/reopen cycle...")
        print("   Closing to 50%...")
        controller.execute_command(50.0, 100.0)
        time.sleep(2)
        print(f"   Position at 50%: {controller.gripper.get_position():.1f}%")
        
        print("   Opening to 100%...")
        controller.execute_command(100.0, 100.0)
        time.sleep(2)
        print(f"   Position after reopen: {controller.gripper.get_position():.1f}%")
        
        print("\n5. Testing torque mode entry and exit...")
        print("   Closing to trigger torque mode...")
        controller.execute_command(0.0, 100.0)
        time.sleep(3)
        
        print(f"   Mode after close: {controller.control_mode}")
        print(f"   Position at torque: {controller.gripper.get_position():.1f}%")
        
        if controller.control_mode in ['torque', 'backoff_torque']:
            print("   Testing opening from torque mode...")
            controller.execute_command(100.0, 100.0)
            time.sleep(3)
            print(f"   Position after torque open: {controller.gripper.get_position():.1f}%")
            print(f"   Mode after torque open: {controller.control_mode}")
        
        print("\n✅ DEBUG COMPLETE")
        
        return True
        
    except Exception as e:
        logger.error(f"Debug failed: {e}")
        return False
    
    finally:
        try:
            if 'controller' in locals():
                controller.shutdown()
        except:
            pass

def main():
    """Main debug function"""
    print("🔧 EZGripper Torque Mode Opening Debug")
    print("This script debugs why the gripper gets stuck in torque mode")
    
    success = debug_opening_issue()
    
    if success:
        print("\n🎉 DEBUG COMPLETED!")
        print("Review the output to identify the opening issue")
    else:
        print("\n❌ DEBUG FAILED")
    
    return success

if __name__ == "__main__":
    main()
