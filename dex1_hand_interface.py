"""
Dex1 Hand DDS Interface

This module provides a clean abstraction for controlling Unitree Dex1-1 grippers via DDS.
It mimics the Unitree G1 hand control interface, allowing test code and applications
to command grippers without directly managing DDS topics and message types.

Usage:
    # Create interface for left gripper
    hand = Dex1HandInterface(side='left', domain=0)
    
    # Command gripper to 50% open
    hand.set_position(50.0)  # Percentage: 0-100
    
    # Get current state
    state = hand.get_state()
    print(f"Position: {state['position_pct']:.1f}%")
    print(f"Force: {state['force']:.2f} N")
"""

import sys
import time
import logging
from dataclasses import dataclass
from typing import Optional, Dict

# CycloneDDS imports
from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.sub import DataReader
from cyclonedds.pub import DataWriter

# Unitree message types
sys.path.insert(0, '/home/kavi/CascadeProjects/unitree_sdk2_python')
from unitree_sdk2py.idl.default import HGHandCmd_, HGMotorCmd_, HGHandState_, HGMotorState_


@dataclass
class Dex1State:
    """Dex1 hand state"""
    position_pct: float      # Position percentage (0-100)
    position_rad: float      # Position in radians (0-6.28)
    force: float             # Grip force (0-10 N)
    timestamp: float         # State timestamp


