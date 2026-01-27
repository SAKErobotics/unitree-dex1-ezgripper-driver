#!/usr/bin/env python3
"""
DDS Interface Module for Dex1 Hand Communication

Pure protocol translator between Dex1 DDS and gripper commands.
No business logic - just unit conversion and buffering.
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

sys.path.insert(0, os.path.expanduser('~/CascadeProjects/unitree_sdk2_python'))
from unitree_sdk2py.idl.default import HGHandCmd_, HGHandState_, HGMotorCmd_, HGMotorState_


class Dex1DDSInterface:
    """
    DDS interface for Dex1 hand communication.
    
    Handles all DDS communication without direct hardware access.
    Publishes cached state for fast response.
    """
    
    # Dex1 hand motor configuration (single motor per hand)
    LEFT_GRIPPER_MOTOR = 1   # Left gripper motor
    RIGHT_GRIPPER_MOTOR = 2  # Right gripper motor
    
    # Dex1 hand position range
    DEX1_OPEN = 6.28    # Fully open
    DEX1_CLOSE = 0.0    # Fully closed
    
    # EZGripper position range (percentage)
    EZGRIPPER_OPEN = 100.0
    EZGRIPPER_CLOSE = 0.0
    
    def __init__(self, side: str, domain: int = 0):
        """
        Initialize DDS interface.
        
        Args:
            side: Gripper side ('left' or 'right')
            domain: DDS domain ID
        """
        self.side = side
        self.domain = domain
        self.logger = logging.getLogger(f"dds_interface_{side}")
        
        # Cached state for fast publishing
        self.cached_position_pct = 50.0
        self.cached_effort_pct = 30.0
        
        # Motor ID for this side
        self.motor_id = self.LEFT_GRIPPER_MOTOR if side == 'left' else self.RIGHT_GRIPPER_MOTOR
        
        # DDS components
        self.participant = None
        self.cmd_reader = None
        self.state_writer = None
        
        # Setup DDS
        self._setup_dds()
        
        self.logger.info(f"DDS interface ready: {side} side")
    
    def _setup_dds(self):
        """Setup DDS participant, topics, reader, and writer"""
        # Create participant
        self.participant = DomainParticipant(self.domain)
        
        # Topic names
        cmd_topic_name = f"rt/dex1/{self.side}/cmd"
        state_topic_name = f"rt/dex1/{self.side}/state"
        
        # Create topics
        cmd_topic = Topic(self.participant, cmd_topic_name, HGHandCmd_)
        state_topic = Topic(self.participant, state_topic_name, HGHandState_)
        
        # Create reader and writer
        self.cmd_reader = DataReader(self.participant, cmd_topic)
        self.state_writer = DataWriter(self.participant, state_topic)
        
        self.logger.info(f"DDS topics: {cmd_topic_name} → {state_topic_name}")
        self.logger.info(f"Motor ID for {self.side}: {self.motor_id}")
    
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
        """Receive latest command from G1 Dex1 DDS, return (position_pct, effort_pct)"""
        try:
            # DDS already maintains 1-depth queue by default (KEEP_LAST, depth=1)
            samples = self.cmd_reader.take()
            
            if samples and len(samples) > 0:
                hand_cmd = samples[0]
                
                # Extract motor command for our gripper side
                if hasattr(hand_cmd, 'motor_cmd') and hand_cmd.motor_cmd:
                    # Get the first motor command (Dex1 has single motor)
                    motor_cmd = hand_cmd.motor_cmd[0]
                    
                    # Convert position
                    position_pct = self.dex1_to_ezgripper(motor_cmd.q)
                    
                    # Convert effort - fixed at 100% (ignore tau from G1)
                    effort_pct = 100.0
                    
                    # Log G1 Dex1 input command
                    self.logger.debug(f"G1 Dex1 INPUT: q={motor_cmd.q:.3f} rad → {position_pct:.1f}%")
                    
                    return (position_pct, effort_pct)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Command receive failed: {e}")
            return None
    
    def update_cached_state(self, position_pct: float, effort_pct: float):
        """Update cached state (called by hardware controller)"""
        self.cached_position_pct = position_pct
        self.cached_effort_pct = effort_pct
    
    def publish_state(self):
        """Publish cached state to G1 Dex1 DDS format (fast, no hardware access)"""
        try:
            # Create motor state for Dex1 hand
            motor_state = HGMotorState_()
            motor_state.id = self.motor_id
            motor_state.q = self.ezgripper_to_dex1(self.cached_position_pct)
            motor_state.dq = 0.0
            motor_state.ddq = 0.0
            motor_state.tau_est = 0.0
            motor_state.q_raw = motor_state.q
            motor_state.dq_raw = 0.0
            motor_state.ddq_raw = 0.0
            motor_state.temperature = 25.0
            motor_state.motor_error = 0
            
            # Create HandState_ message (placeholder for other fields)
            hand_state = HGHandState_()
            hand_state.motor_state = [motor_state]
            hand_state.press_sensor_state = []  # No pressure sensors
            hand_state.imu_state = None  # No IMU
            hand_state.power_v = 12.0
            hand_state.power_a = self.cached_effort_pct * 0.1
            hand_state.system_v = 12.0
            
            # Publish
            self.state_writer.write(hand_state)
            
        except Exception as e:
            self.logger.error(f"State publish failed: {e}")
    
    def shutdown(self):
        """Clean shutdown of DDS interface"""
        pass  # DDS cleanup happens automatically
