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

os.environ['CYCLONEDDS_HOME'] = '/opt/cyclonedds-0.10.2'

from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.sub import DataReader
from cyclonedds.pub import DataWriter

sys.path.insert(0, '/home/kavi/CascadeProjects/unitree_sdk2_python')
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmd_, MotorCmds_, MotorState_, MotorStates_


class Dex1DDSInterface:
    """
    DDS interface for Dex1 hand communication.
    
    Handles all DDS communication without direct hardware access.
    Publishes cached state for fast response.
    """
    
    # Dex1 hand position range (radians)
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
        cmd_topic = Topic(self.participant, cmd_topic_name, MotorCmds_)
        state_topic = Topic(self.participant, state_topic_name, MotorStates_)
        
        # Create reader and writer
        self.cmd_reader = DataReader(self.participant, cmd_topic)
        self.state_writer = DataWriter(self.participant, state_topic)
        
        self.logger.info(f"DDS topics: {cmd_topic_name} → {state_topic_name}")
    
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
        """Receive latest command from DDS, return (position_pct, effort_pct)"""
        try:
            samples = self.cmd_reader.take(N=10)
            
            if samples:
                latest_sample = samples[-1]
                
                if latest_sample and hasattr(latest_sample, 'cmds') and latest_sample.cmds:
                    motor_cmd = latest_sample.cmds[0]
                    
                    # Convert position
                    position_pct = self.dex1_to_ezgripper(motor_cmd.q)
                    
                    # Convert effort (50% default, 40% at extremes)
                    if position_pct <= 5.0 or position_pct >= 95.0:
                        effort_pct = 40.0
                    else:
                        effort_pct = 50.0
                    
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
        """Publish cached state to DDS (fast, no hardware access)"""
        try:
            current_q = self.ezgripper_to_dex1(self.cached_position_pct)
            current_tau = self.cached_effort_pct / 10.0
            
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
            
            # Publish
            self.state_writer.write(motor_states)
            
        except Exception as e:
            self.logger.error(f"State publish failed: {e}")
    
    def shutdown(self):
        """Clean shutdown of DDS interface"""
        pass  # DDS cleanup happens automatically
