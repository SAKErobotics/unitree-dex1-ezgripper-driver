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
from libezgripper.grasp_manager import GraspManager
from libezgripper.gripper_telemetry import GripperTelemetry
from libezgripper.health_monitor import HealthMonitor
import serial.tools.list_ports
import importlib
import sys

# Force reload of grasp_manager to ensure latest code is used
if 'libezgripper.grasp_manager' in sys.modules:
    importlib.reload(sys.modules['libezgripper.grasp_manager'])
    from libezgripper.grasp_manager import GraspManager  # Re-import after reload

# Error recovery handling
from error_recovery_enhancement import ErrorRecoveryHandler, ErrorRecoveryCommand, ErrorStatus


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
        
        # Add file handler for GUI telemetry reading
        file_handler = logging.FileHandler('/tmp/driver_test.log')
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
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
        self.command_thread = None  # Separate thread for DDS command reception
        
        # Grasp manager - state-based adaptive grasping
        self.grasp_manager = None  # Initialized after hardware
        
        # Health monitor for telemetry
        self.health_monitor = None  # Initialized after hardware
        
        # Telemetry publishing
        self.telemetry_enabled = False
        self.telemetry_publisher = None
        self.managed_effort = 0.0  # Track managed effort for telemetry
        
        # Initialize
        self._initialize_hardware()
        self._load_calibration()
        self._setup_dds()
        
        # Initialize simplified grasp manager after hardware is ready
        # Loads force percentages and thresholds from config
        self.grasp_manager = GraspManager(self.gripper.config)
        # GraspManager prints its own initialization message
        
        # Initialize health monitor for telemetry
        if self.gripper.servos:
            self.health_monitor = HealthMonitor(self.gripper.servos[0], self.gripper.config)
            self.logger.info("Health monitor initialized for telemetry")
        
        # Initialize error recovery handler
        self.error_recovery = ErrorRecoveryHandler(self.logger)
        self.last_error_check_time = time.time()
        self.error_check_interval = 0.1  # Check errors every 100ms
        self.error_status = None
        self.error_recovery_enabled = True
        self.logger.info("Error recovery handler initialized")
        
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
            
            # Wait 2 seconds for servo to be ready after USB connection
            # Prevents communication errors on first read operation
            self.logger.info("Waiting for servo to settle...")
            time.sleep(2.0)
            
            self.gripper = create_gripper(self.connection, f'corrected_{self.side}', [1])
            
            # CLEAR HARDWARE ERRORS (The fix for Error 128)
            self.logger.info("Attempting to clear hardware error states (Resetting Error 128)...")
            for servo in self.gripper.servos:
                try:
                    # Method A: Use the libezgripper reboot if available
                    if hasattr(servo, 'reboot'):
                        servo.reboot()
                    else:
                        # Method B: Direct register write to Reboot (Address 0x08 for SAKE/Dynamixel-based)
                        # This clears the 128 (0x80) error bit
                        servo.write_address(0x08, [1]) 
                    
                    self.logger.info(f"Servo {servo.servo_id} reboot command sent.")
                    time.sleep(0.5) # Give the firmware time to restart the control loop
                except Exception as e:
                    self.logger.warning(f"Could not reboot servo {servo.servo_id}: {e}")
            
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
        if not self.current_sensor_data:
            return {'has_error': False, 'errors': []}
        
        # Get error code from sensor data (not error_details)
        error_code = self.current_sensor_data.get('error', 0)
        has_error = error_code != 0
        errors = []
        if has_error:
            errors.append(f"Hardware error code: {error_code}")
        
        return {'has_error': has_error, 'errors': errors}
    
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
        
        # Setup telemetry publisher - always enabled for monitoring
        telemetry_config = self.gripper.config._config.get('telemetry', {})
        topic_prefix = telemetry_config.get('topic_prefix', 'rt/gripper')
        telemetry_topic = f"{topic_prefix}/{self.side}/telemetry"
        
        # Create telemetry publisher using String_ type for JSON
        from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_
        self.telemetry_publisher = ChannelPublisher(telemetry_topic, String_)
        self.telemetry_publisher.Init()
        self.telemetry_enabled = True
        
        # Setup debug telemetry publisher if enabled
        self.debug_telemetry_enabled = telemetry_config.get('debug_enabled', False)
        if self.debug_telemetry_enabled:
            debug_topic_prefix = telemetry_config.get('debug_topic_prefix', 'rt/gripper/debug')
            debug_topic = f"{debug_topic_prefix}/{self.side}"
            self.debug_telemetry_publisher = ChannelPublisher(debug_topic, String_)
            self.debug_telemetry_publisher.Init()
            self.logger.info(f"Debug telemetry publisher ready: {debug_topic} @ 30Hz")
        
        self.logger.info(f"Telemetry publisher ready: {telemetry_topic} @ 30Hz")
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
        Convert Dex1 position to EZGripper position - direct mapping.
        
        Unitree Dex1 convention: 0.0 rad = closed, 5.4 rad = open
        EZGripper internal: 0% = closed, max_open_percent = open
        Commands are scaled: 100% input → max_open_percent output
        
        Direct mapping:
        - 0.0 rad -> 0% (closed)
        - 5.4 rad -> max_open_percent (open)
        """
        q_clamped = max(0.0, min(5.4, q_radians))
        # Direct mapping: 0 rad -> 0%, 5.4 rad -> 100%
        position_100 = (q_clamped / 5.4) * 100.0
        
        # Scale to max_open_percent: 100% input → max_open_percent output
        max_open = self.gripper.config.max_open_percent
        scaled_position = (position_100 / 100.0) * max_open
        
        return max(0.0, min(max_open, scaled_position))
    
    def ezgripper_to_dex1(self, position_pct: float) -> float:
        """
        Convert EZGripper position to Dex1 position - direct mapping.
        
        EZGripper internal: 0% = closed, max_open_percent = open
        Unitree Dex1 convention: 0.0 rad = closed, 5.4 rad = open
        
        Direct mapping:
        - 0% (closed) -> 0.0 rad
        - max_open_percent (open) -> 5.4 rad
        """
        max_open = self.gripper.config.max_open_percent
        
        # Unscale from max_open_percent to 0-100%
        position_100 = (position_pct / max_open) * 100.0
        pct_clamped = max(0.0, min(100.0, position_100))
        
        # Direct mapping: 0% -> 0 rad, 100% -> 5.4 rad
        return (pct_clamped / 100.0) * 5.4
    
    def dex1_to_effort(self, tau: float) -> float:
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
    
    def command_reception_loop(self):
        """Dedicated thread for DDS command reception (blocking Read() is OK here)"""
        self.logger.info("Starting command reception thread...")
        self.logger.info(f"Listening on topic: rt/dex1/{self.side}/cmd")
        
        cmd_count = 0
        while self.running:
            try:
                # ChannelSubscriber.Read() blocks until message arrives - that's OK in this thread
                cmd_msg = self.cmd_subscriber.Read()
                
                if cmd_msg and hasattr(cmd_msg, 'cmds') and cmd_msg.cmds and len(cmd_msg.cmds) > 0:
                    motor_cmd = cmd_msg.cmds[0]
                    cmd_count += 1
                    
                    # Check for error recovery command (using tau field as command)
                    # tau > 0 indicates error recovery command (0-4)
                    if motor_cmd.tau > 0 and motor_cmd.tau <= 4:
                        recovery_cmd = ErrorRecoveryCommand(int(motor_cmd.tau))
                        if recovery_cmd != ErrorRecoveryCommand.NO_OP:
                            self.logger.info(f"📥 DDS RECOVERY CMD #{cmd_count}: {recovery_cmd.name}")
                            self.handle_error_recovery_command(recovery_cmd)
                            continue  # Skip normal command processing
                    
                    # Convert Dex1 command to gripper parameters
                    target_position = self.dex1_to_ezgripper(motor_cmd.q)
                    
                    # Log every command for debugging (will reduce later)
                    if cmd_count % 10 == 1:  # Log every 10th command
                        self.logger.info(f"📥 DDS CMD #{cmd_count}: q={motor_cmd.q:.3f} rad → {target_position:.1f}%")
                    
                    # Store latest command (effort will be managed by GraspManager)
                    self.latest_command = GripperCommand(
                        position_pct=target_position,
                        effort_pct=0.0,  # Effort managed by GraspManager
                        timestamp=time.time(),
                        q_radians=motor_cmd.q,
                        tau=motor_cmd.tau
                    )
                else:
                    # Log when we get a message but it's empty/invalid
                    if cmd_count == 0:  # Only log if we haven't received any valid commands yet
                        self.logger.warning(f"Received invalid/empty command message: {cmd_msg}")
            
            except Exception as e:
                if self.running:  # Only log if not shutting down
                    self.logger.error(f"Command reception error: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())
                    time.sleep(0.1)  # Brief pause on error
        
        self.logger.info(f"Command reception thread stopped (received {cmd_count} commands total)")
    
    def execute_command(self):
        """
        Execute latest command using GraspManager
        
        DDS commands are treated as INPUTS to the state machine, not direct execution.
        The GraspManager owns the goal and adapts based on state + sensors + DDS input.
        """
        if self.latest_command is None:
            return
        
        # HEARTBEAT CHECK: Removed for GUI operation
        # GraspManager state machine properly handles command gaps
        # Previous 250ms timeout was blocking button clicks after continuous mode
        
        # Check for errors before executing command
        self.check_and_handle_errors()
        
        # PROTECTION: Don't execute commands if hardware is unhealthy
        if not self.hardware_healthy:
            self.logger.warning("Hardware unhealthy - skipping command execution")
            return
        
        try:
            cmd = self.latest_command
            
            # Get current sensor data for GraspManager
            sensor_data = self.current_sensor_data if self.current_sensor_data else {}
            
            # Add commanded position to sensor data for GraspManager
            sensor_data['commanded_position'] = cmd.position_pct
            
            # Get hardware current limit from config for percentage conversion
            hardware_current_limit = self.gripper.config._config.get('servo', {}).get('dynamixel_settings', {}).get('current_limit', 1600)
            
            # Process DDS command as INPUT through GraspManager
            # GraspManager returns the MANAGED goal (not raw DDS command)
            goal_position, goal_effort = self.grasp_manager.process_cycle(
                sensor_data=sensor_data,
                hardware_current_limit_ma=hardware_current_limit
            )
            
            # Execute the MANAGED goal (not raw DDS command)
            self.logger.info(f"🎯 DDS INPUT: pos={cmd.position_pct:.1f}%")
            self.logger.info(f"🎯 MANAGED GOAL: pos={goal_position:.1f}%, effort={goal_effort:.1f}%")
            
            # Track managed effort for telemetry
            self.managed_effort = goal_effort
            
            # Publish debug telemetry if enabled
            if self.debug_telemetry_enabled:
                self._publish_debug_telemetry(cmd, sensor_data, goal_position, goal_effort)
            
            self.gripper.goto_position(goal_position, goal_effort)
            
            if self.command_count % 30 == 0:  # Log every second at 30Hz
                state_info = self.grasp_manager.get_state_info()
                self.logger.info(f"State: {state_info.get('state', 'UNKNOWN')}, Contact: {state_info.get('in_contact', False)}")
            
            # Update state (thread-safe)
            with self.state_lock:
                self.target_position_pct = cmd.position_pct  # DDS target
                self.commanded_position_pct = goal_position  # Actual commanded (managed)
                self.current_effort_pct = goal_effort
            
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
                self.logger.info(f"DDS Command: {mode} (q={cmd.q_radians:.3f}, tau={cmd.tau:.3f})")
            
        except Exception as e:
            self.logger.error(f"Command execution failed: {e}")
            self.logger.error(f"Exception type: {type(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
    
    def check_and_handle_errors(self):
        """Monitor for hardware errors and handle them"""
        if not self.error_recovery_enabled or not self.gripper or not self.gripper.servos:
            return
            
        current_time = time.time()
        if current_time - self.last_error_check_time < self.error_check_interval:
            return
            
        self.last_error_check_time = current_time
        
        try:
            # Read error status from first servo
            servo = self.gripper.servos[0]
            self.error_status = self.error_recovery.read_error_status(servo)
            
            # Log errors if detected
            if self.error_recovery.has_error(self.error_status):
                error_list = []
                if self.error_status.overload_error:
                    error_list.append("OVERLOAD")
                if self.error_status.overheating_error:
                    error_list.append("OVERHEATING")
                if self.error_status.voltage_error:
                    error_list.append("VOLTAGE")
                if self.error_status.hardware_error:
                    error_list.append("HARDWARE")
                if self.error_status.servo_in_shutdown:
                    error_list.append("SHUTDOWN")
                
                self.logger.warning(f"Hardware error detected: {', '.join(error_list)} "
                                  f"(status=0x{self.error_status.error_bits:04X})")
                
                # Mark hardware as unhealthy
                self.hardware_healthy = False
                
                # Attempt automatic recovery for overload errors
                if self.error_status.overload_error and not self.error_recovery.recovery_in_progress:
                    self.logger.info("Attempting automatic recovery from overload error")
                    success = self.error_recovery.execute_recovery(servo, ErrorRecoveryCommand.TORQUE_CYCLE)
                    if success:
                        self.logger.info("Automatic recovery successful")
                        self.hardware_healthy = True
                    else:
                        self.logger.error("Automatic recovery failed")
        
        except Exception as e:
            self.logger.error(f"Error checking failed: {e}")
    
    def handle_error_recovery_command(self, command: ErrorRecoveryCommand):
        """Handle error recovery command from DDS"""
        if not self.gripper or not self.gripper.servos:
            self.logger.warning("Cannot execute recovery - no servo available")
            return
            
        servo = self.gripper.servos[0]
        
        # Execute recovery in separate thread to avoid blocking control loop
        import threading
        def recovery_thread():
            success = self.error_recovery.execute_recovery(servo, command)
            if success:
                self.logger.info(f"Recovery command {command.name} completed successfully")
                self.hardware_healthy = True
            else:
                self.logger.error(f"Recovery command {command.name} failed")
        
        thread = threading.Thread(target=recovery_thread)
        thread.daemon = True
        thread.start()
    
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
    
    def _publish_debug_telemetry(self, cmd, sensor_data, goal_position, goal_effort):
        """Publish debug telemetry to DDS for contact detection analysis"""
        try:
            import json
            from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_
            
            debug_info = self.grasp_manager.get_debug_info()
            debug_data = {
                'timestamp': time.time(),
                'commanded_position': cmd.position_pct,
                'actual_position': sensor_data.get('position', 0.0),
                'goal_position': goal_position,
                'goal_effort': goal_effort,
                'current_ma': abs(sensor_data.get('current', 0)),
                'grasp_manager': debug_info
            }
            
            json_str = json.dumps(debug_data)
            msg = String_(data=json_str)
            self.debug_telemetry_publisher.Write(msg)
            
        except Exception as e:
            self.logger.error(f"Debug telemetry publishing failed: {e}")
    
    def _publish_telemetry(self):
        """Publish internal telemetry at 30Hz (called from control loop)"""
        try:
            # Create telemetry from current driver state
            telemetry = GripperTelemetry.from_driver_state(self)
            
            # Log telemetry periodically (every 0.1 seconds = 3 messages at 30Hz)
            if not hasattr(self, '_telemetry_log_count'):
                self._telemetry_log_count = 0
            
            self._telemetry_log_count += 1
            if self._telemetry_log_count % 3 == 0:
                self.logger.info(f"📡 TELEMETRY: state={telemetry.grasp_state}, "
                               f"pos={telemetry.actual_position_pct:.1f}% (cmd={telemetry.commanded_position_pct:.1f}%), "
                               f"effort={telemetry.managed_effort_pct:.0f}%, "
                               f"contact={telemetry.contact_detected}, "
                               f"temp={telemetry.temperature_c:.1f}°C, "
                               f"error={telemetry.hardware_error}")
            
            # Publish to DDS as JSON string
            if self.telemetry_enabled and self.telemetry_publisher:
                import json
                from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_
                
                telemetry_dict = telemetry.to_dict()
                json_str = json.dumps(telemetry_dict)
                
                msg = String_(data=json_str)
                self.telemetry_publisher.Write(msg)
            
        except Exception as e:
            self.logger.error(f"Telemetry publishing failed: {e}")
    
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
            # Use cached position from 30Hz control loop (don't read servo at 200Hz!)
            with self.state_lock:
                actual_pos = self.actual_position_pct
                current_effort = self.current_effort_pct
            
            # Convert actual position to Dex1 units for publishing
            current_q = self.ezgripper_to_dex1(actual_pos)
            current_tau = current_effort / 10.0
            
            # Get GraspManager state for GUI display
            grasp_state_info = self.grasp_manager.get_state_info()
            grasp_state = grasp_state_info.get('state', 'UNKNOWN')
            
            # Map GraspState to motor mode for GUI visibility
            state_to_mode = {
                'idle': 0,
                'moving': 1, 
                'contact': 2,
                'grasping': 3
            }
            mode_for_gui = state_to_mode.get(grasp_state, 1)  # Default to MOVING
            
            # Log state mapping for debugging
            if self.state_publish_count % 50 == 0:  # Every 250ms at 200Hz
                self.logger.info(f"🔄 GUI STATE: {grasp_state} → mode={mode_for_gui}")
            
            self.logger.info(f"📤 PUBLISH: actual_pos={actual_pos:.1f}% → DDS_q={current_q:.3f}rad, state={grasp_state}")
            
            # Create motor state with official SDK2 structure
            # ENFORCE DDS CONTRACT: Clamp to valid range [0.0, 5.4] before writing to DDS
            clamped_q = max(0.0, min(5.4, current_q))
            motor_state = MotorState_(
                mode=mode_for_gui,                 # GraspManager state for GUI
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
                try:
                    # Read sensor data + collision detection (continuous at 30 Hz)
                    try:
                        result = self.gripper.update_main_loop()
                        
                        if result:
                            sensor_data = result['sensor_data']
                            self.current_sensor_data = sensor_data
                            
                            # Process GraspManager every 30Hz cycle (autonomous control)
                            # Get commanded position from latest DDS command (or use default target if no command)
                            if self.latest_command is not None:
                                commanded_position = self.latest_command.position_pct
                            else:
                                # Use target_position_pct (50%) instead of current position to allow movement after calibration
                                commanded_position = self.target_position_pct
                            
                            sensor_data['commanded_position'] = commanded_position
                            
                            # Get hardware current limit from config
                            hardware_current_limit = self.gripper.config._config.get('servo', {}).get('dynamixel_settings', {}).get('current_limit', 1600)
                            
                            # GraspManager runs every cycle for autonomous stall detection
                            goal_position, goal_effort = self.grasp_manager.process_cycle(
                                sensor_data=sensor_data,
                                hardware_current_limit_ma=hardware_current_limit
                            )
                            
                            # Track managed effort for telemetry
                            self.managed_effort = goal_effort
                            
                            # Execute managed goal to hardware
                            self.gripper.goto_position(goal_position, goal_effort)
                            
                            # Serial bus safety: small delay to let RS485 bus settle after write
                            time.sleep(0.005)
                            
                            # Log periodically
                            if self.command_count % 30 == 0:  # Every second at 30Hz
                                state_info = self.grasp_manager.get_state_info()
                                self.logger.info(f"🎯 AUTONOMOUS: pos={goal_position:.1f}%, effort={goal_effort:.1f}%, state={state_info.get('state', 'UNKNOWN')}")
                            
                            self.command_count += 1
                            
                            current_ma = sensor_data.get('current', 0)
                            self.logger.info(f"📊 SENSOR: raw={sensor_data.get('position_raw', 'N/A')}, pct={sensor_data.get('position', 'N/A'):.1f}%, current={current_ma}mA")
                            
                            self._handle_servo_errors(self.get_error_details())
                            
                            with self.state_lock:
                                self.actual_position_pct = self.get_position()
                                self.predicted_position_pct = self.actual_position_pct
                            
                            self.logger.info(f"🔄 READ: actual_position_pct={self.actual_position_pct:.1f}%")
                            
                            # Publish telemetry at 30Hz (same as control loop)
                            if self.telemetry_enabled:
                                self._publish_telemetry()
                            
                            self.comm_error_count = 0
                            self.last_successful_comm = time.time()
                            self.hardware_healthy = True  # Reset health on successful communication
                        
                    except Exception as e:
                        self._handle_communication_error(e)
                        # Clear the serial buffer to recover from noise/collisions
                        if hasattr(self.connection, 'port'):
                            try:
                                self.connection.port.reset_input_buffer()
                                self.logger.debug(f"Serial buffer cleared after error: {e}")
                            except:
                                pass
                    
                    # Absolute time scheduling
                    next_cycle += period
                    sleep_time = next_cycle - time.time()
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    else:
                        next_cycle = time.time()
                        
                except Exception as iter_e:
                    self.logger.error(f"❌ Control loop iteration crashed: {iter_e}")
                    import traceback
                    self.logger.error(traceback.format_exc())
                    
        except Exception as e:
            self.logger.error(f"Control thread encountered a fatal error: {e}")
        finally:
            # Crucial: Disable torque if we are exiting to prevent the "Lock" state
            self.logger.info("Control thread stopping. Cleaning up serial bus...")
            try:
                self.gripper.release() 
            except:
                pass
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
        self.gripper.goto_position(50.0, 10.0)  # Safe position with low effort
        self.hardware_healthy = False

    def _handle_communication_error(self, error):
        """Handle communication errors - SIMPLE: disable torque on failures"""
        self.comm_error_count += 1
        self.logger.error(f"Communication error #{self.comm_error_count}: {error}")
        
        # Sequential communication issues = torque to zero
        if self.comm_error_count >= self.max_comm_errors:
            self.gripper.goto_position(50.0, 10.0)  # Safe position with low effort
            self.hardware_healthy = False
            return
        
        if time.time() - self.last_successful_comm > 2.0:  # 2 second timeout
            self.gripper.goto_position(50.0, 10.0)  # Safe position with low effort
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
        self.logger.info("  State thread: 200 Hz (actual position publishing)")

        # Start threads
        self.command_thread = threading.Thread(target=self.command_reception_loop, daemon=True, name="Commands")
        self.control_thread = threading.Thread(target=self.control_loop, daemon=True, name="Control")
        self.state_thread = threading.Thread(target=self.state_loop, daemon=True, name="State")

        self.command_thread.start()
        self.control_thread.start()
        self.state_thread.start()

        try:
            # Main thread waits for keyboard interrupt
            while self.running:
                time.sleep(0.1)
        except (KeyboardInterrupt, SystemExit):
            self.logger.info("Shutdown signal received...")
        finally:
            self.running = False
            
            # Wait for threads to stop
            if self.command_thread and self.command_thread.is_alive():
                self.command_thread.join(timeout=1.5)
            if self.control_thread and self.control_thread.is_alive():
                self.control_thread.join(timeout=1.5)
            if self.state_thread and self.state_thread.is_alive():
                self.state_thread.join(timeout=1.0)
                
            self.logger.info("Threads joined. Invoking final hardware shutdown...")
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown - Fixed for USB2Dynamixel_Device"""
        self.logger.info("Shutting down hardware...")
        self.running = False
        
        if self.gripper:
            try:
                # 1. Try to release torque one last time
                try:
                    self.gripper.release()
                    time.sleep(0.1)
                except:
                    pass

                # 2. Disable Torque Enable register
                for servo in self.gripper.servos:
                    try:
                        servo.write_address(self.gripper.config.reg_torque_enable, [0])
                    except:
                        pass
                        
            except Exception as e:
                self.logger.warning(f"Hardware shutdown was incomplete: {e}")
            finally:
                # 3. Handle the specific USB2Dynamixel port closure
                if self.connection:
                    try:
                        if hasattr(self.connection, 'port') and hasattr(self.connection.port, 'close'):
                            self.connection.port.close()
                            self.logger.info("Serial port closed via .port.close()")
                        elif hasattr(self.connection, 'close'):
                            self.connection.close()
                            self.logger.info("Connection closed via .close()")
                    except Exception as e:
                        self.logger.debug(f"Port closure handled by OS or library: {e}")
                    finally:
                        # Ensure the object is cleared so it can't be reused
                        self.connection = None

        self.logger.info("Driver shutdown complete. System ready for restart.")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Corrected EZGripper DDS Driver")
    parser.add_argument("--side", required=True, choices=["left", "right"],
                       help="Gripper side (left/right)")
    parser.add_argument("--dev", default=None,
                       help="EZGripper device path (auto-discover if not specified)")
    parser.add_argument("--domain", type=int, default=0,
                       help="DDS domain")
    parser.add_argument("--no-calibrate", action="store_true",
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
    
    # Calibrate by default unless --no-calibrate is specified
    if not args.no_calibrate:
        driver.calibrate()
        print("Calibration completed. Starting DDS driver...")
    
    # Normal DDS operation mode
    try:
        driver.run()
    except KeyboardInterrupt:
        pass
    finally:
        driver.shutdown()


if __name__ == "__main__":
    main()
