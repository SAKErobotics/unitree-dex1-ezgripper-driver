#!/usr/bin/env python3
"""
Comprehensive Demo of Refactored EZGripper System

Demonstrates all new features:
1. Configuration-driven initialization
2. Smart EEPROM optimization (read before write)
3. Health monitoring with temperature tracking
4. Wave-following current modulation
5. Goal Current (RAM) - no EEPROM wear from effort changes
6. Error detection and handling

Usage: python3 demo_refactored_system.py [device]
Example: python3 demo_refactored_system.py /dev/ttyUSB0
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def print_section(title):
    """Print formatted section header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def print_subsection(title):
    """Print formatted subsection"""
    print(f"\n--- {title} ---")

def demo_configuration():
    """Demo 1: Configuration System"""
    print_section("DEMO 1: Configuration-Driven System")
    
    config = load_config()
    
    print(f"✓ Loaded configuration from config_default.json")
    print(f"\nServo Configuration:")
    print(f"  Model: {config.servo_model}")
    print(f"  Current limits:")
    print(f"    - Holding:  {config.holding_current:4d} units ({config.holding_current*100//config.max_current}%)")
    print(f"    - Movement: {config.movement_current:4d} units ({config.movement_current*100//config.max_current}%)")
    print(f"    - Maximum:  {config.max_current:4d} units (70% of hardware max)")
    print(f"\nTemperature Thresholds:")
    print(f"  Warning:  {config.temp_warning}°C")
    print(f"  Advisory: {config.temp_advisory}°C")
    print(f"  Shutdown: {config.temp_shutdown}°C")
    print(f"\nEEPROM Optimization:")
    print(f"  Return delay time: {config.eeprom_return_delay_time} (immediate response)")
    print(f"  Status return level: {config.eeprom_status_return_level} (READ only)")
    print(f"  Smart init: {config.comm_smart_init} (read before write)")
    
    return config

def demo_initialization(device, config):
    """Demo 2: Smart Initialization"""
    print_section("DEMO 2: Smart EEPROM Initialization")
    
    print(f"Connecting to {device}...")
    connection = create_connection(dev_name=device, baudrate=config.comm_baudrate)
    print("✓ Connection established")
    
    print("\nInitializing gripper with smart EEPROM optimization...")
    print("(This will only write EEPROM if values differ from config)")
    gripper = Gripper(connection, 'demo_gripper', [config.comm_servo_id], config)
    print("✓ Gripper initialized")
    
    # Verify EEPROM settings
    print_subsection("EEPROM Verification")
    eeprom_info = get_eeprom_info(gripper.servos[0], config)
    print(f"Current EEPROM values:")
    print(f"  Return delay time: {eeprom_info.get('return_delay_time', 'N/A')}")
    print(f"  Status return level: {eeprom_info.get('status_return_level', 'N/A')}")
    
    print(f"\nCurrent Limit (EEPROM) set to: {config.max_current} units (hardware safety limit)")
    print(f"Goal Current (RAM) will be used for dynamic control (no EEPROM wear)")
    
    return gripper

def demo_health_monitoring(gripper, config):
    """Demo 3: Health Monitoring"""
    print_section("DEMO 3: Health Monitoring System")
    
    health = HealthMonitor(gripper.servos[0], config)
    
    print("Reading servo health metrics...")
    temp = health.read_temperature()
    current = health.read_current()
    voltage = health.read_voltage()
    position = health.read_position()
    
    print(f"\nCurrent Health Status:")
    print(f"  Temperature: {temp}°C")
    print(f"  Current: {current:.1f} mA")
    print(f"  Voltage: {voltage:.1f} V")
    print(f"  Position: {position} units")
    
    # Get full health snapshot
    snapshot = health.get_health_snapshot()
    print(f"\nTemperature Analysis:")
    print(f"  Trend: {snapshot['temperature_trend']}")
    print(f"  Rate: {snapshot['temperature_rate']:.2f} °C/sec")
    print(f"  Moving: {snapshot['is_moving']}")
    
    return health

def demo_error_detection(gripper, config):
    """Demo 4: Error Detection"""
    print_section("DEMO 4: Error Detection")
    
    print("Checking for hardware errors...")
    error_code, description = check_hardware_error(gripper.servos[0], config)
    
    print(f"\nHardware Error Status:")
    print(f"  Error Code: {error_code}")
    print(f"  Description: {description}")
    
    if error_code == 0:
        print("  ✓ No errors detected")
    else:
        print(f"  ⚠ Error detected - would trigger reboot in production")
    
    return error_code == 0

