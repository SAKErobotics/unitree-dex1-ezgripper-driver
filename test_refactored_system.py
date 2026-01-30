#!/usr/bin/env python3
"""
Test suite for refactored EZGripper system

Tests configuration loading, health monitoring, wave-following, and error handling.
"""

import sys
import time
import logging

sys.path.insert(0, '/home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver')

from libezgripper.config import load_config
from libezgripper.health_monitor import HealthMonitor
from libezgripper.wave_controller import WaveController
from libezgripper.error_handler import check_hardware_error, clear_error_via_reboot
from libezgripper.servo_init import get_eeprom_info, verify_eeprom_settings
from libezgripper import create_connection, Gripper

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Track test results
test_results = {
    'config': False,
    'wave': False,
    'hardware': False,
    'health': False,
    'error': False,
    'position': False
}

print("="*70)
print("Refactored EZGripper System Test")
print("="*70)

# Test 1: Configuration Loading
print("\n1. Testing Configuration System")
print("-"*70)
try:
    config = load_config()
    print(f"✓ Config loaded successfully")
    print(f"  Servo model: {config.servo_model}")
    print(f"  Holding current: {config.holding_current} units")
    print(f"  Movement current: {config.movement_current} units")
    print(f"  Max current: {config.max_current} units")
    print(f"  Temp shutdown: {config.temp_shutdown}°C")
    print(f"  Grip max: {config.grip_max}")
    print(f"  EEPROM settings:")
    print(f"    Return delay time: {config.eeprom_return_delay_time}")
    print(f"    Status return level: {config.eeprom_status_return_level}")
    print(f"  Smart init: {config.comm_smart_init}")
    test_results['config'] = True
except Exception as e:
    print(f"✗ Config loading failed: {e}")
    sys.exit(1)

# Test 2: Wave Controller
print("\n2. Testing Wave-Following Controller")
print("-"*70)
try:
    wave = WaveController(config)
    
    # Simulate command stream with movement
    print("  Simulating movement commands...")
    for i in range(5):
        mode = wave.process_command(50.0 + i, current_position=50.0)
        print(f"    Command {i+1}: position={50.0+i}, mode={mode}")
    
    # Simulate steady state
    print("  Simulating steady state...")
    for i in range(10):
        mode = wave.process_command(55.0, current_position=55.0)
    
    final_mode = wave.get_current_mode()
    recommended_current = wave.get_recommended_current()
    
    print(f"✓ Wave controller working")
    print(f"  Final mode: {final_mode}")
    print(f"  Recommended current: {recommended_current} units")
    
    if final_mode == "holding":
        print(f"  ✓ Correctly switched to holding mode")
    
    test_results['wave'] = True
except Exception as e:
    print(f"✗ Wave controller failed: {e}")

# Test 3: Gripper with Config (requires hardware)
device = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
print(f"\n3. Testing Gripper with Configuration")
print("-"*70)
print(f"  Device: {device}")

try:
    connection = create_connection(dev_name=device, baudrate=config.comm_baudrate)
    print("✓ Connection created")
    
    gripper = Gripper(connection, 'test_gripper', [config.comm_servo_id], config)
    print("✓ Gripper created with config")
    print("  Smart EEPROM initialization completed")
    test_results['hardware'] = True
    
    # Verify EEPROM settings
    eeprom_info = get_eeprom_info(gripper.servos[0], config)
    print(f"  Current EEPROM values:")
    print(f"    Return delay time: {eeprom_info.get('return_delay_time', 'N/A')}")
    print(f"    Status return level: {eeprom_info.get('status_return_level', 'N/A')}")
    
    if verify_eeprom_settings(gripper.servos[0], config):
        print("  ✓ EEPROM settings verified and optimized")
    else:
        print("  ⚠ EEPROM settings verification failed")
    
    # Test 4: Health Monitor
    print("\n4. Testing Health Monitor")
    print("-"*70)
    
    health = HealthMonitor(gripper.servos[0], config)
    
    temp = health.read_temperature()
    current = health.read_current()
    voltage = health.read_voltage()
    position = health.read_position()
    
    print(f"✓ Health monitoring working")
    print(f"  Temperature: {temp}°C")
    print(f"  Current: {current} mA")
    print(f"  Voltage: {voltage} V")
    print(f"  Position: {position}")
    
    # Get full snapshot
    snapshot = health.get_health_snapshot()
    print(f"  Temperature trend: {snapshot['temperature_trend']}")
    print(f"  Temperature rate: {snapshot['temperature_rate']:.2f} °C/sec")
    test_results['health'] = True
    
    # Test 5: Error Handler
    print("\n5. Testing Error Handler")
    print("-"*70)
    
    error_code, description = check_hardware_error(gripper.servos[0], config)
    print(f"✓ Error detection working")
    print(f"  Error code: {error_code}")
    print(f"  Description: {description}")
    test_results['error'] = True
    
    if error_code != 0:
        print(f"  ⚠ Hardware error detected - would attempt reboot in production")
    
    # Test 6: Position Control with Config
    print("\n6. Testing Position Control")
    print("-"*70)
    
    current_pos = gripper.get_position()
    print(f"  Current position: {current_pos:.1f}%")
    
    print(f"  Setting max effort to 30% (movement current)...")
    gripper.set_max_effort(30)
    
    print("✓ Position control working with config")
    test_results['position'] = True
    
except FileNotFoundError:
    print(f"✗ Device {device} not found")
    print("  Run with device path as argument to test with hardware")
except Exception as e:
    print(f"✗ Hardware test failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("Test Summary")
print("="*70)

# Report actual results
if test_results['config']:
    print("✓ Configuration system: PASS")
else:
    print("✗ Configuration system: FAIL")

if test_results['wave']:
    print("✓ Wave-following controller: PASS")
else:
    print("✗ Wave-following controller: FAIL")

if test_results['hardware']:
    print("✓ Hardware connection: PASS")
    if test_results['health']:
        print("✓ Health monitoring: PASS")
    else:
        print("✗ Health monitoring: FAIL")
    
    if test_results['error']:
        print("✓ Error handling: PASS")
    else:
        print("✗ Error handling: FAIL")
    
    if test_results['position']:
        print("✓ Position control: PASS")
    else:
        print("✗ Position control: FAIL")
else:
    print("✗ Hardware connection: FAIL (device unavailable or busy)")
    print("  Health monitoring: SKIPPED")
    print("  Error handling: SKIPPED")
    print("  Position control: SKIPPED")

# Overall result
print("\n" + "="*70)
passed = sum(test_results.values())
total = len(test_results)

if test_results['hardware']:
    # All tests attempted
    if passed == total:
        print(f"OVERALL: PASS ({passed}/{total} tests passed)")
        sys.exit(0)
    else:
        print(f"OVERALL: FAIL ({passed}/{total} tests passed)")
        sys.exit(1)
else:
    # Hardware tests skipped
    software_tests = test_results['config'] and test_results['wave']
    if software_tests:
        print(f"OVERALL: PARTIAL ({passed}/{total} tests passed, hardware unavailable)")
        print("Software tests passed, but hardware tests could not run.")
        sys.exit(2)
    else:
        print(f"OVERALL: FAIL ({passed}/{total} tests passed)")
        sys.exit(1)

print("="*70)
