#!/usr/bin/env python3
"""Debug calibration step by step to see where it fails"""

from libezgripper.config import load_config
from libezgripper import create_connection
from libezgripper.lib_robotis import Robotis_Servo
import time

config = load_config()
print("Debugging calibration step by step...")
print(f"Calibration current: {config.calibration_current}")
print(f"Calibration position: {config.calibration_position}")

try:
    conn = create_connection('/dev/ttyUSB0', config.comm_baudrate)
    servo = Robotis_Servo(conn, 1)
    
    # Step 1: Read initial state
    print("\n=== Step 1: Initial State ===")
    pos = servo.read_word_signed(config.reg_present_position)
    temp = servo.read_word(config.reg_present_temperature)
    voltage = servo.read_word(config.reg_present_voltage) / 10.0
    current = servo.read_word_signed(config.reg_present_current)
    error = servo.read_word(config.reg_hardware_error)
    torque = servo.read_word(config.reg_torque_enable)
    mode = servo.read_word(config.reg_operating_mode)
    current_limit = servo.read_word(config.reg_current_limit)
    
    print(f"  Position: {pos}")
    print(f"  Temperature: {temp}°C")
    print(f"  Voltage: {voltage}V")
    print(f"  Current: {current}")
    print(f"  Error: {error}")
    print(f"  Torque: {torque}")
    print(f"  Mode: {mode}")
    print(f"  Current Limit: {current_limit}")
    
    # Step 2: Disable torque
    print("\n=== Step 2: Disable Torque ===")
    try:
        servo.write_word(config.reg_torque_enable, 0)
        time.sleep(0.1)
        torque = servo.read_word(config.reg_torque_enable)
        print(f"  Torque after disable: {torque}")
    except Exception as e:
        print(f"  Error disabling torque: {e}")
    
    # Step 3: Set operating mode to 4 (Extended Position Control)
    print("\n=== Step 3: Set Operating Mode ===")
    try:
        print(f"  Setting mode to 4...")
        servo.write_word(config.reg_operating_mode, 4)
        time.sleep(0.1)
        mode = servo.read_word(config.reg_operating_mode)
        print(f"  Mode after setting: {mode}")
    except Exception as e:
        print(f"  Error setting mode: {e}")
    
    # Step 4: Set current limit
    print("\n=== Step 4: Set Current Limit ===")
    try:
        print(f"  Setting current limit to {config.calibration_current}...")
        servo.write_word(config.reg_current_limit, config.calibration_current)
        time.sleep(0.1)
        current_limit = servo.read_word(config.reg_current_limit)
        print(f"  Current limit after setting: {current_limit}")
    except Exception as e:
        print(f"  Error setting current limit: {e}")
    
    # Step 5: Try to set goal current (this is where it fails)
    print("\n=== Step 5: Set Goal Current ===")
    test_currents = [100, 200, 300, 400, 500, 600]
    
    for test_current in test_currents:
        try:
            print(f"  Trying goal current = {test_current}...")
            servo.write_word(config.reg_goal_current, test_current)
            time.sleep(0.1)
            
            # Read back to verify
            actual_current = servo.read_word_signed(config.reg_present_current)
            print(f"    Present current: {actual_current}")
            print(f"    ✓ Success!")
            break
            
        except Exception as e:
            print(f"    ✗ Failed: {e}")
    
    # Step 6: Re-enable torque
    print("\n=== Step 6: Re-enable Torque ===")
    try:
        servo.write_word(config.reg_torque_enable, 1)
        time.sleep(0.5)
        torque = servo.read_word(config.reg_torque_enable)
        print(f"  Torque after enable: {torque}")
    except Exception as e:
        print(f"  Error enabling torque: {e}")
    
    # Step 7: Try to move to calibration position
    print("\n=== Step 7: Move to Calibration Position ===")
    try:
        print(f"  Moving to position {config.calibration_position}...")
        servo.write_word(config.reg_goal_position, config.calibration_position)
        
        # Monitor movement
        for i in range(5):
            time.sleep(0.5)
            pos = servo.read_word_signed(config.reg_present_position)
            current = servo.read_word_signed(config.reg_present_current)
            print(f"    t={i*0.5:.1f}s: pos={pos}, current={current}")
            
    except Exception as e:
        print(f"  Error moving: {e}")
    
    print("\n=== Final State ===")
    pos = servo.read_word_signed(config.reg_present_position)
    current = servo.read_word_signed(config.reg_present_current)
    error = servo.read_word(config.reg_hardware_error)
    print(f"  Position: {pos}")
    print(f"  Current: {current}")
    print(f"  Error: {error}")
    
except Exception as e:
    print(f"Fatal error: {e}")
    import traceback
    traceback.print_exc()
