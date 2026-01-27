#!/usr/bin/env python3
"""
Capture Real G1 DDS Messages

Listens for actual G1 hand DDS messages to verify our format.
"""

import time
import logging
import os
import sys

os.environ['CYCLONEDDS_HOME'] = os.path.expanduser('~/CascadeProjects/cyclonedds/install')

from unitree_sdk2py.idl.default import HGHandCmd_, HGHandState_
from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.sub import DataReader

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("g1_capture")

def capture_g1_dds():
    """Capture real G1 DDS messages"""
    
    print("🔧 CAPTURING REAL G1 DDS MESSAGES")
    print("=" * 60)
    print("This will listen for actual G1 hand DDS messages")
    print("Run a G1 simulation or real G1 robot to see the real format")
    print()
    
    try:
        # Setup DDS for both left and right hands
        participant = DomainParticipant(0)
        
        # Official Unitree Dex1 topic names
        possible_topics = [
            "rt/dex1/left/cmd",
            "rt/dex1/right/cmd",
            "rt/dex1/left/state",
            "rt/dex1/right/state"
        ]
        
        readers = {}
        for topic_name in possible_topics:
            try:
                topic = Topic(participant, topic_name, HGHandCmd_)
                reader = DataReader(participant, topic)
                readers[topic_name] = reader
                print(f"✅ Listening on: {topic_name}")
            except Exception as e:
                print(f"❌ Failed to create topic {topic_name}: {e}")
        
        if not readers:
            print("❌ No topics created successfully")
            return
        
        print(f"\n📡 Listening for G1 hand commands on {len(readers)} topics...")
        print("Press Ctrl+C to stop capturing")
        print()
        
        count = 0
        while count < 50:  # Capture 50 messages max
            for topic_name, reader in readers.items():
                samples = reader.take()
                
                if samples and len(samples) > 0:
                    hand_cmd = samples[0]
                    
                    print(f"🎯 REAL G1 DDS MESSAGE on {topic_name}:")
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
                    
                    print("-" * 50)
                    count += 1
            
            time.sleep(0.1)
        
        print("✅ CAPTURE COMPLETE")
        
    except KeyboardInterrupt:
        print("\n⏹️  Capture stopped by user")
    except Exception as e:
        logger.error(f"Capture failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    capture_g1_dds()
