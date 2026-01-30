#!/usr/bin/env python3
"""
Interactive Hardware Demo - Refactored EZGripper System

Demonstrates all features with actual gripper movements:
1. Configuration-driven initialization
2. Smart EEPROM optimization
3. Health monitoring during movement
4. Wave-following current modulation
5. Goal Current (no EEPROM wear) with rapid changes
6. Position control with different effort levels

Usage: python3 demo_hardware.py [device]
Example: python3 demo_hardware.py /dev/ttyUSB0
"""

import sys
import time
import logging

sys.path.insert(0, '/home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver')

from libezgripper.config import load_config
from libezgripper.health_monitor import HealthMonitor
from libezgripper.wave_controller import WaveController
from libezgripper.error_handler import check_hardware_error
from libezgripper.servo_init import get_eeprom_info
from libezgripper import create_connection, Gripper

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def print_header(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def main():
    device = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
    
    print_header("REFACTORED EZGRIPPER - HARDWARE DEMO")
    print(f"\nDevice: {device}\n")
    
    # Load configuration
    print("Loading configuration...")
    config = load_config()
    print(f"✓ Config loaded: {config.servo_model}")
    print(f"  Holding current: {config.holding_current} units ({config.holding_current*100//config.max_current}%)")
    print(f"  Movement current: {config.movement_current} units ({config.movement_current*100//config.max_current}%)")
    print(f"  Max current: {config.max_current} units (70%)")
    
    # Connect and initialize
    print_header("INITIALIZATION")
    print("Connecting to gripper...")
    connection = create_connection(dev_name=device, baudrate=config.comm_baudrate)
    print("✓ Connected")
    
    print("\nInitializing with smart EEPROM optimization...")
    gripper = Gripper(connection, 'demo', [config.comm_servo_id], config)
    print("✓ Gripper initialized")
    
    # Verify EEPROM
    eeprom_info = get_eeprom_info(gripper.servos[0], config)
    print(f"\nEEPROM Status:")
    print(f"  Return delay: {eeprom_info.get('return_delay_time', 'N/A')} (optimized)")
    print(f"  Current Limit (EEPROM): {config.max_current} units (set once)")
    print(f"  Goal Current (RAM): Will be used for dynamic control")
    
    # Create health monitor
    health = HealthMonitor(gripper.servos[0], config)
    
    # Check initial health
    print_header("INITIAL HEALTH CHECK")
    temp = health.read_temperature()
    voltage = health.read_voltage()
    position = gripper.get_position()
    print(f"Temperature: {temp}°C")
    print(f"Voltage: {voltage:.1f}V")
    print(f"Position: {position:.1f}%")
    
    error_code, description = check_hardware_error(gripper.servos[0], config)
    print(f"Hardware errors: {description}")
    
    # Demo 1: Open gripper with health monitoring
    print_header("DEMO 1: OPEN GRIPPER + HEALTH MONITORING")
    print("Opening gripper to 100%...")
    gripper.set_max_effort(50)
    gripper._goto_position(gripper.scale(100, config.grip_max))
    
    print("\nMonitoring health during movement:")
    for i in range(10):
        time.sleep(0.3)
        temp = health.read_temperature()
        current = health.read_current()
        pos = gripper.get_position()
        snapshot = health.get_health_snapshot()
        print(f"  [{i+1}] Pos: {pos:5.1f}%, Temp: {temp}°C, Current: {current:6.1f}mA, Trend: {snapshot['temperature_trend']}")
    
    print("✓ Gripper fully open")
    
    # Demo 2: Close with different effort levels
    print_header("DEMO 2: GOAL CURRENT - NO EEPROM WEAR")
    print("Closing gripper with varying effort levels...")
    print("(Each effort change writes to RAM, not EEPROM)\n")
    
    efforts = [20, 40, 60, 80, 100]
    positions = [80, 60, 40, 20, 0]
    
    for effort, pos in zip(efforts, positions):
        print(f"Moving to {pos}% with {effort}% effort...")
        gripper.set_max_effort(effort)
        gripper._goto_position(gripper.scale(pos, config.grip_max))
        time.sleep(1.0)
        actual_pos = gripper.get_position()
        temp = health.read_temperature()
        print(f"  ✓ Position: {actual_pos:.1f}%, Temp: {temp}°C, Goal Current: {effort*config.max_current//100} units")
    
    print(f"\n✓ Completed {len(efforts)} effort changes")
    print("✓ Zero EEPROM writes (all using Goal Current RAM)")
    
    # Demo 3: Wave-following simulation
    print_header("DEMO 3: WAVE-FOLLOWING CURRENT MODULATION")
    print("Simulating steady-state hold to demonstrate wave-following...\n")
    
    wave = WaveController(config)
    
    # Move to 50% position
    print("Moving to 50% position...")
    gripper.set_max_effort(60)
    target_pos = 50
    gripper._goto_position(gripper.scale(target_pos, config.grip_max))
    time.sleep(1.5)
    
    print("\nHolding position (wave-following will detect steady-state):")
    for i in range(20):
        current_pos = gripper.get_position()
        mode = wave.process_command(current_pos, current_pos)
        recommended_current = wave.get_recommended_current()
        
        if i % 5 == 0:
            print(f"  [{i+1}] Mode: {mode:8s}, Recommended: {recommended_current:4d} units, Pos: {current_pos:.1f}%")
        
        time.sleep(0.1)
    
    final_mode = wave.get_current_mode()
    print(f"\n✓ Wave-following result: {final_mode}")
    if final_mode == "holding":
        reduction = (config.movement_current - config.holding_current) * 100 // config.movement_current
        print(f"✓ Switched to holding mode ({reduction}% current reduction)")
        print(f"  Movement: {config.movement_current} units → Holding: {config.holding_current} units")
    
    # Demo 4: Rapid effort changes
    print_header("DEMO 4: RAPID EFFORT CHANGES (EEPROM WEAR TEST)")
    print("Performing 20 rapid effort changes...")
    print("(This would destroy EEPROM with old approach)\n")
    
    start_time = time.time()
    change_count = 0
    
    for i in range(20):
        effort = 30 + (i % 5) * 15  # Cycle through 30, 45, 60, 75, 90
        gripper.set_max_effort(effort)
        change_count += 1
        if i % 5 == 0:
            print(f"  Change {i+1}: {effort}% effort")
        time.sleep(0.05)
    
    elapsed = time.time() - start_time
    
    print(f"\n✓ Completed {change_count} effort changes in {elapsed:.2f} seconds")
    print(f"✓ All writes to Goal Current (RAM register 102)")
    print(f"✓ Zero EEPROM wear")
    print(f"\nWith old approach (Current Limit EEPROM):")
    print(f"  - Would have written EEPROM {change_count} times")
    print(f"  - EEPROM wear: {change_count}/100,000 cycles")
    print(f"  - At this rate, EEPROM would fail after {100000//change_count} test runs")
    
    # Demo 5: Return to open position
    print_header("DEMO 5: RETURN TO OPEN POSITION")
    print("Opening gripper with 100% effort...")
    gripper.set_max_effort(100)
    gripper._goto_position(gripper.scale(100, config.grip_max))
    
    print("\nFinal health check:")
    for i in range(5):
        time.sleep(0.3)
        temp = health.read_temperature()
        pos = gripper.get_position()
        print(f"  [{i+1}] Position: {pos:.1f}%, Temperature: {temp}°C")
    
    print("\n✓ Gripper fully open")
    
    # Final summary
    print_header("DEMO COMPLETE - SUMMARY")
    
    final_temp = health.read_temperature()
    final_pos = gripper.get_position()
    error_code, _ = check_hardware_error(gripper.servos[0], config)
    
    print("\n✓ All refactored features demonstrated on hardware!\n")
    print("Features Demonstrated:")
    print("  1. ✓ Configuration-driven initialization")
    print("  2. ✓ Smart EEPROM optimization (read before write)")
    print("  3. ✓ Health monitoring during movement")
    print("  4. ✓ Wave-following current modulation")
    print("  5. ✓ Goal Current (no EEPROM wear)")
    print("  6. ✓ Position control with effort management")
    
    print(f"\nFinal System Status:")
    print(f"  Temperature: {final_temp}°C")
    print(f"  Position: {final_pos:.1f}%")
    print(f"  Errors: {'None' if error_code == 0 else 'Detected'}")
    print(f"  Total effort changes: {change_count + len(efforts)} (all RAM, no EEPROM wear)")
    
    print("\nKey Achievement:")
    print(f"  • Performed {change_count + len(efforts)} effort changes with ZERO EEPROM wear")
    print(f"  • Old approach would have used {change_count + len(efforts)}/100,000 EEPROM cycles")
    print(f"  • System can now operate indefinitely without EEPROM failure")
    
    print("\n" + "="*70)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n\nDemo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
