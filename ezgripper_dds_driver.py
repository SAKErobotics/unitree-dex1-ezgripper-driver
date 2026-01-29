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
import json
import threading
from dataclasses import dataclass

# CycloneDDS will auto-detect library location
# os.environ['CYCLONEDDS_HOME'] = '/usr/lib/x86_64-linux-gnu'

from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.sub import DataReader
from cyclonedds.pub import DataWriter
from cyclonedds.qos import Qos, Policy

# Import unitree_sdk2py message types for Dex1 hand
sys.path.insert(0, '/home/kavi/CascadeProjects/unitree_sdk2_python')
from unitree_sdk2py.idl.default import HGHandCmd_, HGMotorCmd_, HGHandState_, HGMotorState_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import IMUState_, PressSensorState_

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
        
        # Control state
        self.current_position_pct = 50.0
        self.current_effort_pct = 30.0
        self.last_effort_pct = None  # Track last effort to avoid redundant set_max_effort calls
        self.last_cmd_time = time.time()
        self.target_position_pct = 50.0
        
        # Predictive state for 200 Hz publishing
        self.predicted_position_pct = 50.0  # Predicted position (published at 200 Hz)
        self.actual_position_pct = 50.0     # Last known actual position (read at 5 Hz)
        self.commanded_position_pct = 50.0  # Latest commanded position
        self.movement_speed = 952.43        # Measured gripper speed (%/sec)
        self.last_predict_time = time.time()
        
        # Monitoring for verification
        self.state_publish_count = 0
        self.last_monitor_time = time.time()
        self.monitor_interval = 5.0  # Report every 5 seconds
        
        # Latest command (thread-safe)
        self.latest_command = None
        self.command_count = 0
        self.control_loop_rate = 30.0  # Control thread at 30 Hz (limited by serial)
        self.state_loop_rate = 200.0   # State thread at 200 Hz (predictive)
        
        # Thread control
        self.running = True
        self.state_lock = threading.Lock()  # Protects shared state variables
        self.control_thread = None
        self.state_thread = None
        
        # Initialize
        self._initialize_hardware()
        self._load_calibration()
        self._setup_dds()
        
        # Auto-calibrate at startup
        self.logger.info("Running automatic calibration at startup...")
        self.calibrate()
        
        self.logger.info(f"Corrected EZGripper driver ready: {side} side")
    
    def _initialize_hardware(self):
        """Initialize hardware connection and detect serial number"""
        self.logger.info(f"Connecting to EZGripper on {self.device}")
        
        try:
            self.connection = create_connection(dev_name=self.device, baudrate=57600)
            self.gripper = Gripper(self.connection, f'corrected_{self.side}', [1])
            
            # Test connection
            test_pos = self.gripper.get_position()
            self.logger.info(f"Hardware connected: position {test_pos:.1f}%")
            
            # Read serial number from hardware
            self.serial_number = self._get_serial_number()
            self.logger.info(f"Detected serial number: {self.serial_number}")
            
            # Update device config with current device mapping
            self._update_device_config()
            
        except Exception as e:
            self.logger.error(f"Hardware connection failed: {e}")
            raise
    
    def _get_serial_number(self):
        """Get serial number from connected device"""
        try:
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            for port in ports:
                if port.device == self.device:
                    return port.serial_number if port.serial_number else 'unknown'
            return 'unknown'
        except Exception as e:
            self.logger.warning(f"Failed to read serial number: {e}")
            return 'unknown'
    
    def _update_device_config(self):
        """Update device config with current device and serial number mapping"""
        config_file = '/tmp/ezgripper_device_config.json'
        
        try:
            # Load existing config
            config = {}
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
            
            # Update device and serial mapping for this side
            config[self.side] = self.device
            config[f"{self.side}_serial"] = self.serial_number
            
            # Initialize calibration dict if needed
            if 'calibration' not in config:
                config['calibration'] = {}
            
            # Write back
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            self.logger.info(f"Updated device config: {self.side} -> {self.device} (serial: {self.serial_number})")
            
        except Exception as e:
            self.logger.warning(f"Failed to update device config: {e}")
    
    def _load_calibration(self):
        """Load calibration offset from device config using serial number from hardware"""
        config_file = '/tmp/ezgripper_device_config.json'
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                
                # Use serial number read from hardware (not from config)
                if self.serial_number and self.serial_number != 'unknown':
                    # Get calibration offset for this serial number
                    if 'calibration' in config and self.serial_number in config['calibration']:
                        self.calibration_offset = config['calibration'][self.serial_number]
                        self.gripper.zero_positions[0] = self.calibration_offset
                        self.is_calibrated = True
                        self.logger.info(f"Loaded calibration offset for {self.serial_number}: {self.calibration_offset}")
                        return
        except Exception as e:
            self.logger.warning(f"Failed to load calibration: {e}")
        
        # No calibration found - auto-calibrate
        self.logger.info("No calibration found, running auto-calibration...")
        self.calibrate()
    
    def save_calibration(self, offset: float):
        """Save calibration offset to device config using serial number from hardware"""
        config_file = '/tmp/ezgripper_device_config.json'
        
        try:
            # Load existing config
            config = {}
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
            
            # Use serial number read from hardware
            if self.serial_number and self.serial_number != 'unknown':
                # Initialize calibration dict if needed
                if 'calibration' not in config:
                    config['calibration'] = {}
                
                # Save offset for this serial number
                config['calibration'][self.serial_number] = offset
                
                # Write back
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)
                
                self.logger.info(f"Saved calibration offset for {self.serial_number}: {offset}")
            else:
                self.logger.error(f"Cannot save calibration - no serial number detected")
            
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
        self.cmd_topic = Topic(self.participant, cmd_topic_name, HGHandCmd_)
        self.state_topic = Topic(self.participant, state_topic_name, HGHandState_)
        
        # Create reader/writer
        self.cmd_reader = DataReader(self.participant, self.cmd_topic)
        self.state_writer = DataWriter(self.participant, self.state_topic)
        
        self.logger.info(f"DDS ready: {cmd_topic_name} → {state_topic_name}")
    
    def calibrate(self):
        """Calibration on command - can be called by robot when needed"""
        self.logger.info("Starting calibration on command...")
        
        try:
            # Perform calibration - this closes gripper and sets zero position
            self.gripper.calibrate()
            
            # Save actual zero position to device config for persistence
            zero_pos = self.gripper.zero_positions[0]
            self.save_calibration(zero_pos)
            
            # Verify with quick test using position control only
            self.gripper.set_max_effort(100)  # 100% effort for consistency
            target_pos = self.gripper.scale(25, self.gripper.GRIP_MAX)
            self.gripper._goto_position(target_pos)
            time.sleep(1)
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
        
        Use 100% effort for position mode commands to ensure fast, responsive movement
        """
        # Use 100% effort for position mode
        return 100.0
    
    def get_appropriate_effort(self, position_pct: float) -> float:
        """Get appropriate effort for different positions"""
        if position_pct <= 5.0 or position_pct >= 95.0:
            return 40.0  # Lower effort at extremes
        else:
            return 50.0  # Standard effort (peak power limited)
    
    def receive_commands(self):
        """Receive latest DDS command (non-blocking)"""
        try:
            samples = self.cmd_reader.take(N=10)  # Take up to 10 samples
            
            if samples:
                self.logger.debug(f"Received {len(samples)} DDS samples")
                # Keep only the latest command
                latest_sample = samples[-1]
                
                if latest_sample and hasattr(latest_sample, 'motor_cmd') and latest_sample.motor_cmd and len(latest_sample.motor_cmd) > 0:
                    motor_cmd = latest_sample.motor_cmd[0]
                    
                    # Convert Dex1 command to gripper parameters
                    target_position = self.dex1_to_ezgripper(motor_cmd.q)
                    
                    # Position commands ALWAYS use 100% effort
                    # Force control happens after contact via torque mode transition
                    actual_effort = 100.0
                    
                    # Store latest command
                    self.latest_command = GripperCommand(
                        position_pct=target_position,
                        effort_pct=actual_effort,
                        timestamp=time.time(),
                        q_radians=motor_cmd.q,
                        tau=motor_cmd.tau
                    )
                    self.logger.debug(f"Command received: q={motor_cmd.q:.3f} rad -> {target_position:.1f}%")
                else:
                    self.logger.debug(f"Sample has no motor_cmd data")
        
        except Exception as e:
            self.logger.error(f"Command receive failed: {e}")
    
    def execute_command(self):
        """Execute latest command (no locking, single-threaded)"""
        if self.latest_command is None:
            return
        
        try:
            cmd = self.latest_command
            
            # Only update effort if it changed (reduces serial writes from 3 to 1)
            if self.last_effort_pct != cmd.effort_pct:
                self.gripper.set_max_effort(int(cmd.effort_pct))
                self.last_effort_pct = cmd.effort_pct
            
            # Send position command (only 1 serial write instead of 3)
            self.gripper._goto_position(self.gripper.scale(int(cmd.position_pct), self.gripper.GRIP_MAX))
            
            # Update state (thread-safe)
            with self.state_lock:
                self.target_position_pct = cmd.position_pct
                self.commanded_position_pct = cmd.position_pct  # Update commanded position for prediction
                self.current_effort_pct = cmd.effort_pct
            
            # Increment command counter
            self.command_count += 1
            
            # Log command occasionally
            if self.command_count % 50 == 0:
                if cmd.q_radians <= 0.1:
                    mode = "CLOSE"
                elif cmd.q_radians >= 6.0:
                    mode = "OPEN"
                else:
                    mode = f"POSITION {cmd.position_pct:.1f}%"
                self.logger.info(f"Executing: {mode} (q={cmd.q_radians:.3f}, tau={cmd.tau:.3f})")
            
        except Exception as e:
            self.logger.error(f"Command execution failed: {e}")
    
    def update_predicted_position(self):
        """Update predicted position with constraints (no overshoot, no reverse direction) - thread-safe"""
        current_time = time.time()
        dt = current_time - self.last_predict_time
        self.last_predict_time = current_time
        
        with self.state_lock:
            # Calculate maximum position change based on gripper speed
            max_delta = self.movement_speed * dt  # %/sec * seconds = %
            
            # Calculate error between commanded and predicted position
            position_error = self.commanded_position_pct - self.predicted_position_pct
            
            # Constraint 1: Never overshoot commanded position
            if abs(position_error) <= max_delta:
                # Close enough - snap to commanded position
                self.predicted_position_pct = self.commanded_position_pct
            else:
                # Move toward commanded position at maximum speed
                # Constraint 2: Never move opposite to commanded direction
                direction = 1.0 if position_error > 0 else -1.0
                self.predicted_position_pct += direction * max_delta
    
    def publish_state(self):
        """Publish predicted gripper state at 200 Hz (called from state thread)"""
        current_time = time.time()
        
        try:
            # Update predicted position based on commanded position and movement speed
            self.update_predicted_position()
            
            # Read shared state with lock
            with self.state_lock:
                predicted_pos = self.predicted_position_pct
                actual_pos = self.actual_position_pct
                commanded_pos = self.commanded_position_pct
                effort = self.current_effort_pct
            
            # Convert predicted position to Dex1 units for publishing
            current_q = self.ezgripper_to_dex1(predicted_pos)
            current_tau = effort / 10.0
            
            # Create motor state (only q and tau_est are real, rest are defaults)
            motor_state = HGMotorState_(
                mode=0,
                q=current_q,
                dq=0.0,
                ddq=0.0,
                tau_est=current_tau,
                temperature=[0, 0],
                vol=0.0,
                sensor=[0, 0],
                motorstate=0,
                reserve=[0, 0, 0, 0]
            )
            motor_state.id = 1 if self.side == 'left' else 2
            
            # Create default IMU state (all zeros - no IMU sensor)
            imu_state = IMUState_(
                quaternion=[0.0, 0.0, 0.0, 0.0],
                gyroscope=[0.0, 0.0, 0.0],
                accelerometer=[0.0, 0.0, 0.0],
                rpy=[0.0, 0.0, 0.0],
                temperature=0
            )
            
            hand_state = HGHandState_(
                motor_state=[motor_state],
                press_sensor_state=[],  # No pressure sensors on Dex1-1
                imu_state=imu_state,
                power_v=0.0,
                power_a=0.0,
                system_v=0.0,
                device_v=0.0,
                error=[0, 0],
                reserve=[0, 0]
            )
            
            # Publish state at 200 Hz (every loop)
            self.state_writer.write(hand_state)
            self.last_status_time = current_time
            self.state_publish_count += 1
            
            # Monitor and report every 5 seconds
            if current_time - self.last_monitor_time >= self.monitor_interval:
                elapsed = current_time - self.last_monitor_time
                actual_rate = self.state_publish_count / elapsed
                position_error = abs(predicted_pos - commanded_pos)
                tracking_error = abs(predicted_pos - actual_pos)
                
                self.logger.info(f"📊 Monitor: State={actual_rate:.1f}Hz | Cmd={commanded_pos:.1f}% | Pred={predicted_pos:.1f}% | Actual={actual_pos:.1f}% | Err={position_error:.1f}% | Track={tracking_error:.1f}%")
                
                self.state_publish_count = 0
                self.last_monitor_time = current_time
            
        except Exception as e:
            self.logger.error(f"State publishing failed: {e}")
    
    def control_loop(self):
        """Control thread: Receive commands and execute at 30 Hz (limited by serial)"""
        self.logger.info("Starting control thread at 30 Hz...")
        period = 1.0 / self.control_loop_rate
        next_cycle = time.time()
        
        try:
            while self.running:
                # Receive and execute commands
                self.receive_commands()
                self.execute_command()
                
                # Read actual position periodically (every 10 cycles = 3 Hz)
                if self.command_count % 10 == 0:
                    with self.state_lock:
                        self.actual_position_pct = self.gripper.get_position()
                        # Sync predicted position with actual
                        self.predicted_position_pct = self.actual_position_pct
                
                # Absolute time scheduling to prevent drift
                next_cycle += period
                sleep_time = next_cycle - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    # Missed deadline - reset to current time
                    next_cycle = time.time()
                    
        except Exception as e:
            self.logger.error(f"Control thread error: {e}")
        finally:
            self.logger.info("Control thread stopped")
    
    def state_loop(self):
        """State thread: Publish predicted position at 200 Hz"""
        self.logger.info("Starting state thread at 200 Hz...")
        period = 1.0 / self.state_loop_rate
        next_cycle = time.time()
        
        try:
            while self.running:
                # Update predicted position and publish state
                self.publish_state()
                
                # Absolute time scheduling for precise 200 Hz
                next_cycle += period
                sleep_time = next_cycle - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    # Missed deadline - reset
                    next_cycle = time.time()
                    
        except Exception as e:
            self.logger.error(f"State thread error: {e}")
        finally:
            self.logger.info("State thread stopped")
    
    def run(self):
        """Start multi-threaded driver with control and state threads"""
        self.logger.info("Starting multi-threaded EZGripper driver...")
        self.logger.info("  Control thread: 30 Hz (commands + actual position)")
        self.logger.info("  State thread: 200 Hz (predicted position publishing)")
        
        # Start threads
        self.control_thread = threading.Thread(target=self.control_loop, daemon=True, name="Control")
        self.state_thread = threading.Thread(target=self.state_loop, daemon=True, name="State")
        
        self.control_thread.start()
        self.state_thread.start()
        
        try:
            # Main thread waits for keyboard interrupt
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.logger.info("Shutting down corrected EZGripper driver...")
        finally:
            self.running = False
            self.control_thread.join(timeout=2.0)
            self.state_thread.join(timeout=2.0)
    
    def shutdown(self):
        """Clean shutdown"""
        self.logger.info("Shutting down hardware...")
        self.running = False
        if self.gripper:
            self.gripper.move_with_torque_management(50.0, 30.0)
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
