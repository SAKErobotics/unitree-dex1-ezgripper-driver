#!/usr/bin/env python3
"""Simple test: just enable torque and move"""

from libezgripper.config import load_config
from libezgripper import create_connection
from libezgripper.lib_robotis import Robotis_Servo
import time

config = load_config()
print("Simple movement test...")

try:
    conn = create_connection('/dev/ttyUSB0', config.comm_baudrate)
    servo = Robotis_Servo(conn, 1)
    
    # Read initial state
    raw_pos = servo.read_word_signed(config.reg_present_position)
    torque = servo.read_word(config.reg_torque_enable)
    current = servo.read_word_signed(config.reg_present_current)
    
    print(f"Initial: pos={raw_pos}, torque={torque}, current={current}")
    
    # Enable torque
    print("Enabling torque...")
    servo.write_word(config.reg_torque_enable, 1)
    time.sleep(0.5)
    
    # Verify torque is on
    torque = servo.read_word(config.reg_torque_enable)
    print(f"Torque after enable: {torque}")
    
    # Try to move +100 units
    print("Moving +100 units...")
    servo.write_word(config.reg_goal_position, raw_pos + 100)
    time.sleep(1)
    
    # Check result
    new_pos = servo.read_word_signed(config.reg_present_position)
    new_current = servo.read_word_signed(config.reg_present_current)
    movement = new_pos - raw_pos
    
    print(f"After +100: pos={new_pos}, movement={movement}, current={new_current}")
    
    # Try to move -100 units
    print("Moving -100 units...")
    servo.write_word(config.reg_goal_position, raw_pos - 100)
    time.sleep(1)
    
    # Check result
    new_pos2 = servo.read_word_signed(config.reg_present_position)
    new_current2 = servo.read_word_signed(config.reg_present_current)
    movement2 = new_pos2 - raw_pos
    
    print(f"After -100: pos={new_pos2}, movement={movement2}, current={new_current2}")
    
    if abs(movement) > 5 or abs(movement2) > 5:
        print("✓ Servo moved!")
    else:
        print("✗ Servo didn't move significantly")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
