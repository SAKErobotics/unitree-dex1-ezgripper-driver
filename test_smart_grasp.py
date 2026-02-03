#!/usr/bin/env python3
"""
Test Smart Grasp Reaction

Demonstrates the default production grasping algorithm:
1. Fast close (100% effort)
2. Contact detection with 5-cycle filter
3. Rapid force reduction (100% → 50%) as position stabilizes
4. Grasp set detection (position change = 0)
5. Temperature-aware holding (30-50% force based on temp)
"""

import sys
import time
sys.path.insert(0, 'libezgripper')

from lib_robotis import create_connection
from libezgripper import create_gripper
from libezgripper.config import load_config
from libezgripper.collision_reactions import SmartGraspReaction


def test_smart_grasp():
    """Test complete smart grasp sequence"""
    print("\n" + "="*70)
    print("SMART GRASP TEST - Production Grasping Algorithm")
    print("="*70)
    
    # Connect
    print("\n1. Connecting to gripper...")
    connection = create_connection(dev_name='/dev/ttyUSB0', baudrate=1000000)
    time.sleep(1.0)
    
    config = load_config()
    gripper = create_gripper(connection, 'test', [1], config)
    
    # Calibrate first
    print("\n2. Calibrating...")
    if not gripper.calibrate():
        print("❌ Calibration failed")
        return
    
    print(f"✅ Calibration complete. Zero position: {gripper.zero_positions[0]}")
    time.sleep(1.0)
    
    # Open gripper
    print("\n3. Opening gripper to 100%...")
    gripper.goto_position(100, 50)
    for _ in range(30):
        gripper.update_main_loop()
        time.sleep(0.033)
    
    print("\n4. Setting up Smart Grasp reaction...")
    print("   - Max force: 100%")
    print("   - Grasp set force: 50%")
    print("   - Holding force: 30-50%")
    print("   - Temperature monitoring: 60°C warning, 70°C critical")
    
    # Create smart grasp reaction
    smart_grasp = SmartGraspReaction(
        max_force=100,
        grasp_set_force=50,
        holding_force_low=30,
        holding_force_mid=50,
        temp_warning=60,
        temp_critical=70
    )
    
    # Enable collision monitoring with smart grasp
    gripper.enable_collision_monitoring(smart_grasp)
    
    print("\n5. Starting grasp sequence...")
    print("   Place object in gripper path...")
    time.sleep(2.0)
    
    print("\n6. Closing at 100% effort...")
    gripper.goto_position(0, 100)
    
    # Monitor grasp progression
    print("\n" + "="*70)
    print("GRASP MONITORING")
    print("="*70)
    
    last_state = None
    cycle_count = 0
    
    for i in range(300):  # Up to 10 seconds
        result = gripper.update_main_loop()
        cycle_count += 1
        
        if not result:
            continue
        
        sensor_data = result.get('sensor_data', {})
        reaction_result = result.get('reaction_result')
        
        if reaction_result:
            grasp_state = reaction_result.get('grasp_state')
            current_force = reaction_result.get('current_force', 0)
            control_output = reaction_result.get('control_output', {})
            
            # Print state changes
            if grasp_state != last_state:
                print(f"\n{'='*70}")
                print(f"STATE CHANGE: {last_state} → {grasp_state}")
                print(f"{'='*70}")
                last_state = grasp_state
            
            # Print periodic updates
            if cycle_count % 10 == 0:
                position = sensor_data.get('position', 0)
                current = sensor_data.get('current', 0)
                temp = sensor_data.get('temperature', 0)
                
                print(f"[{i:3d}] State: {grasp_state:12s} | "
                      f"Force: {current_force:5.1f}% | "
                      f"Pos: {position:5.1f}% | "
                      f"Cur: {current:4.0f}mA | "
                      f"Temp: {temp:4.1f}°C")
                
                # Show additional info based on state
                if grasp_state == 'grasping':
                    elapsed = control_output.get('elapsed', 0)
                    pos_change = control_output.get('position_change', 0)
                    print(f"      → Ramping down force (t={elapsed:.3f}s, Δpos={pos_change:.1f})")
                
                elif grasp_state == 'holding':
                    action = control_output.get('action', '')
                    pos_change = control_output.get('position_change', 0)
                    if action == 'slip_detected_increase_force':
                        print(f"      → Slip detected! Increasing force (Δpos={pos_change:.1f})")
                    elif action == 'warning_temp_limit_force':
                        print(f"      → Temperature warning - limiting force")
                    elif action == 'critical_temp_reduce_force':
                        print(f"      → CRITICAL TEMP - reducing force!")
            
            # Check if grasp is stable in holding mode
            if grasp_state == 'holding' and i > 100:
                # Hold for a while to test temperature monitoring
                if cycle_count > 200:  # ~6.6 seconds of holding
                    print(f"\n{'='*70}")
                    print("GRASP TEST COMPLETE")
                    print(f"{'='*70}")
                    
                    # Get statistics
                    stats = smart_grasp.controller.get_statistics()
                    print(f"\nGrasp Statistics:")
                    print(f"  Final state: {stats.get('state')}")
                    print(f"  Current force: {stats.get('current_force', 0):.1f}%")
                    if 'grasp_duration' in stats:
                        print(f"  Grasp duration: {stats['grasp_duration']:.3f}s")
                    if 'time_since_grasp_set' in stats:
                        print(f"  Hold time: {stats['time_since_grasp_set']:.3f}s")
                    if 'avg_temperature' in stats:
                        print(f"  Avg temperature: {stats['avg_temperature']:.1f}°C")
                        print(f"  Max temperature: {stats['max_temperature']:.1f}°C")
                    
                    break
        
        time.sleep(0.033)  # 30Hz
    
    # Release
    print("\n7. Releasing grasp...")
    gripper.disable_collision_monitoring()
    gripper.goto_position(100, 50)
    for _ in range(30):
        gripper.update_main_loop()
        time.sleep(0.033)
    
    print("\n✅ Test complete!")


def test_force_curve_visualization():
    """Visualize the force reduction curve"""
    print("\n" + "="*70)
    print("FORCE CURVE VISUALIZATION")
    print("="*70)
    
    from libezgripper.grasp_controller import GraspController
    
    controller = GraspController(
        max_force=100,
        grasp_set_force=50
    )
    
    print("\nForce reduction over time (exponential decay):")
    print("Time(s) | Force(%) | Visual")
    print("-" * 70)
    
    for t_ms in range(0, 1000, 50):  # 0 to 1 second
        t = t_ms / 1000.0
        
        # Simulate force curve
        decay_rate = 3.0
        force_range = 100 - 50
        force = 50 + force_range * (2.71828 ** (-decay_rate * t))
        
        # Visual bar
        bar_length = int(force / 2)
        bar = "█" * bar_length
        
        print(f"{t:6.3f}  | {force:6.1f}%  | {bar}")
    
    print("\nKey points:")
    print("  - Starts at 100% (max force)")
    print("  - Exponential decay with rate = 3.0")
    print("  - Reaches ~50% in 0.5 seconds")
    print("  - Faster reduction if position stabilizes early")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Smart Grasp Reaction')
    parser.add_argument('--visualize', action='store_true', 
                       help='Visualize force curve only (no hardware)')
    
    args = parser.parse_args()
    
    if args.visualize:
        test_force_curve_visualization()
    else:
        test_smart_grasp()
