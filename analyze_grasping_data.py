#!/usr/bin/env python3
"""
Analyze grasping data collected during tests
Provides insights for algorithm improvements
"""

import csv
import sys
from collections import defaultdict

csv_file = "/tmp/grasping_data.csv"

print("=" * 70)
print("GRASPING DATA ANALYSIS")
print("=" * 70)

# Read data
data = []
with open(csv_file, 'r') as f:
    reader = csv.DictReader(f)
    data = list(reader)

print(f"\nTotal events: {len(data)}")

# Analyze by event type
event_counts = defaultdict(int)
for row in data:
    event_counts[row['event_type']] += 1

print("\nEvent breakdown:")
for event_type, count in sorted(event_counts.items()):
    print(f"  {event_type}: {count}")

# Find state transitions
print("\nState transitions:")
transitions = [row for row in data if row['event_type'] == 'state_transition']
for t in transitions:
    print(f"  {t['timestamp']}: {t['notes']}")

# Analyze position tracking
print("\nPosition tracking:")
positions = [(row['timestamp'], row['dds_position_pct'], row['actual_position_pct']) 
             for row in data if row['actual_position_pct']]

if positions:
    # Show first and last positions
    print(f"  Start: DDS={positions[0][1]}%, Actual={positions[0][2]}%")
    print(f"  End: DDS={positions[-1][1]}%, Actual={positions[-1][2]}%")
    
    # Calculate average tracking error
    errors = []
    for ts, dds, actual in positions:
        if dds and actual:
            try:
                error = abs(float(dds) - float(actual))
                errors.append(error)
            except:
                pass
    
    if errors:
        avg_error = sum(errors) / len(errors)
        max_error = max(errors)
        print(f"  Average tracking error: {avg_error:.1f}%")
        print(f"  Maximum tracking error: {max_error:.1f}%")

# Analyze current draw (contact detection)
print("\nCurrent analysis:")
currents = [(row['timestamp'], row['current_ma']) 
            for row in data if row['current_ma']]

if currents:
    current_values = [int(c[1]) for c in currents if c[1]]
    if current_values:
        avg_current = sum(current_values) / len(current_values)
        max_current = max(current_values)
        print(f"  Average current: {avg_current:.0f}mA")
        print(f"  Peak current: {max_current}mA")
        
        # Detect high current events (potential contact)
        high_current_events = [c for c in current_values if c > 800]
        if high_current_events:
            print(f"  High current events (>800mA): {len(high_current_events)}")

# Analyze effort management
print("\nEffort management:")
servo_writes = [(row['timestamp'], row['servo_write_current']) 
                for row in data if row['servo_write_current']]

if servo_writes:
    efforts = [int(s[1]) for s in servo_writes if s[1]]
    if efforts:
        unique_efforts = sorted(set(efforts))
        print(f"  Effort levels used: {unique_efforts}mA")
        
        # Count effort changes
        effort_changes = 0
        last_effort = None
        for effort in efforts:
            if last_effort and effort != last_effort:
                effort_changes += 1
            last_effort = effort
        print(f"  Effort changes: {effort_changes}")

print("\n" + "=" * 70)
print("Analysis complete. Review data for algorithm improvements.")
print("=" * 70)
