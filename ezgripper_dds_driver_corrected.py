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

# Set CYCLONEDDS_HOME before importing cyclonedds
os.environ['CYCLONEDDS_HOME'] = '/opt/cyclonedds-0.10.2'

from dataclasses import dataclass, field

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


class CorrectedEZGripperDriver:
    """Corrected EZGripper DDS Driver"""
    
    def __init__(self, side: str, device: str = "/dev/ttyUSB0", domain: int = 0, calibration_file: str = None):
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
        self.last_cmd_time = time.time()
        
        # DDS state
        self.participant = None
        self.cmd_reader = None
        self.state_writer = None
        
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
        """Load calibration offset from file"""
        try:
            if os.path.exists(self.calibration_file):
                with open(self.calibration_file, 'r') as f:
                    zero_pos = int(f.read().strip())
                    self.gripper.zero_positions[0] = zero_pos
                    self.is_calibrated = True
                    self.logger.info(f"Loaded calibration: zero_position={zero_pos}")
            else:
                self.logger.warning("No calibration file found - gripper needs calibration")
        except Exception as e:
            self.logger.error(f"Failed to load calibration: {e}")
    
    def _save_calibration(self):
        """Save calibration offset to file"""
        try:
            with open(self.calibration_file, 'w') as f:
                f.write(str(self.gripper.zero_positions[0]))
            self.logger.info(f"Saved calibration: zero_position={self.gripper.zero_positions[0]}")
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
    
    def process_commands(self):
        """Process incoming DDS commands"""
        samples = self.cmd_reader.take(N=1)
        
        if samples:
            self.logger.debug(f"Received {len(samples)} samples")
        
        for sample in samples:
            if sample and hasattr(sample, 'cmds') and sample.cmds and len(sample.cmds) > 0:
                motor_cmd = sample.cmds[0]
                
                # Convert Dex1 command to gripper parameters
                target_position = self.dex1_to_ezgripper(motor_cmd.q)
                requested_effort = self.tau_to_effort_pct(motor_cmd.tau)
                
                # Use appropriate effort for position
                actual_effort = min(requested_effort, self.get_appropriate_effort(target_position))
                
                # Execute command
                self.gripper.goto_position(target_position, actual_effort)
                
                # Update state
                self.current_position_pct = target_position
                self.current_effort_pct = actual_effort
                self.last_cmd_time = time.time()
                
                # Log command
                if motor_cmd.q <= 0.1:
                    mode = "CLOSE"
                elif motor_cmd.q >= 6.0:
                    mode = "OPEN"
                else:
                    mode = f"POSITION {target_position:.1f}%"
                
                self.logger.info(f"Executed: {mode} (q={motor_cmd.q:.3f}, tau={motor_cmd.tau:.3f})")
    
    def publish_state(self):
        """Publish current gripper state"""
        try:
            # Get actual position from hardware
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
    
    def run(self):
        """Main control loop"""
        self.logger.info("Starting corrected EZGripper driver...")
        
        try:
            while True:
                # Process incoming DDS commands
                self.process_commands()
                
                # Publish state at 10Hz
                self.publish_state()
                
                time.sleep(0.1)  # 10 Hz loop
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down corrected EZGripper driver...")
        except Exception as e:
            self.logger.error(f"Driver error: {e}")
    
    def shutdown(self):
        """Clean shutdown"""
        self.logger.info("Shutting down hardware...")
        if self.gripper:
            self.gripper.goto_position(50.0, 30.0)
            time.sleep(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Corrected EZGripper DDS Driver")
    parser.add_argument("--side", required=True, choices=["left", "right"],
                       help="Gripper side (left/right)")
    parser.add_argument("--dev", default="/dev/ttyUSB0",
                       help="EZGripper device path")
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
    
    # Create and run driver
    driver = CorrectedEZGripperDriver(
        side=args.side,
        device=args.dev,
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
