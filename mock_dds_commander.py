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
import random

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
        
        # Phase 3 state tracking
        self.phase3_target = None
        self.phase3_last_update = 0
        self.phase3_current_pos = 1.0  # Start at open
        
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
        """Run 3-phase oscillation pattern"""
        self.logger.info("Starting 3-phase pattern: smooth(10s) -> random jumps(5s) -> point-to-point(5s)")
        
        start_time = time.time()
        random.seed(42)  # Reproducible random sequence
        
        try:
            while True:
                elapsed = time.time() - start_time
                
                # Total cycle: 20 seconds (10s + 5s + 5s)
                cycle_time = elapsed % 20.0
                
                # Phase 1: Smooth oscillation (0-10s)
                if cycle_time < 10.0:
                    phase = cycle_time / 10.0  # 0 to 1
                    if phase < 0.5:
                        normalized = phase * 2  # 0 to 1 (opening)
                    else:
                        normalized = 2 - phase * 2  # 1 to 0 (closing)
                    
                    if int(cycle_time) != int(cycle_time - 0.02):  # Log phase transitions
                        self.logger.info(f"PHASE 1: Smooth oscillation ({cycle_time:.1f}s)")
                
                # Phase 2: Random jumps every second (10-15s)
                elif cycle_time < 15.0:
                    phase2_time = cycle_time - 10.0
                    jump_index = int(phase2_time)  # 0-4
                    random.seed(42 + jump_index)  # Different seed per jump
                    normalized = random.uniform(0.0, 1.0)
                    
                    if int(phase2_time) != int(phase2_time - 0.02):  # Log jumps
                        self.logger.info(f"PHASE 2: Random jump #{jump_index+1} -> {normalized*100:.1f}%")
                
                # Phase 3: Point-to-point movement (15-20s)
                else:
                    phase3_time = cycle_time - 15.0
                    
                    # Check if we need a new target (every ~1 second or when close to target)
                    if self.phase3_target is None or abs(self.phase3_current_pos - self.phase3_target) < 0.05:
                        if time.time() - self.phase3_last_update > 0.5:  # Min 0.5s between targets
                            self.phase3_target = random.uniform(0.0, 1.0)
                            self.phase3_last_update = time.time()
                            self.logger.info(f"PHASE 3: New target -> {self.phase3_target*100:.1f}%")
                    
                    # Move towards target smoothly
                    if self.phase3_target is not None:
                        # Move at ~50%/second
                        move_speed = 0.5 * 0.02  # 50% per second * 0.02s update
                        if self.phase3_current_pos < self.phase3_target:
                            self.phase3_current_pos = min(self.phase3_current_pos + move_speed, self.phase3_target)
                        else:
                            self.phase3_current_pos = max(self.phase3_current_pos - move_speed, self.phase3_target)
                    
                    normalized = self.phase3_current_pos
                    
                    # Reset for next cycle
                    if cycle_time >= 19.9:
                        self.phase3_target = None
                        self.phase3_current_pos = 1.0  # Reset to open
                
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