class Dex1HandInterface:
    """
    Dex1 Hand DDS Interface
    
    Provides a clean Python interface for commanding Unitree Dex1-1 grippers.
    Matches the Unitree G1 hand control interface.
    """
    
    # Motor IDs
    LEFT_MOTOR_ID = 1
    RIGHT_MOTOR_ID = 2
    
    # Position limits
    MIN_POSITION_RAD = 0.0      # Fully closed
    MAX_POSITION_RAD = 6.28     # Fully open (2π)
    
    def __init__(self, side: str, domain: int = 0, rate_hz: float = 200.0):
        """
        Initialize Dex1 hand interface
        
        Args:
            side: 'left' or 'right'
            domain: DDS domain ID
            rate_hz: Command publishing rate (default 200 Hz for G1 XR compatibility)
        """
        if side not in ['left', 'right']:
            raise ValueError(f"Invalid side: {side}. Must be 'left' or 'right'")
        
        self.side = side
        self.domain = domain
        self.rate_hz = rate_hz
        self.motor_id = self.LEFT_MOTOR_ID if side == 'left' else self.RIGHT_MOTOR_ID
        
        self.logger = logging.getLogger(f"dex1_{side}")
        
        # DDS setup
        self._setup_dds()
        
        # State tracking
        self.last_state: Optional[Dex1State] = None
        
        self.logger.info(f"Dex1 hand interface ready: {side} side (motor ID {self.motor_id})")
    
    def _setup_dds(self):
        """Setup DDS participant, topics, and readers/writers"""
        # Create DDS participant
        self.participant = DomainParticipant(self.domain)
        
        # Topic names (match Unitree convention)
        cmd_topic_name = f"rt/dex1/{self.side}/cmd"
        state_topic_name = f"rt/dex1/{self.side}/state"
        
        # Create topics
        self.cmd_topic = Topic(self.participant, cmd_topic_name, HGHandCmd_)
        self.state_topic = Topic(self.participant, state_topic_name, HGHandState_)
        
        # Create writer and reader
        self.cmd_writer = DataWriter(self.participant, self.cmd_topic)
        self.state_reader = DataReader(self.participant, self.state_topic)
        
        self.logger.debug(f"DDS topics: {cmd_topic_name} (cmd), {state_topic_name} (state)")
    
    def set_position(self, position_pct: float, blocking: bool = False, timeout: float = 2.0):
        """
        Command gripper to target position
        
        Args:
            position_pct: Target position percentage (0=closed, 100=open)
            blocking: If True, wait until position is reached
            timeout: Maximum time to wait if blocking (seconds)
        """
        # Clamp position
        position_pct = max(0.0, min(100.0, position_pct))
        
        # Convert to radians
        position_rad = (position_pct / 100.0) * self.MAX_POSITION_RAD
        
        # Create motor command
        motor_cmd = HGMotorCmd_(
            mode=0,           # Position control mode
            q=position_rad,   # Target position
            dq=0.0,
            tau=0.0,
            kp=0.0,
            kd=0.0,
            reserve=0
        )
        motor_cmd.id = self.motor_id
        
        # Create hand command
        hand_cmd = HGHandCmd_(
            motor_cmd=[motor_cmd],
            reserve=[0, 0, 0, 0]
        )
        
        # Publish command
        self.cmd_writer.write(hand_cmd)
        
        self.logger.debug(f"Command sent: {position_pct:.1f}% ({position_rad:.3f} rad)")
        
        # Wait for position if blocking
        if blocking:
            start_time = time.time()
            while time.time() - start_time < timeout:
                state = self.get_state()
                if state and abs(state.position_pct - position_pct) < 5.0:
                    return True
                time.sleep(0.05)
            return False
    
    def set_position_rad(self, position_rad: float):
        """
        Command gripper to target position in radians
        
        Args:
            position_rad: Target position in radians (0-6.28)
        """
        position_pct = (position_rad / self.MAX_POSITION_RAD) * 100.0
        self.set_position(position_pct)
    
    def open(self, blocking: bool = False):
        """Open gripper fully (100%)"""
        return self.set_position(100.0, blocking=blocking)
    
    def close(self, blocking: bool = False):
        """Close gripper fully (0%)"""
        return self.set_position(0.0, blocking=blocking)
    
    def get_state(self) -> Optional[Dex1State]:
        """
        Get current gripper state
        
        Returns:
            Dex1State object or None if no state available
        """
        try:
            samples = self.state_reader.take(N=1)
            
            if samples:
                hand_state = samples[-1]
                
                if hand_state and hand_state.motor_state and len(hand_state.motor_state) > 0:
                    motor_state = hand_state.motor_state[0]
                    
                    # Convert to percentage
                    position_pct = (motor_state.q / self.MAX_POSITION_RAD) * 100.0
                    
                    # Create state object
                    state = Dex1State(
                        position_pct=position_pct,
                        position_rad=motor_state.q,
                        force=motor_state.tau_est * 10.0,  # Convert back to Newtons
                        timestamp=time.time()
                    )
                    
                    self.last_state = state
                    return state
            
            # Return last known state if no new data
            return self.last_state
            
        except Exception as e:
            self.logger.error(f"Failed to read state: {e}")
            return self.last_state
    
    def get_position(self) -> Optional[float]:
        """Get current position percentage (0-100)"""
        state = self.get_state()
        return state.position_pct if state else None
    
    def get_force(self) -> Optional[float]:
        """Get current grip force (Newtons)"""
        state = self.get_state()
        return state.force if state else None
    
    def is_gripping(self, threshold: float = 1.0) -> bool:
        """
        Check if gripper is gripping an object
        
        Args:
            threshold: Force threshold in Newtons
        
        Returns:
            True if grip force exceeds threshold
        """
        force = self.get_force()
        return force is not None and force > threshold
    
    def shutdown(self):
        """Clean shutdown of DDS interface"""
        self.logger.info("Shutting down Dex1 hand interface")
        # DDS cleanup happens automatically


def main():
    """Example usage"""
    logging.basicConfig(level=logging.INFO)
    
    # Create interface for left gripper
    hand = Dex1HandInterface(side='left')
    
    print("Testing Dex1 hand interface...")
    
    # Open gripper
    print("Opening gripper...")
    hand.open(blocking=True)
    time.sleep(1)
    
    # Close gripper
    print("Closing gripper...")
    hand.close(blocking=True)
    time.sleep(1)
    
    # Move to 50%
    print("Moving to 50%...")
    hand.set_position(50.0, blocking=True)
    time.sleep(1)
    
    # Read state
    state = hand.get_state()
    if state:
        print(f"Position: {state.position_pct:.1f}%")
        print(f"Force: {state.force:.2f} N")
    
    hand.shutdown()


if __name__ == "__main__":
    main()
