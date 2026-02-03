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

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize

# Import ONLY what xr_teleoperate uses for Dex1
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_, MotorStates_, MotorState_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_

# Minimal libezgripper imports - only what we use
from libezgripper import create_connection, create_gripper
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
        self.current_sensor_data = {}        # Store bulk sensor data from bulk reads
        
        # Error handling and health monitoring
        self.hardware_healthy = True          # Hardware communication status
        self.comm_error_count = 0            # Consecutive communication errors
        self.max_comm_errors = 5             # Stop after N consecutive errors
        self.last_successful_comm = time.time()
        self.servo_error_count = 0           # Servo hardware errors
        self.critical_servo_errors = 0       # Critical servo errors
        
        # Monitoring for verification
        self.state_publish_count = 0
        self.state_publish_error_count = 0
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
        
        # Auto-calibrate at startup if enabled (but not if manual calibration will be done)
        if self.gripper.config.calibration_auto_on_init:
            self.logger.info("Auto-calibration enabled in config, but skipping - will use manual calibration")
            # Don't auto-calibrate - let manual calibration handle it
        else:
            self.logger.info("Auto-calibration disabled in config")
        
        self.logger.info(f"Corrected EZGripper driver ready: {side} side")
    
    def _initialize_hardware(self):
        """Initialize hardware connection and detect serial number"""
        self.logger.info(f"Connecting to EZGripper on {self.device}")
        
        try:
            self.connection = create_connection(dev_name=self.device, baudrate=1000000)  # 1 Mbps
            self.gripper = create_gripper(self.connection, f'corrected_{self.side}', [1])
            
            # Test connection and cache initial sensor data
            sensor_data = self.gripper.bulk_read_sensor_data()
            self.current_sensor_data = sensor_data
            test_pos = self.get_position()
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
    
    def get_position(self):
        """Get current position from cached sensor data"""
        if self.current_sensor_data and 'position' in self.current_sensor_data:
            return self.current_sensor_data['position']
        else:
            # Fallback if no cached data
            return 50.0
    
    def get_temperature(self):
        """Get current temperature from cached sensor data"""
        return self.current_sensor_data.get('temperature', 25)
    
    def get_voltage(self):
        """Get current voltage from cached sensor data"""
        return self.current_sensor_data.get('voltage', 12.0)
    
    def get_current(self):
        """Get current motor current from cached sensor data"""
        return self.current_sensor_data.get('current', 0)
    
    def get_error(self):
        """Get current error code from cached sensor data"""
        return self.current_sensor_data.get('error', 0)
    
    def get_error_details(self):
        """Get current error details from cached sensor data"""
        return self.current_sensor_data.get('error_details', {'errors': []})
    
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
        
        # No calibration found - will run auto-calibration
        self.logger.info("No calibration found - will run auto-calibration")
    
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
        """Setup DDS interfaces - matches xr_teleoperate exactly"""
        self.logger.info("Setting up DDS interfaces...")
        
        # Initialize DDS factory - matches xr_teleoperate
        ChannelFactoryInitialize(self.domain)  # Don't use shm:// to avoid buffer overflow
        
        # Dex1 topics - matches xr_teleoperate exactly
        cmd_topic_name = f"rt/dex1/{self.side}/cmd"
        state_topic_name = f"rt/dex1/{self.side}/state"
        
        # Create publisher and subscriber - matches xr_teleoperate exactly
        self.cmd_subscriber = ChannelSubscriber(cmd_topic_name, MotorCmds_)
        self.cmd_subscriber.Init()
        
        self.state_publisher = ChannelPublisher(state_topic_name, MotorStates_)
        self.state_publisher.Init()
        
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
            
            # Calibration already moved to 50% position, wait for it to arrive
            import time
            time.sleep(0.5)  # Wait for gripper to reach position 50
            
            sensor_data = self.gripper.bulk_read_sensor_data(0)
            actual = sensor_data.get('position', 0.0)
            error = abs(actual - 50.0)
            
            if error <= 10.0:
                self.is_calibrated = True
                self.logger.info(f"✅ Calibration successful (at {actual:.1f}%, error: {error:.1f}%)")
                return True
            else:
                self.logger.warning(f"⚠️ Calibration issue (at {actual:.1f}%, expected 50%, error: {error:.1f}%)")
                return False
                
        except Exception as e:
            self.logger.error(f"Calibration failed: {e}")
            return False
    
    def dex1_to_ezgripper(self, q_radians: float) -> float:
        """
        Convert Dex1 position to EZGripper position
        Dex1: 0.0 rad = closed, 5.4 rad = open
        EZGripper: 0% = closed, 100% = open
        """
        # Clamp to valid range
        q_clamped = max(0.0, min(5.4, q_radians))
        # Linear mapping: 0.0 rad -> 0% closed, 5.4 rad -> 100% open
        return (q_clamped / 5.4) * 100.0
    
    def ezgripper_to_dex1(self, position_pct: float) -> float:
        """
        Convert EZGripper position to Dex1 position
        EZGripper: 0% = closed, 100% = open
        Dex1: 0.0 rad = closed, 5.4 rad = open
        """
        # Clamp to valid range
        pct_clamped = max(0.0, min(100.0, position_pct))
        # Linear mapping: 0% closed -> 0.0 rad, 100% open -> 5.4 rad
        rad_value = (pct_clamped / 100.0) * 5.4
        # Clamp final result to prevent floating-point precision issues
        return max(0.0, min(5.4, rad_value))
    
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
        """Receive latest DDS command (non-blocking) - matches xr_teleoperate"""
        try:
            # Use ChannelSubscriber.Read() like xr_teleoperate
            cmd_msg = self.cmd_subscriber.Read()
            
            if cmd_msg and hasattr(cmd_msg, 'cmds') and cmd_msg.cmds and len(cmd_msg.cmds) > 0:
                motor_cmd = cmd_msg.cmds[0]
                
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
                self.logger.info(f"Command received: q={motor_cmd.q:.3f} rad -> {target_position:.1f}%")
            else:
                self.logger.debug(f"No command data")
        
        except Exception as e:
            self.logger.error(f"Command receive failed: {e}")
    
    def execute_command(self):
        """Execute latest command (no locking, single-threaded)"""
        if self.latest_command is None:
            return
        
        # PROTECTION: Don't execute commands if hardware is unhealthy
        if not self.hardware_healthy:
            self.logger.warning("Hardware unhealthy - skipping command execution")
            return
        
        try:
            cmd = self.latest_command
            
            # Position mode - use goto_position which sets target variables
            self.gripper.goto_position(cmd.position_pct, cmd.effort_pct)
            
            if self.command_count % 30 == 0:  # Log every second at 30Hz
                self.logger.info(f"Command received: q={cmd.position_pct:.1f}%")
            
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
            self.logger.error(f"Exception type: {type(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
    
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
        
        # PROTECTION: Don't publish false state when hardware is unhealthy
        if not self.hardware_healthy:
            # Option: Stop publishing entirely (safer - xr_teleoperate knows something's wrong)
            # return
            
            # Option: Publish explicit error state
            try:
                motor_state = MotorState_(
                    mode=255,                    # Error mode
                    q=0.0,                       # Safe position
                    dq=0.0,                      # No velocity
                    ddq=0.0,                     # No acceleration
                    tau_est=0.0,                 # No torque
                    q_raw=0.0,                   # Raw position (float32)
                    dq_raw=0.0,                  # Raw velocity (float32)
                    ddq_raw=0.0,                 # Raw acceleration (float32)
                    temperature=0,               # Error temperature (uint8)
                    lost=0xFFFFFFFF,             # Error - max lost packets (uint32)
                    reserve=[0xFFFFFFFF, 0xFFFFFFFF]  # Error flags (array[uint32, 2])
                )
                
                motor_states = MotorStates_()
                motor_states.states = [motor_state]
                self.state_publisher.Write(motor_states)
                return
            except Exception as e:
                self.logger.error(f"Error state publishing failed: {e}")
                return
        
        try:
            # Use actual position from 30Hz control loop - no prediction needed
            with self.state_lock:
                actual_pos = self.actual_position_pct
                current_effort = self.current_effort_pct
            
            # Convert actual position to Dex1 units for publishing
            current_q = self.ezgripper_to_dex1(actual_pos)
            current_tau = current_effort / 10.0
            
            # Read real sensor data for DDS compliance and cache it
            sensor_data = self.gripper.bulk_read_sensor_data()
            self.current_sensor_data = sensor_data  # Update cache
            
            # Create motor state with official SDK2 structure
            # ENFORCE DDS CONTRACT: Clamp to valid range [0.0, 5.4] before writing to DDS
            clamped_q = max(0.0, min(5.4, current_q))
            motor_state = MotorState_(
                mode=0,                           # Position control mode
                q=clamped_q,                      # Position feedback
                dq=0.0,                           # No velocity data
                ddq=0.0,                          # No acceleration data
                tau_est=current_tau,              # Torque estimation

                q_raw=clamped_q,                  # Raw position (float32)
                dq_raw=0.0,                       # Raw velocity (float32)
                ddq_raw=0.0,                      # Raw acceleration (float32)
                temperature=int(self.get_temperature()),  # Temperature (uint8)
                lost=0,                           # Lost packets (uint32)
                reserve=[0, 0]                    # Reserve array[uint32, 2]
            )
            
            # Create MotorStates_ message
            motor_states = MotorStates_()
            motor_states.states = [motor_state]
            
            # Publish to DDS
            try:
                result = self.state_publisher.Write(motor_states)
                self.logger.debug(f"Write() returned: {result} (type: {type(result)})")
            except TypeError as e:
                if "'tuple' object is not callable" in str(e):
                    # This is a bug in CycloneDDS library - ignore it
                    self.state_publish_error_count += 1
                    if self.state_publish_error_count % 100 == 1:  # Log first error and every 100th
                        self.logger.warning(f"CycloneDDS library bug encountered (ignoring): {e}")
                else:
                    self.logger.error(f"State publishing failed (TypeError): {e}")
                    import traceback
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
            except Exception as e:
                self.logger.error(f"State publishing failed: {e}")
                self.logger.error(f"Exception type: {type(e)}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.last_status_time = current_time
            self.state_publish_count += 1
            
            # Monitor and report every 5 seconds
            if current_time - self.last_monitor_time >= self.monitor_interval:
                elapsed = current_time - self.last_monitor_time
                actual_rate = self.state_publish_count / elapsed
                # Use actual position from control loop - no prediction
                with self.state_lock:
                    current_actual = self.actual_position_pct
                    current_commanded = self.commanded_position_pct
                
                position_error = abs(current_actual - current_commanded)
                
                self.logger.info(f"📊 Monitor: State={actual_rate:.1f}Hz | Cmd={current_commanded:.1f}% | Actual={current_actual:.1f}% | Err={position_error:.1f}%")
                
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
                
                # Read sensor data using bulk operations (every cycle = 30 Hz for accurate control)
                # Changed from every 10 cycles (3 Hz) to every cycle (30 Hz)
                try:
                    # Use bulk read for all sensor data in single USB transaction and update cache
                    sensor_data = self.gripper.bulk_read_sensor_data()
                    self.current_sensor_data = sensor_data  # Update cache
                    
                    # Check for servo hardware errors using cache
                    self._handle_servo_errors(self.get_error_details())
                    
                    with self.state_lock:
                        self.actual_position_pct = self.get_position()
                        # Sync predicted position with actual (minimal prediction needed now)
                        self.predicted_position_pct = self.actual_position_pct
                    
                    # Reset communication error counters on success
                    self.comm_error_count = 0
                    self.last_successful_comm = time.time()
                    
                except Exception as e:
                    # Handle communication errors
                    self._handle_communication_error(e)
                    
                    # Fallback to individual position read if bulk read fails
                    try:
                        with self.state_lock:
                            sensor_data = self.gripper.bulk_read_sensor_data(0)
                            self.actual_position_pct = sensor_data.get('position', 0.0)
                            self.predicted_position_pct = self.actual_position_pct
                    except Exception as fallback_e:
                        self.logger.error(f"Both bulk and fallback reads failed: {fallback_e}")
                        self.hardware_healthy = False
                
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

    def _handle_servo_errors(self, error_details):
        """Handle servo hardware errors - SIMPLE: any error = torque off"""
        if not error_details['has_error']:
            # Reset error counters on clean status
            if self.servo_error_count > 0:
                self.logger.info("Servo errors cleared")
            self.servo_error_count = 0
            return
        
        self.servo_error_count += 1
        self.logger.critical(f"Servo error #{self.servo_error_count}: {error_details['errors']}")
        
        # SIMPLE: Any error = disable torque immediately
        self.gripper.disable_torque()  # Torque to zero
        self.hardware_healthy = False

    def _handle_communication_error(self, error):
        """Handle communication errors - SIMPLE: disable torque on failures"""
        self.comm_error_count += 1
        self.logger.error(f"Communication error #{self.comm_error_count}: {error}")
        
        # Sequential communication issues = torque to zero
        if self.comm_error_count >= self.max_comm_errors:
            self.gripper.disable_torque()  # Torque to zero
            self.hardware_healthy = False
            return
        
        if time.time() - self.last_successful_comm > 2.0:  # 2 second timeout
            self.gripper.disable_torque()  # Torque to zero
            self.hardware_healthy = False

    def state_loop(self):
        """State thread: Publish actual position at 200 Hz"""
        self.logger.info("Starting state thread at 200 Hz...")
        period = 1.0 / self.state_loop_rate
        next_cycle = time.time()

        try:
            while self.running:
                # Publish actual position from 30Hz control loop
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
            next_cycle = time.time()
        
            try:
                while self.running:
                    # Publish actual position from 30Hz control loop
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
                    self.gripper.goto_position(50.0, 10.0)  # Move to safe position with low effort
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
        print("Calibration completed. Exiting.")
        return
    
    # Normal DDS operation mode
    try:
        driver.run()
    except KeyboardInterrupt:
        pass
    finally:
        driver.shutdown()


if __name__ == "__main__":
    main()
