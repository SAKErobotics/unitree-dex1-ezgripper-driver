#!/usr/bin/env python3
"""
Debug Telemetry Logger - Filters and logs contact detection debug info
Only logs when values actually change to avoid spam
"""

import argparse
import json
import time
import signal
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_


class DebugTelemetryLogger:
    """Logs debug telemetry with change detection filtering"""
    
    def __init__(self):
        self.last_state = None
        self.last_stall_count = 0
        self.last_current_count = 0
        self.last_position = None
        
    def should_log(self, data):
        """Determine if this message represents a significant change"""
        gm = data.get('grasp_manager', {})
        
        # Always log state changes
        if gm.get('state') != self.last_state:
            self.last_state = gm.get('state')
            return True
        
        # Log when stall sample count changes
        if gm.get('stall_sample_count', 0) != self.last_stall_count:
            self.last_stall_count = gm.get('stall_sample_count', 0)
            return True
        
        # Log when high current sample count changes
        if gm.get('high_current_sample_count', 0) != self.last_current_count:
            self.last_current_count = gm.get('high_current_sample_count', 0)
            return True
        
        # Log significant position changes (> 1%)
        current_pos = data.get('actual_position', 0)
        if self.last_position is None or abs(current_pos - self.last_position) > 1.0:
            self.last_position = current_pos
            return True
        
        return False
    
    def format_message(self, data):
        """Format debug data for readable output"""
        gm = data.get('grasp_manager', {})
        return (f"State: {gm.get('state', 'unknown'):8s} | "
                f"Pos: {data.get('actual_position', 0):5.1f}% → {data.get('commanded_position', 0):5.1f}% | "
                f"Goal: {data.get('goal_position', 0):5.1f}% @ {data.get('goal_effort', 0):3.0f}% | "
                f"Current: {data.get('current_ma', 0):6.1f}mA | "
                f"Stall: {gm.get('stall_sample_count', 0)}/{gm.get('stall_threshold', 0)} | "
                f"HighI: {gm.get('high_current_sample_count', 0)}/{gm.get('high_current_threshold', 0)}")


def main():
    parser = argparse.ArgumentParser(description='Log debug telemetry with change filtering')
    parser.add_argument('side', type=str, choices=['left', 'right'], help='Gripper side to monitor')
    args = parser.parse_args()

    # Initialize DDS
    ChannelFactoryInitialize(0)
    
    logger = DebugTelemetryLogger()
    
    topic = f"rt/gripper/debug/{args.side}"
    subscriber = ChannelSubscriber(topic, String_)
    subscriber.Init()

    print(f"Subscribing to {topic}...")
    print("Logging changes only (filtered). Press Ctrl+C to stop.\n")

    running = True

    def signal_handler(sig, frame):
        nonlocal running
        print("\nShutdown signal received...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)

    try:
        while running:
            try:
                msg = subscriber.Read()
                
                if msg and hasattr(msg, 'data'):
                    data = json.loads(msg.data)
                    
                    # Only log if something changed
                    if logger.should_log(data):
                        print(logger.format_message(data))
                else:
                    time.sleep(0.01)
                    
            except Exception as e:
                if running:
                    print(f"Error: {e}")
                    time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopping logger...")
    finally:
        running = False
        print("Logger stopped.")


if __name__ == "__main__":
    main()
