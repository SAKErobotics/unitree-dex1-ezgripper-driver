#!/usr/bin/env python3
"""
Resistance Mapping Test

Map out exactly where the gripper experiences back pressure
by going from 100% open to resistance detection, 5 times.
"""

import time
import logging
from hardware_controller import EZGripperHardwareController

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("resistance_mapping")

def test_resistance_mapping():
    """Test resistance detection at different positions"""
    
    print("🎯 RESISTANCE MAPPING TEST")
    print("=" * 60)
    print("This test will map exactly where back pressure occurs")
    print("by closing from 100% until resistance is detected.")
    print()
    
    try:
        # Initialize hardware controller
        controller = EZGripperHardwareController("/dev/ttyUSB0", "left")
        
        for test_num in range(1, 6):
            print(f"\n📍 TEST {test_num}/5")
            print("-" * 40)
            
            # Start fully open
            print("1. Moving to 100% open...")
            controller.execute_command(100.0, 100.0)
            time.sleep(2)
            
            # Slowly close until resistance detected
            print("2. Closing slowly until resistance detected...")
            print("   Position | Current | Status")
            print("   ---------|---------|-------")
            
            resistance_detected = False
            test_positions = [95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35, 30, 25, 20, 15, 10, 5, 0]
            
            for pos in test_positions:
                if resistance_detected:
                    break
                    
                print(f"   {pos:7d}% |         | Moving...")
                controller.execute_command(pos, 100.0)
                time.sleep(1)  # Wait for movement to complete
                
                # Read current multiple times for average
                current_readings = []
                for _ in range(3):
                    current = controller._read_current()
                    current_readings.append(current)
                    time.sleep(0.1)
                
                avg_current = sum(current_readings) / len(current_readings)
                
                # Check if we're in torque mode (resistance detected)
                is_torque_mode = controller.control_mode == 'torque' or controller.control_mode == 'backoff_torque'
                
                status = "RESISTANCE!" if is_torque_mode else "OK"
                print(f"   {pos:7d}% | {avg_current:7.0f} | {status}")
                
                if is_torque_mode:
                    resistance_detected = True
                    print(f"\n   ✅ Resistance detected at {pos}% with current {avg_current}")
                    break
            
            if not resistance_detected:
                print("\n   ❌ No resistance detected - reached 0%")
            
            # Reopen for next test
            print("3. Reopening to 100%...")
            controller.execute_command(100.0, 100.0)
            time.sleep(3)
            
            # Wait between tests
            if test_num < 5:
                print("4. Waiting 3 seconds before next test...")
                time.sleep(3)
        
        print("\n✅ RESISTANCE MAPPING TEST COMPLETE")
        print("=" * 60)
        print("Review the results above to identify:")
        print("- At what position % resistance typically occurs")
        print("- Current levels before vs at resistance")
        print("- Consistency across the 5 tests")
        
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
    print("🔧 EZGripper Resistance Mapping Test")
    print("This test maps exactly where back pressure occurs")
    print("to help determine the optimal position threshold for resistance detection")
    
    success = test_resistance_mapping()
    
    if success:
        print("\n🎉 RESISTANCE MAPPING TEST COMPLETED!")
        print("Use the results to optimize the resistance detection position threshold")
    else:
        print("\n❌ RESISTANCE MAPPING TEST FAILED")
    
    return success

if __name__ == "__main__":
    main()
