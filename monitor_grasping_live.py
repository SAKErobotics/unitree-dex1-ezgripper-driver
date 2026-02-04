#!/usr/bin/env python3
"""
Real-time grasping data collector for algorithm analysis
Monitors all aspects of gripper control flow during grasping tests
"""

import time
import re
import csv
from datetime import datetime
from collections import deque

# Configuration
log_file = "/tmp/driver_output.log"
output_csv = "/tmp/grasping_data.csv"

print("=" * 70)
print("GRIPPER GRASPING DATA COLLECTOR")
print("=" * 70)
print(f"Reading from: {log_file}")
print(f"Writing to: {output_csv}")
print("\nCollecting:")
print("  - DDS commands (position, effort)")
print("  - GraspManager state transitions")
print("  - Actual position from sensors")
print("  - Current draw (contact detection)")
print("  - Servo write commands")
print("\nReady! Start grasping tests with the GUI...")
print("=" * 70)
print()

# Initialize CSV file
with open(output_csv, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow([
        'timestamp',
        'event_type',
        'dds_position_pct',
        'dds_effort_pct',
        'managed_position_pct',
        'managed_effort_pct',
        'actual_position_pct',
        'actual_position_raw',
        'current_ma',
        'servo_write_position',
        'servo_write_current',
        'grasp_state',
        'notes'
    ])

# State tracking
last_data = {
    'dds_position': None,
    'dds_effort': None,
    'managed_position': None,
    'managed_effort': None,
    'actual_position': None,
    'actual_raw': None,
    'current': None,
    'servo_pos': None,
    'servo_current': None,
    'state': None
}

event_count = 0

# Follow the log file
with open(log_file, 'r') as f:
    # Seek to end
    f.seek(0, 2)
    
    while True:
        line = f.readline()
        if not line:
            time.sleep(0.01)
            continue
        
        timestamp = datetime.now().isoformat()
        event_type = None
        notes = ""
        
        # Parse DDS commands
        if "🎯 DDS INPUT:" in line:
            match = re.search(r'pos=([\d.]+)%, effort=([\d.]+)%', line)
            if match:
                last_data['dds_position'] = float(match.group(1))
                last_data['dds_effort'] = float(match.group(2))
                event_type = "dds_command"
        
        # Parse managed goals
        elif "🎯 MANAGED GOAL:" in line:
            match = re.search(r'pos=([\d.]+)%, effort=([\d.]+)%', line)
            if match:
                last_data['managed_position'] = float(match.group(1))
                last_data['managed_effort'] = float(match.group(2))
                event_type = "managed_goal"
        
        # Parse actual position
        elif "📊 SENSOR:" in line:
            match = re.search(r'raw=(\d+), pct=([\d.]+)%', line)
            if match:
                last_data['actual_raw'] = int(match.group(1))
                last_data['actual_position'] = float(match.group(2))
                event_type = "sensor_read"
        
        # Parse current
        elif "🔍 POS CALC:" in line:
            match = re.search(r'raw=(\d+).*current.*?(\d+)', line)
            if match:
                last_data['current'] = int(match.group(2)) if len(match.groups()) > 1 else None
        
        # Parse servo writes
        elif "✍️ WRITE:" in line:
            match = re.search(r'pos=([\d.]+)%→raw=(\d+), current=([\d.]+)%→(\d+)mA', line)
            if match:
                last_data['servo_pos'] = int(match.group(2))
                last_data['servo_current'] = int(match.group(4))
                event_type = "servo_write"
        
        # Parse state transitions
        elif "GM:" in line and "→" in line:
            match = re.search(r'(\w+) → (\w+)', line)
            if match:
                old_state = match.group(1)
                new_state = match.group(2)
                last_data['state'] = new_state
                event_type = "state_transition"
                notes = f"{old_state}→{new_state}"
                print(f"[{timestamp}] STATE: {old_state} → {new_state}")
        
        # Write to CSV when we have a significant event
        if event_type:
            event_count += 1
            
            with open(output_csv, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    timestamp,
                    event_type,
                    last_data['dds_position'],
                    last_data['dds_effort'],
                    last_data['managed_position'],
                    last_data['managed_effort'],
                    last_data['actual_position'],
                    last_data['actual_raw'],
                    last_data['current'],
                    last_data['servo_pos'],
                    last_data['servo_current'],
                    last_data['state'],
                    notes
                ])
            
            # Print summary every 100 events
            if event_count % 100 == 0:
                print(f"[{timestamp}] Events logged: {event_count}")
                if last_data['actual_position'] is not None:
                    print(f"  Position: {last_data['actual_position']:.1f}%, Current: {last_data['current']}mA, State: {last_data['state']}")
