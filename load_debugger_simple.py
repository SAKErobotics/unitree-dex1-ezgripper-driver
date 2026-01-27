#!/usr/bin/env python3
"""
Simple Load Condition Debugger for EZGripper Reactive Algorithms

Analyzes reactive behavior under various load conditions while preserving
sacred NO-LOAD relationships for commanding.
"""

import re
from datetime import datetime
import os

class LoadDebugger:
    def __init__(self, log_file="/tmp/gripper_debug.log"):
        self.log_file = log_file
        self.events = []
        
    def parse_log(self):
        """Parse gripper log for reactive algorithm events"""
        print("🔍 Parsing gripper log for reactive events...")
        
        with open(self.log_file, 'r') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            # Parse resistance detection events
            if "Resistance detected" in line:
                match = re.search(r'current=([\d.]+).*pos=([\d.]+)%', line)
                if match:
                    self.events.append({
                        'type': 'resistance_detected',
                        'timestamp': line[:19],
                        'current': float(match.group(1)),
                        'commanded_pos': float(match.group(2)),
                        'line_num': i
                    })
            
            # Parse torque mode events
            elif "Torque mode:" in line and "resistance detected at" in line:
                match = re.search(r'resistance detected at ([\d.]+)%', line)
                if match:
                    self.events.append({
                        'type': 'torque_entry',
                        'timestamp': line[:19],
                        'actual_pos': float(match.group(1)),
                        'line_num': i
                    })
            
            # Parse torque exit events
            elif "Torque pulse complete" in line:
                match = re.search(r'switching to POSITION mode at ([\d.]+)%', line)
                if match:
                    self.events.append({
                        'type': 'torque_exit',
                        'timestamp': line[:19],
                        'exit_pos': float(match.group(1)),
                        'line_num': i
                    })
            
            # Parse command/position tracking
            elif "INPUT: POSITION" in line:
                match = re.search(r'POSITION ([\d.]+)%.*TRACKED: ([\d.]+)%.*current=([\d.]+)', line)
                if match:
                    self.events.append({
                        'type': 'position_update',
                        'timestamp': line[:19],
                        'commanded_pos': float(match.group(1)),
                        'expected_pos': float(match.group(2)),
                        'current': float(match.group(3)),
                        'line_num': i
                    })
        
        print(f"✅ Parsed {len(self.events)} events")
        return self.events
    
    def analyze_reactive_behavior(self):
        """Analyze reactive algorithm behavior under load"""
        print("\n🎯 Analyzing Reactive Algorithm Behavior...")
        
        resistance_events = [e for e in self.events if e['type'] == 'resistance_detected']
        torque_entries = [e for e in self.events if e['type'] == 'torque_entry']
        torque_exits = [e for e in self.events if e['type'] == 'torque_exit']
        
        print(f"\n📊 Reactive Algorithm Summary:")
        print(f"   Resistance Detections: {len(resistance_events)}")
        print(f"   Torque Mode Entries: {len(torque_entries)}")
        print(f"   Torque Mode Exits: {len(torque_exits)}")
        
        if resistance_events:
            currents = [e['current'] for e in resistance_events]
            positions = [e['commanded_pos'] for e in resistance_events]
            
            print(f"\n⚡ Resistance Detection Analysis:")
            print(f"   Current Range: {min(currents):.1f} - {max(currents):.1f} (threshold: 200)")
            print(f"   Detection Positions: {min(positions):.1f}% - {max(positions):.1f}%")
            print(f"   Avg Detection Current: {sum(currents)/len(currents):.1f}")
        
        # Analyze torque mode effectiveness
        if torque_entries and torque_exits:
            print(f"\n🔄 Torque Mode Effectiveness:")
            for i, (entry, exit) in enumerate(zip(torque_entries, torque_exits)):
                position_drift = abs(entry['actual_pos'] - exit['exit_pos'])
                print(f"   Event {i+1}: Drift {position_drift:.1f}%")
        
        return resistance_events, torque_entries, torque_exits
    
    def analyze_sacred_relationships(self):
        """Verify sacred NO-LOAD relationships are preserved"""
        print("\n🏛️ Analyzing Sacred NO-LOAD Relationships...")
        
        position_events = [e for e in self.events if e['type'] == 'position_update']
        
        if not position_events:
            print("❌ No position events found")
            return []
        
        # Analyze commanded vs expected positions
        commanded = [e['commanded_pos'] for e in position_events]
        expected = [e['expected_pos'] for e in position_events]
        differences = [c - e for c, e in zip(commanded, expected)]
        
        print(f"📈 Position Tracking Analysis:")
        print(f"   Commanded Range: {min(commanded):.1f}% - {max(commanded):.1f}%")
        print(f"   Expected Range: {min(expected):.1f}% - {max(expected):.1f}%")
        print(f"   Max Difference: {max(abs(d) for d in differences):.1f}%")
        
        # Check if sacred relationships are preserved
        max_allowed_diff = 2.0  # Small tolerance for timing
        violations = [d for d in differences if abs(d) > max_allowed_diff]
        
        if violations:
            print(f"⚠️  Sacred Relationship Violations: {len(violations)}")
            print(f"   Max Violation: {max(abs(d) for d in violations):.1f}%")
        else:
            print(f"✅ Sacred NO-LOAD relationships preserved!")
        
        return violations
    
    def generate_report(self):
        """Generate comprehensive debugging report"""
        print("\n📋 Generating Load Condition Report...")
        
        # Parse events
        self.parse_log()
        
        # Analyze reactive behavior
        resistance_events, torque_entries, torque_exits = self.analyze_reactive_behavior()
        
        # Analyze sacred relationships
        violations = self.analyze_sacred_relationships()
        
        # Generate summary
        print(f"\n🎯 REACTIVE ALGORITHM DEBUGGING SUMMARY:")
        print(f"   Load Response: ✅ Analyzed {len(resistance_events)} resistance events")
        print(f"   Torque Control: ✅ Analyzed {len(torque_entries)} torque mode cycles")
        print(f"   Sacred Data: {'✅ Preserved' if not violations else f'⚠️ {len(violations)} violations'}")
        
        return {
            'resistance_events': len(resistance_events),
            'torque_cycles': len(torque_entries),
            'sacred_violations': len(violations),
            'events': self.events
        }
    
    def debug_specific_event(self, event_index):
        """Debug a specific resistance detection event in detail"""
        resistance_events = [e for e in self.events if e['type'] == 'resistance_detected']
        
        if event_index >= len(resistance_events):
            print(f"❌ Event {event_index} not found (only {len(resistance_events)} events)")
            return
        
        event = resistance_events[event_index]
        line_num = event['line_num']
        
        print(f"\n🔍 Debugging Resistance Detection Event {event_index + 1}:")
        print(f"   Timestamp: {event['timestamp']}")
        print(f"   Commanded Pos: {event['commanded_pos']:.1f}%")
        print(f"   Current: {event['current']:.1f}")
        
        # Show context around event
        print(f"\n📝 Event Context:")
        with open(self.log_file, 'r') as f:
            lines = f.readlines()
        
        start = max(0, line_num - 5)
        end = min(len(lines), line_num + 10)
        
        for i in range(start, end):
            prefix = ">>> " if i == line_num else "    "
            print(f"{prefix}{lines[i].rstrip()}")

def main():
    debugger = LoadDebugger()
    report = debugger.generate_report()
    
    # Debug first resistance event in detail
    resistance_events = [e for e in debugger.events if e['type'] == 'resistance_detected']
    if resistance_events:
        debugger.debug_specific_event(0)
    
    print(f"\n🏁 Load debugging complete!")
    return report

if __name__ == "__main__":
    main()
