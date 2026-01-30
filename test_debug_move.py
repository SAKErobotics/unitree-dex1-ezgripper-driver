#!/usr/bin/env python3
"""Debug why servo isn't moving"""

from libezgripper.config import load_config
from libezgripper import create_connection
from libezgripper.lib_robotis import Robotis_Servo
import time

config = load_config()
print("Debugging servo movement...")

try:
    conn = create_connection('/dev/ttyUSB0', config.comm_baudrate)
    servo = Robotis_Servo(conn, 1)
    
    # Check torque status
    torque = servo.read_word(config.reg_torque_enable)
    print(f"Torque enabled: {torque}")
    
    # Check current limit
    current_limit = servo.read_word(config.reg_current_limit)
    print(f"Current limit: {current_limit}")
    
    # Check present current
    present_current = servo.read_word_signed(config.reg_present_current)
    print(f"Present current: {present_current}")
    
    # Check operating mode
    operating_mode = servo.read_word(config.reg_operating_mode)
    print(f"Operating mode: {operating_mode}")
    
    # Read initial position
    raw_pos = servo.read_word_signed(config.reg_present_position)
    print(f"Initial position: {raw_pos}")
    
    # Enable torque if not enabled
    if torque != 1:
        print("Enabling torque...")
        servo.write_word(config.reg_torque_enable, 1)
        time.sleep(0.5)
    
    # Set a higher current limit for testing
    print("Setting current limit to 1000...")
    servo.write_word(config.reg_current_limit, 1000)
    time.sleep(0.5)
    
    # Try to move with monitoring
    print("\nTrying to move +500 units...")
    servo.write_word(config.reg_goal_position, raw_pos + 500)
    
    # Monitor for 2 seconds
    for i in range(20):
        time.sleep(0.1)
        try:
            new_pos = servo.read_word_signed(config.reg_present_position)
            current = servo.read_word_signed(config.reg_present_current)
            movement = new_pos - raw_pos
            print(f"  t={i*0.1:.1f}s: pos={new_pos}, movement={movement}, current={current}")
        except Exception as e:
            print(f"  Error reading: {e}")
    
    print("\nFinal check...")
    final_pos = servo.read_word_signed(config.reg_present_position)
    final_current = servo.read_word_signed(config.reg_present_current)
    print(f"Final position: {final_pos} (moved {final_pos - raw_pos})")
    print(f"Final current: {final_current}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
