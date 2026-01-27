#!/usr/bin/env python3
"""
Dex1 DDS Interface Module - Handles real G1 Dex1 hand messages

Pure protocol translator between G1 Dex1 DDS and EZGripper commands.
Handles the proper HandCmd_/HandState_ message structure from the real G1 robot.
"""

import time
import logging
import os
import sys

os.environ['CYCLONEDDS_HOME'] = os.path.expanduser('~/CascadeProjects/cyclonedds/install')

from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.sub import DataReader
from cyclonedds.pub import DataWriter

# Use proper Dex1 hand messages
from unitree_sdk2py.idl.default import (
    HGHandCmd_, HGHandState_, HGMotorCmd_, HGMotorState_,
    HGPressSensorState_, HGIMUState_
)


class Dex1DDSInterface:
    """
    DDS interface for G1 Dex1 hand communication.
    
    Handles real G1 Dex1 hand messages (HandCmd_/HandState_) and converts
    them to EZGripper commands.
    """
    
    # Dex1 hand motor configuration
    LEFT_GRIPPER_MOTORS = [1, 2]  # Left gripper finger motors
    RIGHT_GRIPPER_MOTORS = [3, 4]  # Right gripper finger motors
    
    # Dex1 hand position range
    DEX1_OPEN = 6.28    # Fully open (radians)
    DEX1_CLOSE = 0.0    # Fully closed (radians)
    
    def __init__(self, side: str, domain: int = 0):
        """
        Initialize Dex1 DDS interface.
        
        Args:
            side: Gripper side ('left' or 'right')
            domain: DDS domain ID
        """
        self.side = side
        self.domain = domain
        self.logger = logging.getLogger(f"dex1_dds_interface_{side}")
        
        # Cached state for fast publishing
        self.cached_position_pct = 50.0
        self.cached_effort_pct = 30.0
        
        # DDS components
        self.participant = None
        self.cmd_reader = None
        self.state_writer = None
        
        # Motor IDs for this side
        self.motor_ids = self.LEFT_GRIPPER_MOTORS if side == 'left' else self.RIGHT_GRIPPER_MOTORS
        
        # Initialize DDS
        self._initialize_dds()
    
    def _initialize_dds(self):
        """Initialize DDS components for Dex1 hand topics"""
        try:
            # Create domain participant
            self.participant = DomainParticipant(self.domain)
            
            # Dex1 hand topic naming convention (official Unitree format)
            if self.side == 'left':
                cmd_topic_name = "rt/dex1/left/cmd"
                state_topic_name = "rt/dex1/left/state"
            else:
                cmd_topic_name = "rt/dex1/right/cmd"
                state_topic_name = "rt/dex1/right/state"
            
            # Create topics and readers/writers
            cmd_topic = Topic(self.participant, cmd_topic_name, HGHandCmd_)
            state_topic = Topic(self.participant, state_topic_name, HGHandState_)
            
            self.cmd_reader = DataReader(self.participant, cmd_topic)
            self.state_writer = DataWriter(self.participant, state_topic)
            
            self.logger.info(f"Dex1 DDS topics: {cmd_topic_name} → {state_topic_name}")
            self.logger.info(f"Motor IDs for {self.side}: {self.motor_ids}")
            
        except Exception as e:
            self.logger.error(f"DDS initialization failed: {e}")
            raise
    
    def dex1_to_ezgripper(self, q_radians: float) -> float:
        """
        Convert Dex1 position (radians) to EZGripper percentage.
        
        Args:
            q_radians: Dex1 position in radians (0=close, 6.28=open)
            
        Returns:
            EZGripper position percentage (0-100)
        """
        # Clamp input
        q_clamped = max(self.DEX1_CLOSE, min(self.DEX1_OPEN, q_radians))
        
        # Linear mapping
        pct = (q_clamped - self.DEX1_CLOSE) / (self.DEX1_OPEN - self.DEX1_CLOSE) * 100.0
        
        return pct
    
    def ezgripper_to_dex1(self, position_pct: float) -> float:
        """
        Convert EZGripper percentage to Dex1 position (radians).
        
        Args:
            position_pct: EZGripper position percentage (0-100)
            
        Returns:
            Dex1 position in radians
        """
        # Clamp input
        pct_clamped = max(0.0, min(100.0, position_pct))
        
        # Linear mapping
        q = self.DEX1_CLOSE + (pct_clamped / 100.0) * (self.DEX1_OPEN - self.DEX1_CLOSE)
        
        return q
    
    def receive_command(self):
        """
        Receive latest command from G1 Dex1 DDS, return (position_pct, effort_pct)
        
        Handles the real HandCmd_ message structure with multiple motors.
        """
        try:
            # DDS already maintains 1-depth queue by default (KEEP_LAST, depth=1)
            samples = self.cmd_reader.take()
            
            if samples and len(samples) > 0:
                hand_cmd = samples[0]
                
                # Extract motor commands for our gripper side
                if hasattr(hand_cmd, 'motor_cmd') and hand_cmd.motor_cmd:
                    # Find the first motor command for our side
                    # (For EZGripper, we use the first motor's position)
                    target_motor_cmd = None
                    
                    for motor_cmd in hand_cmd.motor_cmd:
                        if motor_cmd.id in self.motor_ids:
                            target_motor_cmd = motor_cmd
                            break
                    
                    if target_motor_cmd:
                        # Convert position
                        position_pct = self.dex1_to_ezgripper(target_motor_cmd.q)
                        
                        # Convert effort - fixed at 100% (ignore tau from G1)
                        effort_pct = 100.0
                        
                        # Log G1 Dex1 input command
                        self.logger.debug(f"G1 Dex1 INPUT: motor{target_motor_cmd.id} q={target_motor_cmd.q:.3f} rad → {position_pct:.1f}%")
                        
                        return (position_pct, effort_pct)
                    else:
                        self.logger.warning(f"No motor command found for side {self.side} in {len(hand_cmd.motor_cmd)} motors")
                        return None
            
            return None
            
        except Exception as e:
            self.logger.error(f"G1 Dex1 command receive failed: {e}")
            return None
    
    def update_cached_state(self, position_pct: float, effort_pct: float):
        """Update cached state (called by hardware controller)"""
        self.cached_position_pct = position_pct
        self.cached_effort_pct = effort_pct
    
    def publish_state(self):
        """
        Publish cached state to G1 Dex1 DDS format (fast, no hardware access)
        
        Creates proper HandState_ message with motor states, sensors, and power data.
        """
        try:
            # Create proper G1 HandState_ message
            hand_state = HGHandState_()
            
            # Create motor states for our gripper motors
            motor_states = []
            for motor_id in self.motor_ids:
                motor_state = HGMotorState_()
                motor_state.id = motor_id
                motor_state.q = self.ezgripper_to_dex1(self.cached_position_pct)
                motor_state.dq = 0.0  # No velocity (EZGripper doesn't provide it)
                motor_state.ddq = 0.0  # No acceleration
                motor_state.tau_est = 0.0  # No torque estimate
                motor_state.q_raw = motor_state.q  # Same as processed
                motor_state.dq_raw = 0.0
                motor_state.ddq_raw = 0.0
                motor_state.temperature = 25.0  # Normal temperature estimate
                motor_state.motor_error = 0  # No error
                
                motor_states.append(motor_state)
            
            # Set motor states
            hand_state.motor_state = motor_states
            
            # Create placeholder press sensor states (EZGripper doesn't have pressure sensors)
            press_sensor_states = []
            for i in range(len(self.motor_ids)):
                press_state = HGPressSensorState_()
                press_state.press = [0, 0]  # No pressure sensors on EZGripper
                press_sensor_states.append(press_state)
            hand_state.press_sensor_state = press_sensor_states
            
            # Create placeholder IMU state (EZGripper doesn't have IMU)
            imu_state = HGIMUState_()
            imu_state.quaternion = [0, 0, 0, 1]  # Identity quaternion
            imu_state.gyroscope = [0, 0, 0]  # No rotation
            imu_state.accelerometer = [0, 0, -9.81]  # Gravity only
            imu_state.rpy = [0, 0, 0]  # No rotation
            imu_state.temperature = 25.0
            hand_state.imu_state = imu_state
            
            # Power estimates for EZGripper
            hand_state.power_v = 12.0  # 12V system
            hand_state.power_a = self.cached_effort_pct * 0.1  # Rough current estimate
            hand_state.system_v = 12.0  # Same as power
            
            # Publish the hand state
            self.state_writer.write(hand_state)
            
        except Exception as e:
            self.logger.error(f"G1 Dex1 state publish failed: {e}")
    
    def shutdown(self):
        """Shutdown DDS components"""
        try:
            # Note: CycloneDDS handles cleanup automatically when objects go out of scope
            self.logger.info("Dex1 DDS interface shutdown complete")
        except Exception as e:
            self.logger.error(f"DDS shutdown error: {e}")


def main():
    """Test function for Dex1 DDS interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Dex1 DDS Interface')
    parser.add_argument('--side', choices=['left', 'right'], required=True,
                      help='Gripper side (left or right)')
    parser.add_argument('--domain', type=int, default=0,
                      help='DDS domain ID (default: 0)')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.DEBUG, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Test the interface
    interface = Dex1DDSInterface(args.side, args.domain)
    
    print(f"Testing G1 Dex1 DDS interface for {args.side} gripper...")
    print("Waiting for commands from G1...")
    
    try:
        while True:
            cmd = interface.receive_command()
            if cmd:
                pos, effort = cmd
                print(f"Received: position={pos:.1f}%, effort={effort:.1f}%")
                interface.update_cached_state(pos, effort)
                interface.publish_state()
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping test...")
    finally:
        interface.shutdown()


if __name__ == "__main__":
    main()
