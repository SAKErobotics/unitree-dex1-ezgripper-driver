#!/usr/bin/env python3
"""
Test Dex1 DDS Reception

Shows exactly what the new Dex1 DDS interface receives from the mock commander.
"""

import time
import logging
import os
import sys

os.environ['CYCLONEDDS_HOME'] = os.path.expanduser('~/CascadeProjects/cyclonedds/install')

# Use proper Dex1 hand messages
from unitree_sdk2py.idl.default import HGHandCmd_, HGMotorCmd_
from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.sub import DataReader

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("dex1_test")

def test_dex1_receive():
    """Test what Dex1 DDS actually sends"""
    
    print("🔧 TESTING DEX1 DDS RECEPTION")
    print("=" * 50)
    
    try:
        # Setup DDS for left hand
        participant = DomainParticipant(0)
        cmd_topic = Topic(participant, "dt/hand_left_cmd", HGHandCmd_)
        cmd_reader = DataReader(participant, cmd_topic)
        
        print("Listening for Dex1 hand commands on dt/hand_left_cmd...")
        print("Format should be: side=left, motor1, q=X.XXX rad → XX.X%")
        print()
        
        count = 0
        while count < 10:  # Show 10 messages
            samples = cmd_reader.take()
            
            if samples and len(samples) > 0:
                hand_cmd = samples[0]
                
                print(f"📡 RAW DEX1 HAND CMD RECEIVED:")
                print(f"   Type: {type(hand_cmd)}")
                print(f"   Has motor_cmd: {hasattr(hand_cmd, 'motor_cmd')}")
                
                if hasattr(hand_cmd, 'motor_cmd') and hand_cmd.motor_cmd:
                    print(f"   Motor count: {len(hand_cmd.motor_cmd)}")
                    
                    for i, motor_cmd in enumerate(hand_cmd.motor_cmd):
                        print(f"   Motor {i+1}:")
                        print(f"     q: {motor_cmd.q:.6f} rad")
                        print(f"     mode: {motor_cmd.mode}")
                        print(f"     dq: {motor_cmd.dq}")
                        print(f"     tau: {motor_cmd.tau}")
                        print(f"     kp: {motor_cmd.kp}")
                        print(f"     kd: {motor_cmd.kd}")
                        print(f"     reserve: {motor_cmd.reserve}")
                        
                        # Convert to percentage
                        pct = (motor_cmd.q / 6.28) * 100.0
                        print(f"     → {pct:.1f}%")
                
                if hasattr(hand_cmd, 'reserve'):
                    print(f"   Reserve: {hand_cmd.reserve}")
                
                print("-" * 40)
                count += 1
            
            time.sleep(0.1)
        
        print("✅ TEST COMPLETE")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dex1_receive()
