#!/usr/bin/env python3
"""
DDS Interface Module for Dex1 Hand Communication

Handles DDS communication with Dex1 hand protocol:
- Receives motor commands from DDS
- Publishes motor states to DDS
- Converts between Dex1 units and gripper percentages
- Caches last known state for fast publishing
- Last-write-wins command handling
"""

import time
import logging
import os
from dataclasses import dataclass
from typing import Optional, Callable

# Set CYCLONEDDS_HOME before importing cyclonedds
os.environ['CYCLONEDDS_HOME'] = '/opt/cyclonedds-0.10.2'

from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.sub import DataReader
from cyclonedds.pub import DataWriter

import sys
sys.path.insert(0, '/home/kavi/CascadeProjects/unitree_sdk2_python')
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmd_, MotorCmds_, MotorState_, MotorStates_


@dataclass
class GripperCommand:
    """Gripper command in percentage units"""
    position_pct: float  # 0-100%
    effort_pct: float    # 0-100%
    timestamp: float
    q_radians: float     # Original Dex1 q value
    tau: float          # Original Dex1 tau value


@dataclass
class GripperState:
    """Gripper state in percentage units"""
    position_pct: float  # 0-100%
    effort_pct: float    # 0-100%
    timestamp: float


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
        
        # Cached state (for fast publishing without hardware access)
        self.cached_state = GripperState(
            position_pct=50.0,
            effort_pct=30.0,
            timestamp=time.time()
        )
        
        # Latest command (last-write-wins)
        self.latest_command: Optional[GripperCommand] = None
        
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
    
    def tau_to_effort_pct(self, tau: float) -> float:
        """
        Convert Dex1 tau to effort percentage.
        
        For preliminary XR Teleoperate compatibility: always use 50% effort.
        
        Args:
            tau: Dex1 torque value
            
        Returns:
            Effort percentage (0-100)
        """
        return 50.0
    
    def receive_command(self) -> Optional[GripperCommand]:
        """
        Receive latest command from DDS (non-blocking, last-write-wins).
        
        Returns:
            Latest GripperCommand if available, None otherwise
        """
        try:
            samples = self.cmd_reader.take(N=10)
            
            if samples:
                # Last-write-wins: keep only the latest command
                latest_sample = samples[-1]
                
                if latest_sample and hasattr(latest_sample, 'cmds') and latest_sample.cmds and len(latest_sample.cmds) > 0:
                    motor_cmd = latest_sample.cmds[0]
                    
                    # Convert to gripper units
                    target_position = self.dex1_to_ezgripper(motor_cmd.q)
                    requested_effort = self.tau_to_effort_pct(motor_cmd.tau)
                    
                    # Apply effort limits based on position
                    if target_position <= 5.0 or target_position >= 95.0:
                        actual_effort = 40.0  # Lower effort at extremes
                    else:
                        actual_effort = 50.0  # Standard effort
                    
                    actual_effort = min(requested_effort, actual_effort)
                    
                    # Create command
                    cmd = GripperCommand(
                        position_pct=target_position,
                        effort_pct=actual_effort,
                        timestamp=time.time(),
                        q_radians=motor_cmd.q,
                        tau=motor_cmd.tau
                    )
                    
                    # Store as latest command
                    self.latest_command = cmd
                    return cmd
            
            return None
            
        except Exception as e:
            self.logger.error(f"Command receive failed: {e}")
            return None
    
    def update_cached_state(self, position_pct: float, effort_pct: float):
        """
        Update cached state (called by hardware controller).
        
        Args:
            position_pct: Current position percentage
            effort_pct: Current effort percentage
        """
        self.cached_state = GripperState(
            position_pct=position_pct,
            effort_pct=effort_pct,
            timestamp=time.time()
        )
    
    def publish_state(self):
        """
        Publish cached state to DDS (fast, no hardware access).
        """
        try:
            # Use cached state
            current_q = self.ezgripper_to_dex1(self.cached_state.position_pct)
            current_tau = self.cached_state.effort_pct / 10.0
            
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
    
    def get_latest_command(self) -> Optional[GripperCommand]:
        """
        Get the latest command without receiving new ones.
        
        Returns:
            Latest GripperCommand if available, None otherwise
        """
        return self.latest_command
    
    def shutdown(self):
        """Clean shutdown of DDS interface"""
        self.logger.info("Shutting down DDS interface...")
        # DDS cleanup happens automatically
