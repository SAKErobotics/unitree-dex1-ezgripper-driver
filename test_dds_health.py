#!/usr/bin/env python3
"""
DDS Health Monitor for EZGripper

Monitors servo health status to diagnose errors.
"""

import sys
import time
import threading
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize

sys.path.insert(0, '/home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver')

from libezgripper.config import load_config
from libezgripper import create_connection, Gripper
from libezgripper.health_monitor import HealthMonitor

class DDSHealthMonitor:
    def __init__(self, side='left', domain=0):
        self.side = side
        self.domain = domain
        
        # Initialize DDS factory
        ChannelFactoryInitialize(domain)
        
        # Subscribe to state
        state_topic_name = f"rt/dex1/{side}/state"
        self.state_subscriber = ChannelSubscriber(state_topic_name, MotorStates_)
        self.state_subscriber.Init()
        
        # State tracking
        self.current_state = None
        self.state_lock = threading.Lock()
        
        # Start state listener
        self.running = True
        self.state_thread = threading.Thread(target=self._state_listener)
        self.state_thread.daemon = True
        self.state_thread.start()
        
        print(f"DDS Health Monitor initialized for {side} gripper")
        print(f"State topic: {state_topic_name}")
    
    def _state_listener(self):
        """Listen for state messages"""
        while self.running:
            try:
                state = self.state_subscriber.Read()
                if state is not None:
                    with self.state_lock:
                        self.current_state = state
                    if state.states:
                        pos = state.states[0].q
                        torque = state.states[0].tau_est
                        print(f"  DDS State: pos={pos:.3f}rad, torque={torque:.3f}Nm")
            except Exception as e:
                print(f"  DDS read error: {e}")
            time.sleep(0.002)
    
    def cleanup(self):
        """Clean up DDS resources"""
        self.running = False
        if self.state_thread.is_alive():
            self.state_thread.join(timeout=1.0)

def check_servo_health(device='/dev/ttyUSB0'):
    """Check servo health directly"""
    print("\n" + "="*70)
    print("  DIRECT SERVO HEALTH CHECK")
    print("="*70)
    
    try:
        config = load_config()
        connection = create_connection(dev_name=device, baudrate=config.comm_baudrate)
        gripper = Gripper(connection, 'health_check', [config.comm_servo_id], config)
        
        print(f"\n✓ Connected to servo ID {config.comm_servo_id}")
        
        # Check basic registers
        print("\nChecking servo status:")
        
        # Read present position
        try:
            pos = gripper.servos[0].read_word_signed(config.reg_present_position)
            print(f"  Present Position: {pos}")
        except Exception as e:
            print(f"  ✗ Position read failed: {e}")
        
        # Read hardware error
        try:
            error = gripper.servos[0].read_word(70)  # Hardware error register
            print(f"  Hardware Error: {error}")
            if error != 0:
                print(f"    Error details:")
                if error & 0x01: print("      - Input Voltage Error")
                if error & 0x02: print("      - Overheating Error")
                if error & 0x04: print("      - Motor Encoder Error")
                if error & 0x08: print("      - Circuit Error")
                if error & 0x10: print("      - Overload Error")
                if error & 0x20: print("      - Goal Position Error")
                if error & 0x40: print("      - Checksum Error")
        except Exception as e:
            print(f"  ✗ Error register read failed: {e}")
        
        # Read present current
        try:
            current = gripper.servos[0].read_word_signed(102)  # Present current
            print(f"  Present Current: {current} mA")
        except Exception as e:
            print(f"  ✗ Current read failed: {e}")
        
        # Read temperature
        try:
            temp = gripper.servos[0].read_word(146)  # Present temperature
            print(f"  Temperature: {temp}°C")
        except Exception as e:
            print(f"  ✗ Temperature read failed: {e}")
        
        # Read torque enable status
        try:
            torque = gripper.servos[0].read_word(config.reg_torque_enable)
            print(f"  Torque Enable: {torque} (0=disabled, 1=enabled)")
        except Exception as e:
            print(f"  ✗ Torque status read failed: {e}")
        
        # Read operating mode
        try:
            mode = gripper.servos[0].read_word(config.reg_operating_mode)
            print(f"  Operating Mode: {mode} (3=Position, 4=Extended Position)")
        except Exception as e:
            print(f"  ✗ Operating mode read failed: {e}")
        
        # Test basic movement
        print("\nTesting basic movement:")
        try:
            print("  Enabling torque...")
            gripper.servos[0].write_address(config.reg_torque_enable, [1])
            time.sleep(0.1)
            
            print("  Moving to position 1000...")
            gripper.servos[0].write_word(config.reg_goal_position, 1000)
            time.sleep(1.0)
            
            new_pos = gripper.servos[0].read_word_signed(config.reg_present_position)
            print(f"  New position: {new_pos}")
            
            if abs(new_pos - 1000) < 100:
                print("  ✓ Movement successful")
            else:
                print("  ✗ Movement failed - servo not responding")
                
        except Exception as e:
            print(f"  ✗ Movement test failed: {e}")
        
        return gripper
        
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return None

def main():
    side = sys.argv[1] if len(sys.argv) > 1 else 'left'
    domain = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    device = sys.argv[3] if len(sys.argv) > 3 else '/dev/ttyUSB0'
    
    print("="*70)
    print("  EZGRIPPER DDS HEALTH MONITOR")
    print("="*70)
    print(f"\nSide: {side}")
    print(f"DDS Domain: {domain}")
    print(f"Device: {device}")
    
    # First check servo health directly
    gripper = check_servo_health(device)
    
    if gripper is None:
        print("\n✗ Cannot connect to servo - check device and power")
        return
    
    # Then monitor DDS state
    print("\n" + "="*70)
    print("  DDS STATE MONITOR")
    print("="*70)
    
    try:
        # Import DDS types
        from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorStates_
        
        # Create DDS monitor
        monitor = DDSHealthMonitor(side, domain)
        
        print("\nMonitoring DDS state for 10 seconds...")
        print("(Make sure ezgripper_dds_driver is running)")
        
        time.sleep(10)
        
        print("\n✓ Health monitoring complete")
        
    except ImportError:
        print("✗ DDS libraries not available")
    except Exception as e:
        print(f"✗ DDS monitoring failed: {e}")
    finally:
        if 'monitor' in locals():
            monitor.cleanup()

if __name__ == '__main__':
    main()
