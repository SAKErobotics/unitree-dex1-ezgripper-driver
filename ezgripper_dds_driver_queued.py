#!/usr/bin/env python3
"""
EZGripper DDS Driver with Command Queue and Asynchronous Status

Key improvements:
1. 1-deep command queue (keeps latest, drops old)
2. Asynchronous status publishing (non-blocking)
3. Rate limiting on command execution
4. Separate command processing from hardware execution
"""

import time
import math
import argparse
import logging
import sys
import os
import threading
from queue import Queue, Empty
from dataclasses import dataclass, field

# Set CYCLONEDDS_HOME before importing cyclonedds
os.environ['CYCLONEDDS_HOME'] = '/opt/cyclonedds-0.10.2'

from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.sub import DataReader
from cyclonedds.pub import DataWriter
from cyclonedds.qos import Qos, Policy

# Import unitree_sdk2py message types
sys.path.insert(0, '/home/kavi/CascadeProjects/unitree_sdk2_python')
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmd_, MotorCmds_, MotorState_, MotorStates_

# Minimal libezgripper imports
from libezgripper import create_connection, Gripper


@dataclass
class GripperCommand:
    """Queued gripper command"""
    position_pct: float
    effort_pct: float
    timestamp: float
    q_radians: float
    tau: float


class EZGripperDriverWithQueue:
    """EZGripper DDS Driver with command queue and async status"""
    
    def __init__(self, side: str, device: str = "/dev/ttyUSB0", domain: int = 0, 
                 calibration_file: str = None, command_rate_limit: float = 20.0):
        self.side = side
        self.device = device
        self.domain = domain
        self.calibration_file = calibration_file or f"/tmp/ezgripper_{side}_calibration.txt"
        self.command_rate_limit = command_rate_limit  # Max commands per second
        
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
        self.last_command_execute_time = 0.0
        self.command_count = 0.0
        
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
        self.status_update_interval = 0.05  # 20Hz status updates
        
        # Initialize
        self._initialize_hardware()
        self._load_calibration()
        self._setup_dds()
        
        self.logger.info(f"Queued EZGripper driver ready: {side} side")
    
    def _initialize_hardware(self):
        """Initialize hardware connection"""
        self.logger.info(f"Connecting to EZGripper on {self.device}")
        
        try:
            self.connection = create_connection(dev_name=self.device, baudrate=57600)
            self.gripper = Gripper(self.connection, f'queued_{self.side}', [1])
            
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
        """Calibration on command"""
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
        """Convert Dex1 torque to gripper effort"""
        return 50.0  # Fixed 50% effort for XR Teleoperate
    
    def get_appropriate_effort(self, position_pct: float) -> float:
        """Get appropriate effort for different positions"""
        if position_pct <= 5.0 or position_pct >= 95.0:
            return 40.0  # Lower effort at extremes
        else:
            return 50.0  # Standard effort
    
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
        """Execute queued command with rate limiting"""
        # Check rate limit
        time_since_last = time.time() - self.last_command_execute_time
        min_interval = 1.0 / self.command_rate_limit
        
        if time_since_last < min_interval:
            return  # Rate limited
        
        # Get command from queue (non-blocking)
        try:
            cmd = self.command_queue.get_nowait()
            self.current_command = cmd
            
            # Execute command
            self.gripper.goto_position(cmd.position_pct, cmd.effort_pct)
            
            # Update state
            self.current_position_pct = cmd.position_pct
            self.current_effort_pct = cmd.effort_pct
            self.last_command_execute_time = time.time()
            self.command_count += 1.0
            
            # Log command
            if cmd.q_radians <= 0.1:
                mode = "CLOSE"
            elif cmd.q_radians >= 6.0:
                mode = "OPEN"
            else:
                mode = f"POSITION {cmd.position_pct:.1f}%"
            
            self.logger.info(f"Executed: {mode} (q={cmd.q_radians:.3f}, tau={cmd.tau:.3f})")
            
        except Empty:
            # No command in queue
            pass
        except Exception as e:
            self.logger.error(f"Command execution failed: {e}")
    
    def publish_state_async(self):
        """Publish current gripper state (non-blocking, runs in separate thread)"""
        while self.running:
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
            
            # Sleep for status update interval
            time.sleep(self.status_update_interval)
    
    def run(self):
        """Main control loop"""
        self.logger.info("Starting queued EZGripper driver...")
        
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
            self.logger.info("Shutting down queued EZGripper driver...")
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
    parser = argparse.ArgumentParser(description="Queued EZGripper DDS Driver")
    parser.add_argument("--side", required=True, choices=["left", "right"],
                       help="Gripper side (left/right)")
    parser.add_argument("--dev", default="/dev/ttyUSB0",
                       help="EZGripper device path")
    parser.add_argument("--domain", type=int, default=0,
                       help="DDS domain")
    parser.add_argument("--calibrate", action="store_true",
                       help="Calibrate on startup")
    parser.add_argument("--command-rate-limit", type=float, default=20.0,
                       help="Max commands per second (default: 20)")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run driver
    driver = EZGripperDriverWithQueue(
        side=args.side,
        device=args.dev,
        domain=args.domain,
        command_rate_limit=args.command_rate_limit
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
