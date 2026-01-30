#!/usr/bin/env python3
"""Check what servo model we have"""

from libezgripper.config import load_config
from libezgripper import create_connection
from libezgripper.lib_robotis import Robotis_Servo
import time

config = load_config()
print("Checking servo model...")

try:
    conn = create_connection('/dev/ttyUSB0', config.comm_baudrate)
    servo = Robotis_Servo(conn, 1)
    
    # Read model number (address 0, 4 bytes)
    model_data = servo.read_address(0, 4)
    model_bytes = list(model_data)
    
    # Convert to model number
    model_number = (model_bytes[3] << 24) | (model_bytes[2] << 16) | (model_bytes[1] << 8) | model_bytes[0]
    
    print(f"Model bytes: {model_bytes}")
    print(f"Model number: {model_number}")
    
    # Common MX model numbers
    models = {
        30: "MX-28",
        31: "MX-28(2.0)",
        32: "MX-64",
        33: "MX-64(2.0)",
        34: "MX-106",
        35: "MX-106(2.0)"
    }
    
    if model_number in models:
        print(f"Servo model: {models[model_number]}")
    else:
        print(f"Unknown model number: {model_number}")
    
    # Read firmware version (address 6)
    fw_version = servo.read_word(6)
    print(f"Firmware version: {fw_version}")
    
    # Read protocol type (address 13)
    protocol = servo.read_word(13)
    print(f"Protocol type: {protocol} (0=Protocol 1.0, 1=Protocol 2.0)")
    
    # Read the ID
    servo_id = servo.read_word(7)
    print(f"Servo ID: {servo_id}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
