#!/usr/bin/env python3
"""
Wrapping Characterization Test

Characterizes how the gripper behaves when wrapping around objects,
specifically looking at "beyond zero" position values and resistance patterns.
"""

import time
import logging
from hardware_controller import EZGripperHardwareController

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("wrapping_characterization")

def test_wrapping_characterization():
    """Test wrapping behavior with an object"""
    
    print("🎯 WRAPPING CHARACTERIZATION TEST")
    print("=" * 60)
    print("This test characterizes gripper behavior when wrapping around objects")
    print("Specifically looking for 'beyond zero' position values and resistance patterns")
    print()
    
    try:
        # Initialize hardware controller
        controller = EZGripperHardwareController("/dev/ttyUSB0", "left")
        
        print("📍 SETUP PHASE")
        print("-" * 40)
        print("1. Moving to calibrated open position...")
        controller.execute_command(100.0, 100.0)
        time.sleep(3)
        
        print("2. Reading calibrated open position...")
        open_pos = controller.gripper.get_position()
        print(f"   Calibrated open position: {open_pos:.1f}%")
        
        print("\n📍 WRAPPING TEST")
        print("-" * 40)
        print("3. Moving to 20% to engage wrapping object with higher torque...")
        controller.execute_command(20.0, 100.0)
        time.sleep(3)
        
        print("4. Checking if torque mode engaged...")
        is_torque_mode = controller.control_mode == 'torque' or controller.control_mode == 'backoff_torque'
        print(f"   Torque mode engaged: {is_torque_mode}")
        print(f"   Current control mode: {controller.control_mode}")
        
        if not is_torque_mode:
            print("   ⚠️  Torque mode not engaged - trying 15%...")
            controller.execute_command(15.0, 100.0)
            time.sleep(2)
            is_torque_mode = controller.control_mode == 'torque' or controller.control_mode == 'backoff_torque'
            print(f"   Torque mode engaged at 15%: {is_torque_mode}")
        
        if not is_torque_mode:
            print("   ⚠️  Torque mode not engaged - trying 10%...")
            controller.execute_command(10.0, 100.0)
            time.sleep(2)
            is_torque_mode = controller.control_mode == 'torque' or controller.control_mode == 'backoff_torque'
            print(f"   Torque mode engaged at 10%: {is_torque_mode}")
        
        if not is_torque_mode:
            print("   ⚠️  Torque mode not engaged - trying 5%...")
            controller.execute_command(5.0, 100.0)
            time.sleep(2)
            is_torque_mode = controller.control_mode == 'torque' or controller.control_mode == 'backoff_torque'
            print(f"   Torque mode engaged at 5%: {is_torque_mode}")
        
        if not is_torque_mode:
            print("   ⚠️  Torque mode not engaged - trying 0% (full wrap)...")
            controller.execute_command(0.0, 100.0)
            time.sleep(3)
            is_torque_mode = controller.control_mode == 'torque' or controller.control_mode == 'backoff_torque'
            print(f"   Torque mode engaged at 0%: {is_torque_mode}")
        
        if is_torque_mode:
            print("\n5. Characterizing wrapping behavior...")
            print("   Reading multiple position and current samples...")
            
            # Read multiple samples to get stable readings
            positions = []
            currents = []
            
            for i in range(10):
                pos = controller.gripper.get_position()
                current = controller._read_current()
                positions.append(pos)
                currents.append(current)
                print(f"   Sample {i+1}: position={pos:.1f}%, current={current}")
                time.sleep(0.2)
            
            avg_position = sum(positions) / len(positions)
            avg_current = sum(currents) / len(currents)
            min_position = min(positions)
            max_position = max(positions)
            
            print(f"\n📊 WRAPPING CHARACTERIZATION RESULTS:")
            print(f"   Average position: {avg_position:.1f}%")
            print(f"   Position range: {min_position:.1f}% to {max_position:.1f}%")
            print(f"   Average current: {avg_current:.0f}")
            print(f"   Current range: {min(currents)} to {max(currents)}")
            
            # Check if we're "beyond zero"
            if avg_position < 0:
                print(f"   ✅ BEYOND ZERO DETECTED: {avg_position:.1f}%")
            elif avg_position < 5:
                print(f"   ⚠️  NEAR ZERO: {avg_position:.1f}%")
            else:
                print(f"   📍 ABOVE ZERO: {avg_position:.1f}%")
            
            # Check if it's a wrapping scenario
            if min_position < 0 or max_position < 0:
                print(f"   🎯 WRAPPING SCENARIO CONFIRMED")
                print(f"   📈 This data will help design wrapping-specific logic")
            else:
                print(f"   📍 STANDARD GRIPPING SCENARIO")
        
        else:
            print("   ❌ Could not engage torque mode - object may not be present or positioned correctly")
        
        print("\n6. Returning to open position...")
        controller.execute_command(100.0, 100.0)
        time.sleep(3)
        
        print("\n✅ WRAPPING CHARACTERIZATION TEST COMPLETE")
        print("=" * 60)
        print("Review the results above to understand:")
        print("- Whether 'beyond zero' positions occur during wrapping")
        print("- Current patterns during wrapping vs standard gripping")
        print("- Position stability and range during wrapping")
        print("- How this differs from our 65% resistance mapping")
        
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
    print("🔧 EZGripper Wrapping Characterization Test")
    print("This test characterizes gripper behavior when wrapping around objects")
    print("to understand 'beyond zero' position values and design appropriate control logic")
    
    success = test_wrapping_characterization()
    
    if success:
        print("\n🎉 WRAPPING CHARACTERIZATION TEST COMPLETED!")
        print("Use the results to design wrapping-specific control logic")
    else:
        print("\n❌ WRAPPING CHARACTERIZATION TEST FAILED")
    
    return success

if __name__ == "__main__":
    main()
