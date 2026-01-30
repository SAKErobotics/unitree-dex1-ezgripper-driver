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
    
    # Read model number (first 4 bytes from address 0)
    model_bytes = []
    for i in range(4):
        byte_val = servo.read_byte(i)
        model_bytes.append(byte_val)
    
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
    
    # Read firmware version
    fw_version = servo.read_byte(6)
    print(f"Firmware version: {fw_version}")
    
    # Read protocol type
    protocol = servo.read_byte(13)
    print(f"Protocol type: {protocol} (0=Protocol 1.0, 1=Protocol 2.0)")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
