#!/usr/bin/env python3
"""
Corrected EZGripper DDS Driver

Key corrections:
1. Peak power reduction (50% torque cap) - NOT spring force elimination
2. Calibration on command interface - NOT automatic only
3. Minimal libezgripper integration - only used files
"""

import time
import math
import argparse
import logging
import sys
import os
import threading
import json
from queue import Queue, Empty
from dataclasses import dataclass

# Set CYCLONEDDS_HOME before importing cyclonedds
os.environ['CYCLONEDDS_HOME'] = '/opt/cyclonedds-0.10.2'

from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.sub import DataReader
from cyclonedds.pub import DataWriter
from cyclonedds.qos import Qos, Policy

# Import unitree_sdk2py message types (which work with cyclonedds 0.10.2)
sys.path.insert(0, '/home/kavi/CascadeProjects/unitree_sdk2_python')
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmd_, MotorCmds_, MotorState_, MotorStates_

# Minimal libezgripper imports - only what we use
from libezgripper import create_connection, Gripper
import serial.tools.list_ports


@dataclass
class GripperCommand:
    """Queued gripper command"""
    position_pct: float
    effort_pct: float
    timestamp: float
    q_radians: float
    tau: float


def discover_ezgripper_devices():
    """Auto-discover EZGripper devices by scanning USB ports"""
    devices = []
    ports = serial.tools.list_ports.comports()
    
    for port in ports:
        # Look for FTDI USB-to-serial adapters (common for EZGripper)
        if 'FTDI' in port.description or 'USB' in port.description:
            devices.append({
                'device': port.device,
                'serial': port.serial_number,
                'description': port.description
            })
    
    return devices


def verify_device_mapping(config):
    """Interactive verification of left/right device mapping"""
    import sys
    
    print("\n" + "="*60)
    print("EZGripper Device Mapping Verification")
    print("="*60)
    print(f"\nDiscovered devices:")
    print(f"  Left:  {config['left']} (serial: {config['left_serial']})")
    print(f"  Right: {config['right']} (serial: {config['right_serial']})")
    print("\nPlease verify this mapping is correct.")
    print("The 'left' gripper should be on the LEFT side of the robot.")
    print("The 'right' gripper should be on the RIGHT side of the robot.")
    
    while True:
        response = input("\nIs this mapping correct? [Y/n] ").strip().lower()
        if response in ['', 'y', 'yes']:
            print("\nMapping confirmed. Saving configuration...")
            return config
        elif response in ['n', 'no']:
            print("\nSwapping left/right mapping...")
            config['left'], config['right'] = config['right'], config['left']
            config['left_serial'], config['right_serial'] = config['right_serial'], config['left_serial']
            # Calibration offsets are stored by serial number, no need to swap
            print(f"\nNew mapping:")
            print(f"  Left:  {config['left']} (serial: {config['left_serial']})")
            print(f"  Right: {config['right']} (serial: {config['right_serial']})")
            print("\nSaving corrected configuration...")
            return config
        else:
            print("Please enter 'y' or 'n'")


def get_device_config():
    """Load device configuration from file or auto-discover"""
    config_file = '/tmp/ezgripper_device_config.json'
    
    # Try to load existing config
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"Failed to load config: {e}")
    
    # Auto-discover devices
    devices = discover_ezgripper_devices()
    
    if len(devices) >= 2:
        # Found at least 2 devices, create config
        config = {
            'left': devices[0]['device'],
            'right': devices[1]['device'],
            'left_serial': devices[0].get('serial', 'unknown'),
            'right_serial': devices[1].get('serial', 'unknown'),
            'calibration': {  # Calibration stored by serial number
                devices[0].get('serial', 'unknown'): 0.0,
                devices[1].get('serial', 'unknown'): 0.0
            }
        }
        
        # Verify mapping with user
        config = verify_device_mapping(config)
        
        # Save config
        try:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logging.info(f"Saved device config: {config_file}")
        except Exception as e:
            logging.warning(f"Failed to save config: {e}")
        
        return config
    
    elif len(devices) == 1:
        # Only one device found
        config = {
            'left': devices[0]['device'],
            'right': None,
            'left_serial': devices[0].get('serial', 'unknown'),
            'right_serial': None,
            'calibration': {
                devices[0].get('serial', 'unknown'): 0.0
            }
        }
        logging.warning(f"Only found 1 device: {devices[0]['device']}")
        return config
    
    else:
        logging.error("No EZGripper devices found!")
        return None


