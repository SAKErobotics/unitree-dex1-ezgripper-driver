#!/usr/bin/env python3
"""
Mock DDS Commander - Simulates XR Teleoperate

Publishes DDS commands that slowly oscillate from full open to full close.
Used for testing gripper driver without actual XR teleoperate system.
"""

import time
import argparse
import logging
import os
import sys
import math

os.environ['CYCLONEDDS_HOME'] = os.path.expanduser('~/CascadeProjects/cyclonedds/install')

from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.pub import DataWriter

sys.path.insert(0, os.path.expanduser('~/CascadeProjects/unitree_sdk2_python'))
from unitree_sdk2py.idl.default import HGHandCmd_, HGMotorCmd_


class MockDDSCommander:
    """Mock DDS commander that simulates XR teleoperate with slow oscillation"""
    
    # Dex1 hand motor configuration (single motor per hand)
    LEFT_GRIPPER_MOTOR = 1   # Left gripper motor
    RIGHT_GRIPPER_MOTOR = 2  # Right gripper motor
    
    # Dex1 hand position range
    DEX1_OPEN = 6.28    # Fully open (radians)
    DEX1_CLOSE = 0.0    # Fully closed (radians)
    
    def __init__(self, side: str, domain: int = 0, period: float = 5.0):
        """
        Initialize mock commander.
        
        Args:
            side: Gripper side ('left' or 'right')
            domain: DDS domain ID
            period: Cycle period in seconds (default 5s = 1s close, 2s hold, 1s open, 1s hold)
        """
        self.side = side
        self.domain = domain
        self.period = period
        self.logger = logging.getLogger(f"mock_commander_{side}")
        
        # Setup DDS
        self.participant = DomainParticipant(domain)
        cmd_topic_name = f"rt/dex1/{side}/cmd"
        cmd_topic = Topic(self.participant, cmd_topic_name, HGHandCmd_)
        self.cmd_writer = DataWriter(self.participant, cmd_topic)
        
        # Motor ID for this side
        self.motor_id = self.LEFT_GRIPPER_MOTOR if side == 'left' else self.RIGHT_GRIPPER_MOTOR
        
        self.logger.info(f"Mock commander ready: {side} side, period={period}s")
        self.logger.info(f"Publishing to: {cmd_topic_name}")
        self.logger.info(f"Motor ID: {self.motor_id}")
    
    def run(self):
        """Run continuous oscillation loop"""
        self.logger.info("Starting mock commander - fast close, 2s hold, then open...")
        
        start_time = time.time()
        
        try:
            while True:
                elapsed = time.time() - start_time
                
                # Cycle: close (1s) -> hold (2s) -> open (1s) -> hold (1s) = 5s total
                cycle_time = elapsed % self.period
                
                # Define phases
                close_duration = 1.0   # 1 second to close
                hold_closed = 2.0      # 2 seconds holding closed
                open_duration = 1.0    # 1 second to open
                hold_open = self.period - close_duration - hold_closed - open_duration  # Rest of period
                
                if cycle_time < close_duration:
                    # Closing phase: 100% -> 0%
                    normalized = 1.0 - (cycle_time / close_duration)
                elif cycle_time < close_duration + hold_closed:
                    # Hold closed phase: 0%
                    normalized = 0.0
                elif cycle_time < close_duration + hold_closed + open_duration:
                    # Opening phase: 0% -> 100%
                    open_progress = (cycle_time - close_duration - hold_closed) / open_duration
                    normalized = open_progress
                else:
                    # Hold open phase: 100%
                    normalized = 1.0
                
                # Map to Dex1 range
                q = self.DEX1_CLOSE + normalized * (self.DEX1_OPEN - self.DEX1_CLOSE)
                
                # Create single motor command for Dex1 hand
                motor_cmd = HGMotorCmd_(
                    mode=0,      # Position control mode
                    q=q,         # Position command
                    dq=0.0,      # Velocity command
                    tau=0.0,     # Torque command
                    kp=0.0,      # Position gain
                    kd=0.0,      # Damping gain
                    reserve=0    # Reserved field (uint32)
                )
                motor_cmd.id = self.motor_id
                
                # Create proper Dex1 HandCmd_ message with single motor
                hand_cmd = HGHandCmd_(
                    motor_cmd=[motor_cmd],  # Single motor in sequence
                    reserve=[0, 0, 0, 0]   # Reserved fields
                )
                
                self.cmd_writer.write(hand_cmd)
                
                # Log occasionally
                if int(elapsed * 10) % 10 == 0:  # Every 1 second
                    pct = normalized * 100
                    self.logger.info(f"Command: q={q:.3f} rad ({pct:.1f}%)")
                
                # Publish at 50Hz
                time.sleep(0.02)
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down mock commander...")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Mock DDS Commander for Testing")
    parser.add_argument("--side", required=True, choices=["left", "right"],
                       help="Gripper side (left/right)")
    parser.add_argument("--domain", type=int, default=0,
                       help="DDS domain")
    parser.add_argument("--period", type=float, default=5.0,
                       help="Cycle period in seconds (default: 5s = 1s close, 2s hold, 1s open, 1s hold)")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run mock commander
    commander = MockDDSCommander(
        side=args.side,
        domain=args.domain,
        period=args.period
    )
    
    commander.run()


if __name__ == "__main__":
    main()
