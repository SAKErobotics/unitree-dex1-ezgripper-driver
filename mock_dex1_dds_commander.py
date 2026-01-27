#!/usr/bin/env python3
"""
Mock Dex1 DDS Commander - Exactly matches G1 Dex1 hand publishing

Publishes DDS commands that exactly match what the real G1 robot publishes
for the Dex1 hand, using proper HandCmd_ message structure.
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

# Use proper Dex1 hand messages
from unitree_sdk2py.idl.default import HGHandCmd_, HGMotorCmd_


class MockDex1DDSCommander:
    """Mock DDS commander that exactly matches G1 Dex1 hand publishing"""
    
    # Dex1 hand motor configuration (single motor per hand)
    LEFT_GRIPPER_MOTOR = 1   # Left gripper motor
    RIGHT_GRIPPER_MOTOR = 2  # Right gripper motor
    
    # Dex1 hand position range (same as before)
    DEX1_OPEN = 6.28    # Fully open (radians)
    DEX1_CLOSE = 0.0    # Fully closed (radians)
    
    def __init__(self, side: str, domain: int = 0, period: float = 10.0):
        """
        Initialize mock Dex1 commander.
        
        Args:
            side: Gripper side ('left' or 'right')
            domain: DDS domain ID
            period: Oscillation period in seconds (default 10s = 5s open, 5s close)
        """
        self.side = side
        self.domain = domain
        self.period = period
        
        # Setup DDS for Dex1 hand topics
        self.participant = DomainParticipant(domain)
        
        # Dex1 hand command topic naming convention
        if side == 'left':
            cmd_topic_name = "dt/hand_left_cmd"
        else:
            cmd_topic_name = "dt/hand_right_cmd"
            
        cmd_topic = Topic(self.participant, cmd_topic_name, HGHandCmd_)
        self.cmd_writer = DataWriter(self.participant, cmd_topic)
        
        # Motor ID for this side
        self.motor_id = self.LEFT_GRIPPER_MOTOR if side == 'left' else self.RIGHT_GRIPPER_MOTOR
        
        print(f"Mock Dex1 DDS Commander ready:")
        print(f"  Side: {side}")
        print(f"  Domain: {domain}")
        print(f"  Topic: {cmd_topic_name}")
        print(f"  Motor ID: {self.motor_id}")
        print(f"  Period: {period}s")
    
    def run(self):
        """Run the mock commander - publishes realistic Dex1 hand commands"""
        print(f"Publishing Dex1 hand commands on {'dt/hand_' + self.side + '_cmd'}...")
        
        start_time = time.time()
        
        try:
            while True:
                elapsed = time.time() - start_time
                
                # Calculate position using sine wave for smooth oscillation
                # Period = full cycle time, so half period = open to close
                phase = (elapsed % self.period) / self.period  # 0 to 1
                
                # Linear motion: 0 -> 1 -> 0 (constant speed)
                if phase < 0.5:
                    normalized = phase * 2  # 0 to 1 (opening)
                else:
                    normalized = 2 - phase * 2  # 1 to 0 (closing)
                
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
                    reserve=[0, 0, 0, 0]   # Reserved fields, typically zero
                )
                
                # Publish the hand command
                self.cmd_writer.write(hand_cmd)
                
                # Log what we're publishing (matches real G1 format)
                print(f"Dex1 Hand CMD: side={self.side}, motor{motor_cmd.id}, q={q:.3f} rad → {normalized*100:.1f}%")
                
                time.sleep(0.033)  # ~30Hz publishing rate (typical for G1)
                
        except KeyboardInterrupt:
            print("\nStopping Dex1 mock commander...")
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Mock Dex1 DDS Commander - Exactly matches G1 publishing')
    parser.add_argument('--side', choices=['left', 'right'], required=True,
                      help='Gripper side (left or right)')
    parser.add_argument('--domain', type=int, default=0,
                      help='DDS domain ID (default: 0)')
    parser.add_argument('--period', type=float, default=10.0,
                      help='Oscillation period in seconds (default: 10.0)')
    
    args = parser.parse_args()
    
    # Create and run mock commander
    commander = MockDex1DDSCommander(args.side, args.domain, args.period)
    commander.run()


if __name__ == "__main__":
    main()
