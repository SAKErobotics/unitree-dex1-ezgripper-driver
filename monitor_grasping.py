#!/usr/bin/env python3
"""
Monitor gripper grasping behavior for closed-loop algorithm development.
Tracks position, current, commands, and state transitions.
"""

import time
import re
from datetime import datetime
from collections import deque

# Configuration
log_file = "/tmp/driver_output.log"
output_file = "/tmp/grasping_analysis.log"

print("=" * 70)
print("GRIPPER GRASPING BEHAVIOR MONITOR")
print("=" * 70)
print(f"Monitoring: {log_file}")
print(f"Analysis output: {output_file}")
print("\nTracking:")
print("  - Position commands (DDS)")
print("  - Actual position (sensors)")
print("  - Current draw (contact detection)")
print("  - GraspManager state transitions")
print("\nReady for grasping tests!")
print("=" * 70)
print()

# State tracking
last_position = None
last_current = None
last_command = None
last_state = None
position_history = deque(maxlen=10)
current_history = deque(maxlen=10)

with open(output_file, 'w') as out:
    out.write(f"# Gripper Grasping Analysis Log\n")
    out.write(f"# Started: {datetime.now().isoformat()}\n")
    out.write(f"# Format: timestamp, event_type, details\n\n")
    
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
            
            # Track DDS commands
            if "📥 DDS CMD:" in line:
                match = re.search(r'q=([\d.]+) rad → ([\d.]+)%', line)
                if match:
                    q_rad = float(match.group(1))
                    pos_pct = float(match.group(2))
                    
                    if last_command is None or abs(pos_pct - last_command) > 1.0:
                        msg = f"COMMAND: {pos_pct:.1f}% ({q_rad:.2f}rad)"
                        print(f"[{timestamp}] 📥 {msg}")
                        out.write(f"{timestamp}, COMMAND, {pos_pct:.1f}, {q_rad:.2f}\n")
                        out.flush()
                        last_command = pos_pct
            
            # Track position changes
            elif "🔍 POS CALC:" in line:
                match = re.search(r'raw=(\d+), zero=(\d+), servo_pos=(\d+), raw_pct=([\d.]+)%, final=([\d.]+)%', line)
                if match:
                    raw = int(match.group(1))
                    final_pct = float(match.group(5))
                    
                    position_history.append(final_pct)
                    
                    if last_position is None or abs(final_pct - last_position) > 2.0:
                        msg = f"POSITION: {final_pct:.1f}% (raw={raw})"
                        print(f"[{timestamp}] 📍 {msg}")
                        out.write(f"{timestamp}, POSITION, {final_pct:.1f}, {raw}\n")
                        out.flush()
                        last_position = final_pct
            
            # Track current (contact detection)
            elif "current=" in line and "mA" in line:
                match = re.search(r'current=(\d+)mA', line)
                if match:
                    current_ma = int(match.group(1))
                    current_history.append(current_ma)
                    
                    # Log significant current changes (contact events)
                    if last_current is None or abs(current_ma - last_current) > 100:
                        if current_ma > 300:  # High current = contact
                            msg = f"CONTACT: {current_ma}mA"
                            print(f"[{timestamp}] ⚡ {msg}")
                            out.write(f"{timestamp}, CONTACT, {current_ma}\n")
                            out.flush()
                        last_current = current_ma
            
            # Track GraspManager state
            elif "State:" in line and "Contact:" in line:
                match = re.search(r'State: (\w+), Contact: (\w+)', line)
                if match:
                    state = match.group(1)
                    contact = match.group(2)
                    
                    if state != last_state:
                        msg = f"STATE: {state} (contact={contact})"
                        print(f"[{timestamp}] 🎯 {msg}")
                        out.write(f"{timestamp}, STATE, {state}, {contact}\n")
                        out.flush()
                        last_state = state
