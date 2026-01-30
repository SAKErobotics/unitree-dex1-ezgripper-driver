#!/usr/bin/env python3
"""
Test both left and right sides
Check if USB adapter or wiring is the issue
"""

import serial
import time
import sys

def test_usb_device(device, name):
    """Test if USB device is working"""
    print(f"\n--- Testing {name}: {device} ---")
    
    try:
        # Test if we can open the port
        ser = serial.Serial(device, 1000000, timeout=0.1)
        print(f"✓ Port opened successfully")
        
        # Test if we can write and read (loopback test)
        ser.write(b'TEST')
        time.sleep(0.01)
        
        # Check for any data
        waiting = ser.in_waiting
        print(f"  Bytes waiting: {waiting}")
        
        if waiting > 0:
            data = ser.read(waiting)
            print(f"  Data: {data.hex()}")
        
        ser.close()
        return True
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

def test_servo_direct(device, side):
    """Try to communicate with servo directly"""
    print(f"\n--- Testing {side} servo on {device} ---")
    
    try:
        from libezgripper.config import load_config
        from libezgripper import create_connection
        
        config = load_config()
        print(f"  Config: servo_id={config.comm_servo_id}, baud={config.comm_baudrate}")
        
        # Try to create connection
        connection = create_connection(dev_name=device, baudrate=config.comm_baudrate)
        print(f"  ✓ Connection created")
        
        # Try to read directly from servo
        from libezgripper.lib_robotis import Robotis_Servo
        servo = Robotis_Servo(connection, config.comm_servo_id)
        
        # Try to read ID register
        try:
            servo_id = servo.read_word(3)  # Device ID register
            print(f"  Servo ID: {servo_id}")
            
            if servo_id == config.comm_servo_id:
                print(f"  ✓ Correct servo ID {servo_id}")
                
                # Try reading position
                pos = servo.read_word_signed(config.reg_present_position)
                print(f"  Position: {pos}")
                
                # Try reading torque status
                torque = servo.read_word(config.reg_torque_enable)
                print(f"  Torque: {torque}")
                
                return True
            else:
                print(f"  ✗ Wrong servo ID: expected {config.comm_servo_id}, got {servo_id}")
                
        except Exception as e:
            print(f"  ✗ Servo communication failed: {e}")
        
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
    
    return False

def check_dds_domains():
    """Check what DDS domains are active"""
    print("\n--- Checking DDS domains ---")
    
    try:
        # Try to subscribe to both left and right topics
        from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
        from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorStates_
        
        for domain in [0, 1, 2]:
            print(f"\n  Domain {domain}:")
            ChannelFactoryInitialize(domain)
            
            for side in ['left', 'right']:
                topic = f"rt/dex1/{side}/state"
                try:
                    sub = ChannelSubscriber(topic, MotorStates_)
                    sub.Init()
                    
                    # Try to read once
                    msg = sub.Read()
                    if msg:
                        print(f"    {side}: ✓ Receiving data")
                    else:
                        print(f"    {side}: No data (but topic accessible)")
                        
                except Exception as e:
                    print(f"    {side}: ✗ {e}")
                    
    except ImportError:
        print("  DDS libraries not available")
    except Exception as e:
        print(f"  DDS check failed: {e}")

def main():
    print("="*70)
    print("  BOTH SIDES DIAGNOSTIC")
    print("="*70)
    
    # Check all USB serial devices
    print("\n1. Checking USB devices:")
    import serial.tools.list_ports
    ports = serial.tools.list_ports.comports()
    
    if not ports:
        print("  ✗ No USB serial devices found")
        return
    
    for p in ports:
        print(f"  Found: {p.device} - {p.description}")
        test_usb_device(p.device, p.device)
    
    # Test each device with servo
    print("\n2. Testing servo communication:")
    for p in ports:
        if 'USB' in p.device:
            side = 'left' if '0' in p.device else 'right'
            test_servo_direct(p.device, side)
    
    # Check DDS
    print("\n3. Checking DDS:")
    check_dds_domains()
    
    print("\n" + "="*70)
    print("  DIAGNOSTIC COMPLETE")
    print("="*70)

if __name__ == '__main__':
    main()
