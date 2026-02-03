#!/usr/bin/env python3
"""
Example: Using Modular Collision Detection System

Demonstrates different collision reaction strategies for various use cases.
"""

import sys
import time
sys.path.insert(0, 'libezgripper')

from lib_robotis import create_connection
from libezgripper import create_gripper
from libezgripper.config import load_config
from libezgripper.collision_reactions import (
    CalibrationReaction,
    AdaptiveGripReaction,
    HoldPositionReaction,
    RelaxReaction,
    CustomReaction
)


def example_1_calibration():
    """Example 1: Calibration with collision detection"""
    print("\n" + "="*60)
    print("EXAMPLE 1: Calibration")
    print("="*60)
    
    connection = create_connection(dev_name='/dev/ttyUSB0', baudrate=1000000)
    time.sleep(1.0)
    
    config = load_config()
    gripper = create_gripper(connection, 'test', [1], config)
    
    # Calibration automatically uses CalibrationReaction
    # - Closes until collision
    # - Records zero position
    # - Opens to 50%
    gripper.calibrate()
    
    print(f"✅ Calibration complete. Zero position: {gripper.zero_positions[0]}")


def example_2_adaptive_grip():
    """Example 2: Adaptive grip - fast close, gentle hold"""
    print("\n" + "="*60)
    print("EXAMPLE 2: Adaptive Grip")
    print("="*60)
    
    connection = create_connection(dev_name='/dev/ttyUSB0', baudrate=1000000)
    time.sleep(1.0)
    
    config = load_config()
    gripper = create_gripper(connection, 'test', [1], config)
    
    # Assume already calibrated
    gripper.zero_positions[0] = 58000  # Example zero position
    
    # Set adaptive grip reaction: reduce to 30% effort on contact
    adaptive_reaction = AdaptiveGripReaction(holding_effort=30)
    gripper.enable_collision_monitoring(adaptive_reaction)
    
    print("Closing gripper at 100% effort...")
    gripper.goto_position(0, 100)  # Close fast
    
    # Monitor for collision
    for i in range(100):  # Up to 3 seconds
        result = gripper.update_main_loop()
        
        if result['collision_detected']:
            print(f"✅ Contact detected! Reaction: {result['reaction_result']}")
            break
        
        time.sleep(0.033)  # 30Hz
    
    print("Gripper now holding object with 30% effort")


def example_3_obstacle_detection():
    """Example 3: Stop at obstacle while opening"""
    print("\n" + "="*60)
    print("EXAMPLE 3: Obstacle Detection")
    print("="*60)
    
    connection = create_connection(dev_name='/dev/ttyUSB0', baudrate=1000000)
    time.sleep(1.0)
    
    config = load_config()
    gripper = create_gripper(connection, 'test', [1], config)
    
    # Set hold position reaction: stop if obstacle detected
    hold_reaction = HoldPositionReaction(hold_effort=50)
    gripper.enable_collision_monitoring(hold_reaction)
    
    print("Opening gripper...")
    gripper.goto_position(100, 80)  # Open
    
    # Monitor for collision
    for i in range(100):
        result = gripper.update_main_loop()
        
        if result['collision_detected']:
            print(f"🛑 Obstacle detected! Stopped at: {result['reaction_result']['hold_position']:.1f}%")
            break
        
        time.sleep(0.033)


def example_4_safety_relax():
    """Example 4: Safety relax on excessive force"""
    print("\n" + "="*60)
    print("EXAMPLE 4: Safety Relax")
    print("="*60)
    
    connection = create_connection(dev_name='/dev/ttyUSB0', baudrate=1000000)
    time.sleep(1.0)
    
    config = load_config()
    gripper = create_gripper(connection, 'test', [1], config)
    
    # Set relax reaction: open to 80% if excessive force
    relax_reaction = RelaxReaction(safe_position=80, safe_effort=20)
    gripper.enable_collision_monitoring(relax_reaction)
    
    print("Closing gripper with high force...")
    gripper.goto_position(0, 100)
    
    # Monitor for excessive force
    for i in range(100):
        result = gripper.update_main_loop()
        
        if result['collision_detected']:
            print(f"⚠️ Excessive force! Opening to safe position")
            print(f"   Trigger current: {result['reaction_result']['trigger_current']}mA")
            break
        
        time.sleep(0.033)


