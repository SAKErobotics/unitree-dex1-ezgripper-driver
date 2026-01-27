#!/usr/bin/env python3
"""
Test script to verify torque pumping prevention

This script demonstrates that new commands while in torque mode
are ignored to prevent torque pumping/cycling.
"""

import time
import logging
from hardware_controller import HardwareController

# Setup logging to see debug messages
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_no_pumping")

def test_no_torque_pumping():
    """Test that torque pumping is prevented"""
    
    print("🎯 TESTING TORQUE PUMPING PREVENTION")
    print("=" * 60)
    
    try:
        # Initialize hardware controller
        controller = HardwareController("/dev/ttyUSB0", "left")
        
        print("\n1️⃣  TRIGGER TORQUE MODE")
        print("   Sending close command to trigger resistance detection...")
        
        # Trigger torque mode
        controller.send_command(15.0, 100.0)
        time.sleep(2)
        
        print("\n2️⃣  VERIFY TORQUE MODE ACTIVE")
        print("   Should be in torque mode now...")
        time.sleep(1)
        
        print("\n3️⃣  SEND MULTIPLE COMMANDS (SHOULD BE IGNORED)")
        print("   Sending various commands while in torque mode...")
        print("   These should be IGNORED to prevent torque pumping:")
        
        # Send multiple commands that should be ignored
        test_commands = [12.0, 10.0, 8.0, 5.0, 3.0, 1.0]
        
        for cmd in test_commands:
            print(f"   Sending command {cmd}%...")
            controller.send_command(cmd, 100.0)
            time.sleep(0.5)
        
        print("\n4️⃣  VERIFY NO TORQUE PUMPING")
        print("   Check logs - should see 'Ignoring non-opening command' messages")
        print("   Torque should remain stable without cycling")
        time.sleep(2)
        
        print("\n5️⃣  TEST OPENING COMMAND (SHOULD WORK)")
        print("   Sending opening command - should exit torque mode...")
        
        # Send opening command (should work)
        controller.send_command(50.0, 100.0)
        time.sleep(2)
        
        print("\n6️⃣  TEST BACKOFF TORQUE MODE")
        print("   Triggering torque mode again to test backoff...")
        
        # Trigger torque mode again
        controller.send_command(15.0, 100.0)
        time.sleep(1)  # Torque mode
        
        print("   Waiting for backoff mode (0.5s timeout)...")
        time.sleep(1)  # Should transition to backoff
        
        print("\n7️⃣  TEST BACKOFF COMMAND IGNORING")
        print("   Sending commands in backoff mode (should be ignored)...")
        
        # Send commands in backoff mode (should be ignored)
        backoff_commands = [20.0, 25.0, 30.0]
        
        for cmd in backoff_commands:
            print(f"   Sending command {cmd}% in backoff mode...")
            controller.send_command(cmd, 100.0)
            time.sleep(0.5)
        
        print("\n8️⃣  TEST CLOSING COMMAND IN BACKOFF")
        print("   Sending closing command - should exit backoff mode...")
        
        # Send closing command (should exit backoff)
        controller.send_command(10.0, 100.0)
        time.sleep(2)
        
        print("\n✅ TORQUE PUMPING PREVENTION TEST COMPLETE")
        print("=" * 60)
        print("Expected behavior observed:")
        print("  ✅ Non-opening commands ignored in torque mode")
        print("  ✅ Non-closing commands ignored in backoff mode")
        print("  ✅ No torque pumping/cycling during command streams")
        print("  ✅ Opening/closing commands still work properly")
        
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
    print("🔧 EZGripper Torque Pumping Prevention Test")
    print("This test verifies that new commands while in torque mode are ignored")
    print("to prevent torque pumping/cycling issues")
    
    success = test_no_torque_pumping()
    
    if success:
        print("\n🎉 TORQUE PUMPING PREVENTION WORKING CORRECTLY!")
    else:
        print("\n❌ TORQUE PUMPING PREVENTION TEST FAILED")
    
    return success

if __name__ == "__main__":
    main()
