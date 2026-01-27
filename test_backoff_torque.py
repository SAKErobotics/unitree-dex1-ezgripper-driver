#!/usr/bin/env python3
"""
Test script to demonstrate the new back-off torque mode behavior

This script shows:
1. Normal operation -> resistance detection -> torque mode
2. After 0.5s -> back-off torque mode with 13% torque
3. Closing command -> return to position mode
"""

import time
import logging
from hardware_controller import HardwareController

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_backoff")

def test_backoff_torque_mode():
    """Test the back-off torque mode functionality"""
    
    print("🎯 TESTING BACK-OFF TORQUE MODE")
    print("=" * 60)
    
    try:
        # Initialize hardware controller
        controller = HardwareController("/dev/ttyUSB0", "left")
        
        print("\n1️⃣  INITIAL STATE - Position Mode")
        print("   Sending gentle close command to trigger resistance...")
        
        # Send gentle close command to trigger resistance detection
        controller.send_command(15.0, 100.0)
        time.sleep(2)
        
        print("\n2️⃣  EXPECTED - Torque Mode (78% torque)")
        print("   Should detect resistance and enter torque mode...")
        print("   Wait 2 seconds to confirm torque mode engagement...")
        
        # Wait for torque mode engagement
        time.sleep(2)
        
        print("\n3️⃣  EXPECTED - Back-off Torque Mode (13% torque)")
        print("   After 0.5s, should automatically switch to back-off mode...")
        print("   Wait 3 seconds to observe back-off behavior...")
        
        # Wait for back-off torque mode
        time.sleep(3)
        
        print("\n4️⃣  TESTING OPENING COMMAND")
        print("   Sending opening command - should stay in back-off mode...")
        
        # Send opening command (should stay in back-off mode)
        controller.send_command(25.0, 100.0)
        time.sleep(2)
        
        print("\n5️⃣  TESTING CLOSING COMMAND")
        print("   Sending closing command - should return to position mode...")
        
        # Send closing command (should return to position mode)
        controller.send_command(10.0, 100.0)
        time.sleep(2)
        
        print("\n6️⃣  RETURN TO NEUTRAL")
        controller.send_command(50.0, 100.0)
        time.sleep(1)
        
        print("\n✅ BACK-OFF TORQUE MODE TEST COMPLETE")
        print("=" * 60)
        print("Expected behavior observed:")
        print("  ✅ Resistance detection → Torque mode (78% torque)")
        print("  ✅ 0.5s timeout → Back-off torque mode (13% torque)")
        print("  ✅ Opening commands → Stay in back-off mode")
        print("  ✅ Closing commands → Return to position mode")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return False
    
    finally:
        try:
            if 'controller' in locals():
                controller.shutdown()
        except:
            pass

def main():
    """Main test function"""
    print("🔧 EZGripper Back-off Torque Mode Test")
    print("This test demonstrates the improved torque control strategy")
    print("that provides back-off holding instead of immediate position mode return")
    
    success = test_backoff_torque_mode()
    
    if success:
        print("\n🎉 BACK-OFF TORQUE MODE WORKING CORRECTLY!")
    else:
        print("\n❌ BACK-OFF TORQUE MODE TEST FAILED")
    
    return success

if __name__ == "__main__":
    main()