def example_5_custom_reaction():
    """Example 5: Custom reaction with user-defined logic"""
    print("\n" + "="*60)
    print("EXAMPLE 5: Custom Reaction")
    print("="*60)
    
    def my_custom_reaction(gripper, sensor_data):
        """Custom logic: oscillate grip on contact"""
        current_pos = sensor_data.get('position', 0)
        
        print(f"  🎯 Custom reaction triggered at {current_pos:.1f}%")
        print(f"  🔄 Oscillating grip...")
        
        # Example: oscillate between current position ±10%
        gripper.goto_position(current_pos + 10, 40)
        time.sleep(0.5)
        gripper.goto_position(current_pos - 10, 40)
        
        return {
            'action_taken': 'oscillate_grip',
            'new_position': current_pos - 10,
            'new_effort': 40,
            'stop_monitoring': False
        }
    
    connection = create_connection(dev_name='/dev/ttyUSB0', baudrate=1000000)
    time.sleep(1.0)
    
    config = load_config()
    gripper = create_gripper(connection, 'test', [1], config)
    
    # Set custom reaction
    custom_reaction = CustomReaction(callback=my_custom_reaction)
    gripper.enable_collision_monitoring(custom_reaction)
    
    print("Closing gripper with custom reaction...")
    gripper.goto_position(0, 100)
    
    # Monitor
    for i in range(100):
        result = gripper.update_main_loop()
        
        if result['collision_detected']:
            print(f"✅ Custom reaction executed")
            break
        
        time.sleep(0.033)


def example_6_dynamic_switching():
    """Example 6: Switch reactions dynamically during operation"""
    print("\n" + "="*60)
    print("EXAMPLE 6: Dynamic Reaction Switching")
    print("="*60)
    
    connection = create_connection(dev_name='/dev/ttyUSB0', baudrate=1000000)
    time.sleep(1.0)
    
    config = load_config()
    gripper = create_gripper(connection, 'test', [1], config)
    
    # Phase 1: Fast close with adaptive grip
    print("\nPhase 1: Fast close with adaptive grip")
    gripper.set_collision_reaction(AdaptiveGripReaction(holding_effort=30))
    gripper.enable_collision_monitoring()
    gripper.goto_position(0, 100)
    
    for i in range(50):
        result = gripper.update_main_loop()
        if result['collision_detected']:
            print(f"✅ Object gripped with adaptive force")
            break
        time.sleep(0.033)
    
    time.sleep(1.0)
    
    # Phase 2: Open with obstacle detection
    print("\nPhase 2: Open with obstacle detection")
    gripper.set_collision_reaction(HoldPositionReaction(hold_effort=50))
    gripper.enable_collision_monitoring()
    gripper.goto_position(100, 80)
    
    for i in range(50):
        result = gripper.update_main_loop()
        if result['collision_detected']:
            print(f"🛑 Obstacle detected during opening")
            break
        time.sleep(0.033)
    
    print("\n✅ Dynamic switching complete")


if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════╗
║  EZGripper Modular Collision Detection Examples             ║
╚══════════════════════════════════════════════════════════════╝

Choose an example:
  1. Calibration (record zero position)
  2. Adaptive Grip (fast close, gentle hold)
  3. Obstacle Detection (stop at obstacle)
  4. Safety Relax (open on excessive force)
  5. Custom Reaction (user-defined logic)
  6. Dynamic Switching (change reactions during operation)
  
Enter number (1-6): """)
    
    choice = input().strip()
    
    examples = {
        '1': example_1_calibration,
        '2': example_2_adaptive_grip,
        '3': example_3_obstacle_detection,
        '4': example_4_safety_relax,
        '5': example_5_custom_reaction,
        '6': example_6_dynamic_switching
    }
    
    if choice in examples:
        examples[choice]()
    else:
        print("Invalid choice")
