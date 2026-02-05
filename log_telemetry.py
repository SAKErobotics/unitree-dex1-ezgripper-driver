import argparse
import csv
import json
import os
import time
from datetime import datetime

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.std_msgs.msg.dds_ import String_

class TelemetryCsvLogger:
    """
    Logs significant gripper telemetry events to a structured CSV file.
    """
    def __init__(self, log_dir="/tmp/gripper_telemetry"):
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = os.path.join(log_dir, f"telemetry_events_{timestamp}.csv")
        self.file = open(self.log_path, 'w', newline='')
        self.writer = None
        self.header_written = False
        self.fieldnames = [
            'timestamp',
            'grasp_state',
            'actual_pos_pct',
            'commanded_pos_pct',
            'current_ma',
            'hw_error'
        ]

    def write_event(self, data):
        """Writes a single event row to the CSV file."""
        if not self.header_written:
            self.writer = csv.DictWriter(self.file, fieldnames=self.fieldnames)
            self.writer.writeheader()
            self.header_written = True
        
        row = {
            'timestamp': f"{data['timestamp']:.3f}",
            'grasp_state': data['grasp_manager']['state'],
            'actual_pos_pct': f"{data['position']['actual_pct']:.2f}",
            'commanded_pos_pct': f"{data['position']['commanded_pct']:.2f}",
            'current_ma': f"{data['health']['current_ma']:.2f}",
            'hw_error': data['health']['hardware_error_description']
        }
        self.writer.writerow(row)
        self.file.flush() # Ensure data is written immediately

    def close(self):
        if self.file:
            self.file.close()
            print(f"\nTelemetry event log saved to {self.log_path}")

def main():
    parser = argparse.ArgumentParser(description='Log gripper telemetry events from DDS.')
    parser.add_argument('side', type=str, choices=['left', 'right'], help='Gripper side to monitor.')
    args = parser.parse_args()

    # Initialize the DDS channel factory (domain 0, no network interface needed for local)
    ChannelFactoryInitialize(0)
    
    logger = TelemetryCsvLogger()
    
    topic = f"rt/gripper/{args.side}/telemetry"
    subscriber = ChannelSubscriber(topic, String_)
    subscriber.Init()

    print(f"Subscribing to {topic}...")
    print("Logging significant events. Press Ctrl+C to stop.")

    last_state = None
    last_error = "No error"
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        print("\nShutdown signal received...")
        running = False

    import signal
    signal.signal(signal.SIGINT, signal_handler)

    try:
        while running:
            try:
                # Read message (blocking with timeout)
                msg = subscriber.Read()
                
                if msg and hasattr(msg, 'data'):
                    data = json.loads(msg.data)
                    
                    current_state = data['grasp_manager']['state']
                    current_error = data['health']['hardware_error_description']

                    # Log only when state or error changes
                    if current_state != last_state or current_error != last_error:
                        print(f"Event: State -> {current_state}, Error -> {current_error}")
                        logger.write_event(data)
                        last_state = current_state
                        last_error = current_error
                else:
                    time.sleep(0.01)  # Small delay if no message
            except Exception as e:
                if running:  # Only log if not shutting down
                    print(f"Error reading message: {e}")
                    time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopping logger...")
    finally:
        running = False
        logger.close()
        print("Logger stopped.")

if __name__ == "__main__":
    main()
