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

os.environ['CYCLONEDDS_HOME'] = '/opt/cyclonedds-0.10.2'

from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.pub import DataWriter

sys.path.insert(0, '/home/kavi/CascadeProjects/unitree_sdk2_python')
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmd_, MotorCmds_


class MockDDSCommander:
    """Mock DDS commander that simulates XR teleoperate with slow oscillation"""
    
    # Dex1 hand position range
    DEX1_OPEN = 6.28    # Fully open (radians)
    DEX1_CLOSE = 0.0    # Fully closed (radians)
    
    def __init__(self, side: str, domain: int = 0, period: float = 10.0):
        """
        Initialize mock commander.
        
        Args:
            side: Gripper side ('left' or 'right')
            domain: DDS domain ID
            period: Oscillation period in seconds (default 10s = 5s open, 5s close)
        """
        self.side = side
        self.domain = domain
        self.period = period
        self.logger = logging.getLogger(f"mock_commander_{side}")
        
        # Setup DDS
        self.participant = DomainParticipant(domain)
        cmd_topic_name = f"rt/dex1/{side}/cmd"
        cmd_topic = Topic(self.participant, cmd_topic_name, MotorCmds_)
        self.cmd_writer = DataWriter(self.participant, cmd_topic)
        
        self.logger.info(f"Mock commander ready: {side} side, period={period}s")
        self.logger.info(f"Publishing to: {cmd_topic_name}")
    
    def run(self):
        """Run continuous oscillation loop"""
        self.logger.info("Starting mock commander - oscillating from open to close...")
        
        start_time = time.time()
        
        try:
            while True:
                elapsed = time.time() - start_time
                
                # Calculate position using sine wave for smooth oscillation
                # Period = full cycle time, so half period = open to close
                phase = (elapsed % self.period) / self.period  # 0 to 1
                
                # Sine wave: 0 -> 1 -> 0 (smooth acceleration/deceleration)
                normalized = (1 - math.cos(phase * 2 * math.pi)) / 2
                
                # Map to Dex1 range
                q = self.DEX1_CLOSE + normalized * (self.DEX1_OPEN - self.DEX1_CLOSE)
                
                # Create and publish command
                motor_cmd = MotorCmd_(
                    mode=0,
                    q=q,
                    dq=0.0,
                    tau=0.0,
                    kp=0.0,
                    kd=0.0
                )
                
                motor_cmds = MotorCmds_(cmds=[motor_cmd])
                self.cmd_writer.write(motor_cmds)
                
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
    parser.add_argument("--period", type=float, default=10.0,
                       help="Oscillation period in seconds (default: 10s)")
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