class CorrectedEZGripperDriver:
    """Corrected EZGripper DDS Driver with Command Queue"""
    
    def __init__(self, side: str, device: str = "/dev/ttyUSB0", domain: int = 0, 
                 calibration_file: str = None):
        self.side = side
        self.device = device
        self.domain = domain
        self.calibration_file = calibration_file or f"/tmp/ezgripper_{side}_calibration.txt"
        
        # Setup logging
        self.logger = logging.getLogger(f"ezgripper_{side}")
        
        # Hardware state
        self.gripper = None
        self.connection = None
        self.is_calibrated = False
        
        # Serial connection lock (prevents concurrent access)
        self.serial_lock = threading.Lock()
        
        # Control state
        self.current_position_pct = 50.0
        self.current_effort_pct = 30.0
        self.last_cmd_time = time.time()
        self.target_position_pct = 50.0
        
        # Command queue (1-deep - keeps latest, drops old)
        self.command_queue = Queue(maxsize=1)
        self.current_command = None
        
        # DDS state
        self.participant = None
        self.cmd_reader = None
        self.state_writer = None
        
        # Threading
        self.running = True
        self.status_thread = None
        self.status_update_interval = 0.5  # 2Hz status updates (reduced from 20Hz to reduce lock contention)
        
        # Initialize
        self._initialize_hardware()
        self._load_calibration()
        self._setup_dds()
        
        self.logger.info(f"Corrected EZGripper driver ready: {side} side")
    
    def _initialize_hardware(self):
        """Initialize hardware connection"""
        self.logger.info(f"Connecting to EZGripper on {self.device}")
        
        try:
            self.connection = create_connection(dev_name=self.device, baudrate=57600)
            self.gripper = Gripper(self.connection, f'corrected_{self.side}', [1])
            
            # Test connection
            test_pos = self.gripper.get_position()
            self.logger.info(f"Hardware connected: position {test_pos:.1f}%")
            
        except Exception as e:
            self.logger.error(f"Hardware connection failed: {e}")
            raise
    
    def _load_calibration(self):
        """Load calibration offset from device config using serial number"""
        config_file = '/tmp/ezgripper_device_config.json'
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                
                # Get serial number for this side
                serial_key = f"{self.side}_serial"
                if serial_key in config and config[serial_key] != 'unknown':
                    serial = config[serial_key]
                    
                    # Get calibration offset for this serial number
                    if 'calibration' in config and serial in config['calibration']:
                        self.calibration_offset = config['calibration'][serial]
                        self.gripper.zero_positions[0] = self.calibration_offset
                        self.is_calibrated = True
                        self.logger.info(f"Loaded calibration offset for {serial}: {self.calibration_offset}")
                        return
        except Exception as e:
            self.logger.warning(f"Failed to load calibration: {e}")
        
        # No calibration found
        self.calibration_offset = 0.0
        self.gripper.zero_positions[0] = self.calibration_offset
        self.logger.info("No calibration found, using default offset")
    
    def save_calibration(self, offset: float):
        """Save calibration offset to device config using serial number"""
        config_file = '/tmp/ezgripper_device_config.json'
        
        try:
            # Load existing config
            config = {}
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
            
            # Get serial number for this side
            serial_key = f"{self.side}_serial"
            if serial_key in config and config[serial_key] != 'unknown':
                serial = config[serial_key]
                
                # Initialize calibration dict if needed
                if 'calibration' not in config:
                    config['calibration'] = {}
                
                # Save offset for this serial number
                config['calibration'][serial] = offset
                
                # Write back
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)
                
                self.logger.info(f"Saved calibration offset for {serial}: {offset}")
            else:
                self.logger.error(f"Cannot save calibration - no serial number for {self.side}")
            
        except Exception as e:
            self.logger.error(f"Failed to save calibration: {e}")
    
    def _setup_dds(self):
        """Setup DDS interfaces"""
        self.logger.info("Setting up DDS interfaces...")
        
        self.participant = DomainParticipant(self.domain)
        
        # Dex1 topics
        cmd_topic_name = f"rt/dex1/{self.side}/cmd"
        state_topic_name = f"rt/dex1/{self.side}/state"
        
        # Create topics
        self.cmd_topic = Topic(self.participant, cmd_topic_name, MotorCmds_)
        self.state_topic = Topic(self.participant, state_topic_name, MotorStates_)
        
        # Create reader/writer
        self.cmd_reader = DataReader(self.participant, self.cmd_topic)
        self.state_writer = DataWriter(self.participant, self.state_topic)
        
        self.logger.info(f"DDS ready: {cmd_topic_name} → {state_topic_name}")
    
    def calibrate(self):
        """Calibration on command - can be called by robot when needed"""
        self.logger.info("Starting calibration on command...")
        
        try:
            # Move to relaxed position
            self.gripper.goto_position(50.0, 30.0)
            time.sleep(2)
            
            # Perform calibration
            self.gripper.calibrate()
            
            # Save calibration offset to file
            self._save_calibration()
            
            # Verify with quick test
            self.gripper.goto_position(25.0, 40.0)
            time.sleep(2)
            actual = self.gripper.get_position()
            error = abs(actual - 25.0)
            
            if error <= 10.0:
                self.is_calibrated = True
                self.logger.info(f"✅ Calibration successful (error: {error:.1f}%)")
                return True
            else:
                self.logger.warning(f"⚠️ Calibration issue (error: {error:.1f}%)")
                return False
                
        except Exception as e:
            self.logger.error(f"Calibration failed: {e}")
            return False
    
    def dex1_to_ezgripper(self, q_radians: float) -> float:
        """Convert Dex1 position to EZGripper position"""
        if q_radians <= 0.1:
            return 0.0    # Close
        elif q_radians >= 6.0:
            return 100.0  # Open
        else:
            return (q_radians / (2.0 * math.pi)) * 100.0
    
    def ezgripper_to_dex1(self, position_pct: float) -> float:
        """Convert EZGripper position to Dex1 position"""
        return (position_pct / 100.0) * 2.0 * math.pi
    
    def tau_to_effort_pct(self, tau: float) -> float:
        """
        Convert Dex1 torque to gripper effort
        
        KEY: Cap at 50% to reduce peak power consumption
        This is NOT about spring force - it's about power management
        
        FIXED for preliminary XR Teleoperate compatibility: always use 50% effort
        """
        # Fixed 50% effort for preliminary XR Teleoperate configuration
        return 50.0
    
    def get_appropriate_effort(self, position_pct: float) -> float:
        """Get appropriate effort for different positions"""
        if position_pct <= 5.0 or position_pct >= 95.0:
            return 40.0  # Lower effort at extremes
        else:
            return 50.0  # Standard effort (peak power limited)
    
    def receive_commands(self):
        """Receive and queue incoming DDS commands (non-blocking)"""
        try:
            samples = self.cmd_reader.take(N=10)  # Take up to 10 samples
            
            if samples:
                self.logger.debug(f"Received {len(samples)} samples")
                
                # Keep only the latest command (1-deep queue)
                latest_sample = samples[-1]  # Last sample is most recent
                
                if latest_sample and hasattr(latest_sample, 'cmds') and latest_sample.cmds and len(latest_sample.cmds) > 0:
                    motor_cmd = latest_sample.cmds[0]
                    
                    # Convert Dex1 command to gripper parameters
                    target_position = self.dex1_to_ezgripper(motor_cmd.q)
                    requested_effort = self.tau_to_effort_pct(motor_cmd.tau)
                    actual_effort = min(requested_effort, self.get_appropriate_effort(target_position))
                    
                    # Create command object
                    cmd = GripperCommand(
                        position_pct=target_position,
                        effort_pct=actual_effort,
                        timestamp=time.time(),
                        q_radians=motor_cmd.q,
                        tau=motor_cmd.tau
                    )
                    
                    # Put in queue (will drop old command if queue is full)
                    try:
                        self.command_queue.put_nowait(cmd)
                        self.logger.debug(f"Queued command: position={target_position:.1f}%")
                    except:
                        # Queue was full, old command will be replaced
                        self.command_queue.get_nowait()  # Remove old
                        self.command_queue.put_nowait(cmd)  # Add new
                        self.logger.debug(f"Replaced old command with new: position={target_position:.1f}%")
        
        except Exception as e:
            self.logger.error(f"Command receive failed: {e}")
    
    def execute_command(self):
        """Execute latest queued command immediately (servo handles command replacement)"""
        try:
            cmd = self.command_queue.get_nowait()
            self.current_command = cmd
            
            # Execute command with lock to protect serial connection
            with self.serial_lock:
                self.gripper.goto_position(cmd.position_pct, cmd.effort_pct)
            
            # Update state
            self.target_position_pct = cmd.position_pct
            self.current_position_pct = cmd.position_pct
            self.current_effort_pct = cmd.effort_pct
            
            # Log command
            if cmd.q_radians <= 0.1:
                mode = "CLOSE"
            elif cmd.q_radians >= 6.0:
                mode = "OPEN"
            else:
                mode = f"POSITION {cmd.position_pct:.1f}%"
            
            self.logger.info(f"Executing: {mode} (q={cmd.q_radians:.3f}, tau={cmd.tau:.3f})")
            
        except Empty:
            # No command in queue
            pass
        except Exception as e:
            self.logger.error(f"Command execution failed: {e}")
    
    def publish_state_async(self):
        """Publish current gripper state (non-blocking, runs in separate thread)"""
        while self.running:
            try:
                # Get actual position from hardware with lock to protect serial connection
                with self.serial_lock:
                    actual_position = self.gripper.get_position()
                
                # Convert to Dex1 units
                current_q = self.ezgripper_to_dex1(actual_position)
                current_tau = self.current_effort_pct / 10.0
                
                # Create motor state
                motor_state = MotorState_(
                    mode=0,
                    q=current_q,
                    dq=0.0,
                    ddq=0.0,
                    tau_est=current_tau,
                    q_raw=current_q,
                    dq_raw=0.0,
                    ddq_raw=0.0,
                    temperature=25,
                    lost=0,
                    reserve=[0, 0]
                )
                
                motor_states = MotorStates_(states=[motor_state])
                
                # Publish state
                self.state_writer.write(motor_states)
                
            except Exception as e:
                self.logger.error(f"State publish failed: {e}")
            
            # Sleep for status update interval
            time.sleep(self.status_update_interval)
    
    def run(self):
        """Main control loop"""
        self.logger.info("Starting corrected EZGripper driver...")
        
        # Start async status publishing thread
        self.status_thread = threading.Thread(target=self.publish_state_async, daemon=True)
        self.status_thread.start()
        
        try:
            while self.running:
                # Receive and queue commands (non-blocking)
                self.receive_commands()
                
                # Execute queued command with rate limiting
                self.execute_command()
                
                # Small sleep to prevent CPU spinning
                time.sleep(0.01)  # 100Hz loop
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down corrected EZGripper driver...")
        except Exception as e:
            self.logger.error(f"Driver error: {e}")
        finally:
            self.running = False
            if self.status_thread:
                self.status_thread.join(timeout=1.0)
    
    def shutdown(self):
        """Clean shutdown"""
        self.logger.info("Shutting down hardware...")
        self.running = False
        if self.gripper:
            self.gripper.goto_position(50.0, 30.0)
            time.sleep(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Corrected EZGripper DDS Driver")
    parser.add_argument("--side", required=True, choices=["left", "right"],
                       help="Gripper side (left/right)")
    parser.add_argument("--dev", default=None,
                       help="EZGripper device path (auto-discover if not specified)")
    parser.add_argument("--domain", type=int, default=0,
                       help="DDS domain")
    parser.add_argument("--calibrate", action="store_true",
                       help="Calibrate on startup")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get device path
    if args.dev:
        device = args.dev
    else:
        # Auto-discover device
        config = get_device_config()
        if config is None:
            logging.error("Failed to auto-discover devices. Please specify --dev manually.")
            sys.exit(1)
        
        device = config.get(args.side)
        if device is None:
            logging.error(f"No device configured for {args.side} side. Please specify --dev manually.")
            sys.exit(1)
        
        logging.info(f"Auto-discovered device for {args.side}: {device}")
    
    # Create and run driver
    driver = CorrectedEZGripperDriver(
        side=args.side,
        device=device,
        domain=args.domain
    )
    
    # Calibrate if requested
    if args.calibrate:
        driver.calibrate()
    
    try:
        driver.run()
    except KeyboardInterrupt:
        pass
    finally:
        driver.shutdown()


if __name__ == "__main__":
    main()
