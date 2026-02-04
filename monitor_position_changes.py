#!/usr/bin/env python3
"""
Monitor gripper position changes and log to file with timestamps.
Only logs when position actually changes (filters out noise).
"""

import time
import re
from datetime import datetime

# Configuration
log_file = "/tmp/driver_output.log"
output_file = "/tmp/gripper_position_changes.log"
position_threshold = 0.5  # Only log if position changes by more than this %

print("=" * 60)
print("GRIPPER POSITION CHANGE MONITOR")
print("=" * 60)
print(f"Monitoring: {log_file}")
print(f"Output: {output_file}")
print(f"Threshold: {position_threshold}%")
print("\nManually move the gripper now...")
print("Press Ctrl+C to stop")
print("=" * 60)
print()

last_position = None
last_raw = None
last_log_time = None

with open(output_file, 'w') as out:
    out.write(f"# Gripper Position Change Log\n")
    out.write(f"# Started: {datetime.now().isoformat()}\n")
    out.write(f"# Format: timestamp, raw_position, position_pct, delta_pct\n\n")
    
    # Follow the log file
    with open(log_file, 'r') as f:
        # Seek to end
        f.seek(0, 2)
        
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.01)
                continue
            
            # Parse sensor readings: "📊 SENSOR: raw=4357, pct=100.0%"
            if "📊 SENSOR:" in line:
                match = re.search(r'raw=(\d+), pct=([\d.]+)%', line)
                if match:
                    raw = int(match.group(1))
                    pct = float(match.group(2))
                    
                    # Check if position changed significantly
                    if last_position is None or abs(pct - last_position) >= position_threshold:
                        timestamp = datetime.now().isoformat()
                        delta = 0.0 if last_position is None else pct - last_position
                        
                        # Log to file
                        out.write(f"{timestamp}, {raw}, {pct:.1f}, {delta:+.1f}\n")
                        out.flush()
                        
                        # Print to console
                        if last_position is None:
                            print(f"[{timestamp}] Initial: {pct:.1f}% (raw={raw})")
                        else:
                            direction = "↑" if delta > 0 else "↓"
                            print(f"[{timestamp}] {pct:.1f}% (raw={raw}) {direction} {abs(delta):.1f}%")
                        
                        last_position = pct
                        last_raw = raw
                        last_log_time = time.time()
