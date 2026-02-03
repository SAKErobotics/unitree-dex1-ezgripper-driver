#!/usr/bin/env python3
"""
Simple GUI for controlling EZGripper via DDS commands
Sends position commands to test GraspManager state machine
"""

import tkinter as tk
from tkinter import ttk
import cyclonedds.domain as domain
from cyclonedds.pub import DataWriter
from cyclonedds.topic import Topic
from cyclonedds.sub import DataReader
from cyclonedds.util import duration
from dataclasses import dataclass
import time

@dataclass
class GripperCommand:
    q: float
    dq: float
    tau: float

@dataclass
class GripperState:
    q: float
    dq: float
    tau: float

class GripperControlGUI:
    def __init__(self, side='left'):
        self.side = side
        self.window = tk.Tk()
        self.window.title(f"EZGripper Control - {side.upper()}")
        self.window.geometry("500x400")
        
        # DDS setup
        self.participant = domain.DomainParticipant()
        
        # Command publisher
        cmd_topic = Topic(self.participant, f'rt/dex1/{side}/cmd', GripperCommand)
        self.cmd_writer = DataWriter(self.participant, cmd_topic)
        
        # State subscriber
        state_topic = Topic(self.participant, f'rt/dex1/{side}/state', GripperState)
        self.state_reader = DataReader(self.participant, state_topic)
        
        # Current state
        self.current_position = 50.0
        self.current_effort = 30.0
        
        self._create_widgets()
        self._start_state_monitor()
        
    def _create_widgets(self):
        # Title
        title = tk.Label(self.window, text=f"{self.side.upper()} Gripper Control", 
                        font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Position control
        pos_frame = tk.LabelFrame(self.window, text="Position Control", padx=20, pady=20)
        pos_frame.pack(fill="x", padx=20, pady=10)
        
        self.pos_label = tk.Label(pos_frame, text="Position: 50%", font=("Arial", 12))
        self.pos_label.pack()
        
        self.pos_slider = tk.Scale(pos_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                   length=400, command=self._on_position_change)
        self.pos_slider.set(50)
        self.pos_slider.pack()
        
        # Quick position buttons
        btn_frame = tk.Frame(pos_frame)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="Fully Open (100%)", 
                 command=lambda: self._set_position(100), width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Half Open (50%)", 
                 command=lambda: self._set_position(50), width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Closed (0%)", 
                 command=lambda: self._set_position(0), width=15).pack(side=tk.LEFT, padx=5)
        
        # Effort control (informational - force is managed internally)
        effort_frame = tk.LabelFrame(self.window, text="Force (Managed by GraspManager)", 
                                     padx=20, pady=20)
        effort_frame.pack(fill="x", padx=20, pady=10)
        
        info_text = ("Force is automatically managed:\n"
                    "• MOVING: 80% force\n"
                    "• CONTACT: 30% force (settling)\n"
                    "• GRASPING: 30% force (holding)")
        tk.Label(effort_frame, text=info_text, justify=tk.LEFT, 
                font=("Arial", 10)).pack()
        
        # Current state display
        state_frame = tk.LabelFrame(self.window, text="Current State", padx=20, pady=20)
        state_frame.pack(fill="x", padx=20, pady=10)
        
        self.state_label = tk.Label(state_frame, text="Position: --%, Force: --%", 
                                    font=("Arial", 11))
        self.state_label.pack()
        
    def _on_position_change(self, value):
        position = float(value)
        self.pos_label.config(text=f"Position: {position:.0f}%")
        self.current_position = position
        self._send_command()
        
    def _set_position(self, position):
        self.pos_slider.set(position)
        self.current_position = position
        self._send_command()
        
    def _send_command(self):
        # Convert percentage (0-100) to radians (0-5.4)
        # 0% = fully closed = 0 rad
        # 100% = fully open = 5.4 rad
        q_rad = (self.current_position / 100.0) * 5.4
        
        # Effort is informational only - GraspManager manages force internally
        # Send nominal 30% effort (will be overridden by state machine)
        tau = 0.3
        
        cmd = GripperCommand(q=q_rad, dq=0.0, tau=tau)
        self.cmd_writer.write(cmd)
        
        print(f"📤 Sent: position={self.current_position:.0f}% ({q_rad:.2f}rad), effort={tau*100:.0f}%")
        
    def _start_state_monitor(self):
        def update_state():
            samples = self.state_reader.take(N=1)
            if samples:
                state = samples[0]
                # Convert radians back to percentage
                pos_pct = (state.q / 5.4) * 100.0
                effort_pct = state.tau * 100.0
                self.state_label.config(
                    text=f"Position: {pos_pct:.1f}%, Force: {effort_pct:.0f}%"
                )
            self.window.after(50, update_state)  # Update at 20 Hz
        
        update_state()
        
    def run(self):
        self.window.mainloop()

if __name__ == '__main__':
    import sys
    side = sys.argv[1] if len(sys.argv) > 1 else 'left'
    
    print(f"Starting GUI for {side} gripper...")
    print("Commands sent to: rt/dex1/{}/cmd".format(side))
    print("State received from: rt/dex1/{}/state".format(side))
    print("\nGraspManager will automatically manage force based on state:")
    print("  • MOVING: 80% force (fast movement)")
    print("  • CONTACT: 30% force (settling)")
    print("  • GRASPING: 30% force (holding)")
    print("\nUse the slider or buttons to control gripper position.\n")
    
    gui = GripperControlGUI(side)
    gui.run()