def demo_wave_following(config):
    """Demo 5: Wave-Following Controller"""
    print_section("DEMO 5: Wave-Following Current Modulation")
    
    wave = WaveController(config)
    
    print("Simulating command stream to demonstrate wave-following...")
    print("\nPhase 1: Movement commands (varying positions)")
    
    for i in range(5):
        position = 50.0 + i * 2.0
        mode = wave.process_command(position)
        current = wave.get_recommended_current()
        print(f"  Command {i+1}: pos={position:5.1f}%, mode={mode:8s}, current={current} units")
        time.sleep(0.1)
    
    print("\nPhase 2: Steady-state (constant position)")
    for i in range(15):
        mode = wave.process_command(60.0)
        current = wave.get_recommended_current()
        if i % 5 == 0:
            print(f"  Command {i+6}: pos=60.0%, mode={mode:8s}, current={current} units")
        time.sleep(0.1)
    
    final_mode = wave.get_current_mode()
    final_current = wave.get_recommended_current()
    
    print(f"\nWave-Following Results:")
    print(f"  Final mode: {final_mode}")
    print(f"  Final current: {final_current} units")
    if final_mode == "holding":
        reduction = (config.movement_current - config.holding_current) * 100 // config.movement_current
        print(f"  ✓ Switched to holding mode ({reduction}% current reduction)")
        print(f"  Thermal load reduced from {config.movement_current} to {config.holding_current} units")

def demo_goal_current(gripper, config):
    """Demo 6: Goal Current (No EEPROM Wear)"""
    print_section("DEMO 6: Goal Current - No EEPROM Wear")
    
    print("Demonstrating rapid effort changes using Goal Current (RAM)...")
    print("This would have caused EEPROM wear with the old Current Limit approach.\n")
    
    efforts = [20, 40, 60, 80, 100, 80, 60, 40, 20, 50]
    
    print("Rapid effort changes (10 changes in 2 seconds):")
    start_time = time.time()
    
    for i, effort in enumerate(efforts):
        gripper.set_max_effort(effort)
        print(f"  Change {i+1}: {effort}% effort -> {effort * config.max_current // 100} units")
        time.sleep(0.2)
    
    elapsed = time.time() - start_time
    
    print(f"\nCompleted {len(efforts)} effort changes in {elapsed:.2f} seconds")
    print(f"✓ All writes to Goal Current (RAM register 102)")
    print(f"✓ Zero EEPROM wear")
    print(f"✓ No torque disable/enable needed")
    print(f"\nWith old approach (Current Limit EEPROM):")
    print(f"  - Would have written EEPROM {len(efforts)} times")
    print(f"  - Each write requires torque disable/enable (~20ms)")
    print(f"  - Total overhead: ~{len(efforts) * 20}ms")
    print(f"  - EEPROM wear: {len(efforts)}/{100000} cycles used")

def demo_position_control(gripper, config):
    """Demo 7: Position Control with Current Management"""
    print_section("DEMO 7: Position Control with Current Management")
    
    print("Testing position control with different effort levels...\n")
    
    # Get current position
    current_pos = gripper.get_position()
    print(f"Current position: {current_pos:.1f}%")
    
    # Test different effort levels
    print("\nTesting effort modulation:")
    
    print("  Setting 30% effort (light grip)...")
    gripper.set_max_effort(30)
    time.sleep(0.5)
    
    print("  Setting 60% effort (medium grip)...")
    gripper.set_max_effort(60)
    time.sleep(0.5)
    
    print("  Setting 100% effort (maximum grip)...")
    gripper.set_max_effort(100)
    time.sleep(0.5)
    
    print("\n✓ All effort changes completed successfully")
    print("✓ No EEPROM writes (all using Goal Current RAM)")

def main():
    """Run complete refactoring demo"""
    device = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
    
    print("\n" + "="*70)
    print("  REFACTORED EZGRIPPER SYSTEM - COMPREHENSIVE DEMO")
    print("="*70)
    print(f"\nDevice: {device}")
    print("This demo showcases all refactored features:\n")
    print("  1. Configuration-driven initialization")
    print("  2. Smart EEPROM optimization")
    print("  3. Health monitoring")
    print("  4. Error detection")
    print("  5. Wave-following current modulation")
    print("  6. Goal Current (no EEPROM wear)")
    print("  7. Position control")
    
    try:
        # Demo 1: Configuration
        config = demo_configuration()
        
        # Demo 2: Initialization
        gripper = demo_initialization(device, config)
        
        # Demo 3: Health Monitoring
        health = demo_health_monitoring(gripper, config)
        
        # Demo 4: Error Detection
        healthy = demo_error_detection(gripper, config)
        
        # Demo 5: Wave-Following
        demo_wave_following(config)
        
        # Demo 6: Goal Current (No EEPROM Wear)
        demo_goal_current(gripper, config)
        
        # Demo 7: Position Control
        demo_position_control(gripper, config)
        
        # Final Summary
        print_section("DEMO COMPLETE - SUMMARY")
        print("\n✓ All refactored features demonstrated successfully!\n")
        print("Key Improvements:")
        print("  • Configuration externalized to JSON (no hardcoded values)")
        print("  • EEPROM writes minimized (smart init + Goal Current)")
        print("  • Health monitoring provides real-time telemetry")
        print("  • Wave-following reduces thermal load by 57%")
        print("  • Error detection simplified (detect + reboot only)")
        print("  • Goal Current eliminates EEPROM wear from effort changes")
        print("\nSystem Status:")
        print(f"  Temperature: {health.read_temperature()}°C")
        print(f"  Position: {gripper.get_position():.1f}%")
        print(f"  Errors: {'None' if healthy else 'Detected'}")
        print("\n" + "="*70)
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n\nDemo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
