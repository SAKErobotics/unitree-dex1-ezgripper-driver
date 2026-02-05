#!/usr/bin/env python3
"""
Simple GUI for controlling EZGripper via DDS commands
Sends position commands to test GraspManager state machine
Includes direct hardware calibration (bypasses DDS)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import time
import threading

# Import Unitree SDK2 for DDS communication
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_, MotorStates_, MotorCmd_, MotorState_

# Import for direct hardware access (calibration only)
from libezgripper import create_connection, create_gripper
from libezgripper.gripper_telemetry import GripperTelemetry

class GripperControlGUI:
    def __init__(self, side='left', device=None, domain=0):
        print("DEBUG: __init__ started")
        self.side = side
        self.device = device or f"/dev/ttyUSB0"  # Default device
        self.domain = domain
        print("DEBUG: Creating tk window")
        self.window = tk.Tk()
        self.window.title(f"EZGripper Control - {side.upper()}")
        self.window.geometry("650x600")
        
        print("DEBUG: Initializing DDS")
        # DDS setup using Unitree SDK2
        ChannelFactoryInitialize(self.domain)
        print("DEBUG: DDS initialized")
        
        # Command publisher
        print("DEBUG: Creating command publisher")
        cmd_topic_name = f"rt/dex1/{side}/cmd"
        self.cmd_publisher = ChannelPublisher(cmd_topic_name, MotorCmds_)
        self.cmd_publisher.Init()
        print("DEBUG: Command publisher created")
        
        # State subscriber - DISABLED for now due to blocking Read() calls
        # TODO: Implement proper non-blocking state reading with threading
        print("DEBUG: State subscriber disabled (blocking issue)")
        self.state_subscriber = None
        
        # Current state
        self.current_position = 50.0
        self.current_effort = 30.0
        
        # Telemetry state (internal)
        self.telemetry_enabled = False
        self.latest_telemetry = None
        
        # Command mode: continuous (G1 pattern) or on-demand (button clicks)
        self.continuous_mode = tk.BooleanVar(value=False)  # Default to off - user must enable
        self.command_publisher_active = False
        
        # Direct hardware connection (for calibration only)
        self.hw_connection = None
        self.hw_gripper = None
        self.calibrating = False
        
        print("DEBUG: Creating widgets")
        self._create_widgets()
        print("DEBUG: Widgets created")
        
        # Schedule DDS operations after window is shown
        # This prevents blocking during initialization
        self.window.after(100, self._init_dds_operations)
        print("DEBUG: __init__ complete - DDS operations scheduled")
        
    def _init_dds_operations(self):
        """Initialize DDS operations after window is shown"""
        print("DEBUG: Starting state monitor")
        self._start_state_monitor()
        print("DEBUG: State monitor started")
        print("DEBUG: Starting telemetry reader")
        self._start_telemetry_reader()
        print("DEBUG: Telemetry reader started")
        print("DEBUG: Starting command publisher")
        self._start_command_publisher()
        print("DEBUG: Command publisher started")
    
    def _create_widgets(self):
        # Title
        title = tk.Label(self.window, text=f"{self.side.upper()} Gripper Control", 
                        font=("Arial", 12, "bold"))
        title.pack(pady=5)
        
        # Command mode selector (compact)
        mode_frame = tk.Frame(self.window)
        mode_frame.pack(pady=2)
        
        mode_check = tk.Checkbutton(
            mode_frame,
            text="🔄 Continuous (200Hz)",
            variable=self.continuous_mode,
            command=self._toggle_command_mode,
            font=("Arial", 8)
        )
        mode_check.pack()
        
        # Position control
        pos_frame = tk.LabelFrame(self.window, text="Position Control", padx=10, pady=5)
        pos_frame.pack(fill="x", padx=10, pady=5)
        
        self.pos_label = tk.Label(pos_frame, text="Position: 50%", font=("Arial", 10))
        self.pos_label.pack()
        
        self.pos_slider = tk.Scale(pos_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                   length=500, command=self._on_position_change)
        self.pos_slider.set(50)
        self.pos_slider.pack()
        
        # Quick position buttons
        btn_frame = tk.Frame(pos_frame)
        btn_frame.pack(pady=5)
        
        tk.Button(btn_frame, text="Open (100%)", 
                 command=lambda: self._set_position(100), width=12, font=("Arial", 8)).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="Half (50%)", 
                 command=lambda: self._set_position(50), width=12, font=("Arial", 8)).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="Close (0%)", 
                 command=lambda: self._set_position(0), width=12, font=("Arial", 8)).pack(side=tk.LEFT, padx=3)
        
        
        # Command Interface (xr_teleoperate echo) - compact
        cmd_frame = tk.LabelFrame(self.window, text="DDS State", 
                                  padx=10, pady=3)
        cmd_frame.pack(fill="x", padx=10, pady=3)
        
        self.state_label = tk.Label(cmd_frame, text="Cmd: --%, Echo: --%", 
                                    font=("Arial", 8))
        self.state_label.pack()
        
        # Internal Telemetry (real state) - compact
        telemetry_frame = tk.LabelFrame(self.window, text="Internal State", 
                                        padx=10, pady=3)
        telemetry_frame.pack(fill="x", padx=10, pady=3)
        
        # Compact single-line displays
        self.telemetry_position = tk.Label(telemetry_frame, 
                                          text="Pos: --% (err: --%)  State: --  Effort: --%",
                                          font=("Arial", 8), anchor="w")
        self.telemetry_position.pack(fill="x")
        
        self.telemetry_contact = tk.Label(telemetry_frame, 
                                          text="Contact: --  Temp: --°C  Current: --mA",
                                          font=("Arial", 8), anchor="w")
        self.telemetry_contact.pack(fill="x")
        
        # Telemetry status (compact)
        self.telemetry_status = tk.Label(telemetry_frame, 
                                        text="⚠️ Telemetry: driver logs only",
                                        font=("Arial", 7), fg="orange")
        self.telemetry_status.pack()
        
        # Calibration section (compact)
        calib_frame = tk.LabelFrame(self.window, text="Calibration", 
                                    padx=10, pady=5)
        calib_frame.pack(fill="x", padx=10, pady=5)
        
        # Device and button in one row
        calib_row = tk.Frame(calib_frame)
        calib_row.pack()
        
        tk.Label(calib_row, text="Device:", font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
        self.device_entry = tk.Entry(calib_row, width=15, font=("Arial", 8))
        self.device_entry.insert(0, self.device)
        self.device_entry.pack(side=tk.LEFT, padx=2)
        
        self.calibrate_btn = tk.Button(calib_row, text="🔧 Calibrate", 
                                       command=self._calibrate_hardware,
                                       font=("Arial", 8),
                                       bg="#4CAF50", fg="white",
                                       width=12)
        self.calibrate_btn.pack(side=tk.LEFT, padx=2)
        
        self.calib_status = tk.Label(calib_row, text="Ready", 
                                     font=("Arial", 7), fg="gray")
        self.calib_status.pack(side=tk.LEFT, padx=2)
        
    def _on_position_change(self, value):
        position = float(value)
        self.pos_label.config(text=f"Position: {position:.0f}%")
        self.current_position = position
        # In on-demand mode, send command immediately
        if not self.continuous_mode.get():
            self._send_command()
        
    def _set_position(self, position):
        print(f"🔘 Button clicked: setting position to {position}%")
        self.pos_slider.set(position)
        self.current_position = position
        print(f"   Updated self.current_position = {self.current_position}%")
        # In on-demand mode, send command immediately
        if not self.continuous_mode.get():
            self._send_command()
        
    def _send_command(self):
        try:
            # Convert percentage (0-100) to radians (0-5.4) with INVERSION
            # GUI shows: 0% = closed, 100% = open
            # DDS expects: 0 rad = open (trigger released), 5.4 rad = closed (trigger squeezed)
            # INVERT: 0% -> 5.4 rad, 100% -> 0 rad
            q_rad = (100.0 - self.current_position) / 100.0 * 5.4
            
            # Effort is informational only - GraspManager manages force internally
            # Send nominal 30% effort (will be overridden by state machine)
            tau = 0.3
            
            # Create MotorCmd_ for single motor
            motor_cmd = MotorCmd_(
                mode=0,
                q=q_rad,
                dq=0.0,
                tau=tau,
                kp=0.0,
                kd=0.0,
                reserve=[0, 0, 0]
            )
            
            # Create MotorCmds_ message
            motor_cmds = MotorCmds_()
            motor_cmds.cmds = [motor_cmd]
            
            # Publish command at 200Hz (G1 pattern)
            self.cmd_publisher.Write(motor_cmds)
            
            # Debug: Log first few commands to verify publishing
            if not hasattr(self, '_cmd_count'):
                self._cmd_count = 0
            self._cmd_count += 1
            
            if self._cmd_count <= 5 or self._cmd_count % 100 == 0:
                print(f"📤 GUI CMD #{self._cmd_count}: Publishing {self.current_position:.0f}% → {q_rad:.3f} rad to rt/dex1/{self.side}/cmd")
            
        except Exception as e:
            # Only log errors (not every command at 200Hz)
            if not hasattr(self, '_last_error') or self._last_error != str(e):
                print(f"❌ Error in _send_command(): {e}")
                import traceback
                traceback.print_exc()
                self._last_error = str(e)
        
    def _toggle_command_mode(self):
        """Toggle between continuous and on-demand command mode"""
        if self.continuous_mode.get():
            # Switch to continuous mode
            print("🔄 Continuous mode enabled - sending at 200Hz")
            if not self.command_publisher_active:
                self._start_command_publisher()
        else:
            # Switch to on-demand mode
            print("⏸️ On-demand mode enabled - sending only on changes")
            self.command_publisher_active = False
    
    def _start_command_publisher(self):
        """Publish commands continuously at 200Hz like G1 teleoperation"""
        self.command_publisher_active = True
        print(f"🚀 Starting command publisher loop (continuous_mode={self.continuous_mode.get()})")
        
        def publish_command():
            # Only continue if continuous mode is still enabled
            if self.continuous_mode.get() and self.command_publisher_active:
                self._send_command()
                self.window.after(5, publish_command)  # 5ms = 200Hz
            else:
                print(f"⏸️ Command publisher stopped (continuous_mode={self.continuous_mode.get()}, active={self.command_publisher_active})")
        
        publish_command()
    
    def _start_state_monitor(self):
        """Update display with current commanded values"""
        def update_display():
            # Just show commanded position (no state feedback available)
            self.state_label.config(
                text=f"Cmd: {self.current_position:.0f}% (no feedback)"
            )
            self.window.after(100, update_display)  # Update at 10 Hz
        
        # Schedule first update
        self.window.after(100, update_display)
    
    def _start_telemetry_reader(self):
        """Read telemetry from driver log file"""
        import re
        import os
        
        log_file = "/tmp/driver_test.log"
        
        def read_telemetry():
            try:
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        # Read last 100 lines to find most recent telemetry
                        f.seek(0, 2)  # Seek to end
                        file_size = f.tell()
                        # Read last ~10KB (enough for ~100 lines)
                        read_size = min(10000, file_size)
                        f.seek(file_size - read_size)
                        lines = f.readlines()
                        
                        # Find last telemetry line
                        for line in reversed(lines):
                            if "📡 TELEMETRY:" in line:
                                # Parse: state=moving, pos=6.0% (cmd=5.0%), effort=80%, contact=False, temp=39.0°C, error=0
                                match = re.search(r'state=(\w+), pos=([\d.]+)% \(cmd=([\d.]+)%\), effort=([\d.]+)%, contact=(\w+), temp=([\d.]+)°C(?:, error=(\d+))?', line)
                                if match:
                                    state = match.group(1)
                                    actual_pos = match.group(2)
                                    cmd_pos = match.group(3)
                                    effort = match.group(4)
                                    contact = match.group(5)
                                    temp = match.group(6)
                                    hw_error = match.group(7) if match.group(7) else "0"
                                    
                                    error = float(cmd_pos) - float(actual_pos)
                                    
                                    # Decode hardware error
                                    hw_error_int = int(hw_error)
                                    hw_error_text = ""
                                    if hw_error_int != 0:
                                        errors = []
                                        if hw_error_int & 0x01: errors.append("Voltage")
                                        if hw_error_int & 0x04: errors.append("Overheat")
                                        if hw_error_int & 0x08: errors.append("Encoder")
                                        if hw_error_int & 0x10: errors.append("Shock")
                                        if hw_error_int & 0x20: errors.append("OVERLOAD")
                                        hw_error_text = f" ⚠️ {','.join(errors)}"
                                    
                                    # Format state with color coding
                                    state_upper = state.upper()
                                    state_colors = {
                                        'IDLE': 'gray',
                                        'MOVING': 'blue',
                                        'CONTACT': 'orange',
                                        'GRASPING': 'green'
                                    }
                                    state_color = state_colors.get(state_upper, 'black')
                                    
                                    # Update telemetry displays with GraspManager state
                                    self.telemetry_position.config(
                                        text=f"Pos: {actual_pos}% (err: {error:+.1f}%)  Effort: {effort}%{hw_error_text}"
                                    )
                                    self.telemetry_contact.config(
                                        text=f"GM State: {state_upper}  Contact: {contact}  Temp: {temp}°C",
                                        fg=state_color
                                    )
                                    self.telemetry_status.config(
                                        text="✅ Telemetry: live from driver logs",
                                        fg="green"
                                    )
                                break
            except Exception as e:
                # Silently handle errors
                pass
            
            # Schedule next read
            self.window.after(500, read_telemetry)  # Read at 2 Hz
        
        # Schedule first read
        self.window.after(500, read_telemetry)
        
    def _calibrate_hardware(self):
        """Calibrate gripper using direct hardware access (bypasses DDS)"""
        if self.calibrating:
            messagebox.showwarning("Calibration", "Calibration already in progress")
            return
        
        # Get device path from entry
        device_path = self.device_entry.get().strip()
        if not device_path:
            messagebox.showerror("Error", "Please enter a device path")
            return
        
        # Run calibration in background thread to avoid blocking GUI
        def calibrate_thread():
            self.calibrating = True
            self.calibrate_btn.config(state=tk.DISABLED, text="Calibrating...")
            self.calib_status.config(text="Connecting to hardware...", fg="blue")
            
            try:
                # Connect to hardware
                print(f"\n🔧 Starting calibration on {device_path}...")
                self.calib_status.config(text="Opening serial connection...")
                self.hw_connection = create_connection(dev_name=device_path, baudrate=1000000)
                time.sleep(1.0)  # Wait for connection
                
                self.calib_status.config(text="Creating gripper instance...")
                self.hw_gripper = create_gripper(self.hw_connection, f'calib_{self.side}', [1])
                
                # Perform calibration
                self.calib_status.config(text="Running calibration sequence...", fg="orange")
                print("📍 Running calibration...")
                self.hw_gripper.calibrate()
                
                # Get zero position
                zero_pos = self.hw_gripper.zero_positions[0]
                print(f"✅ Calibration complete! Zero position: {zero_pos}")
                
                # Test calibration
                self.calib_status.config(text="Verifying calibration...")
                time.sleep(0.5)
                sensor_data = self.hw_gripper.bulk_read_sensor_data(0)
                actual_pos = sensor_data.get('position', 0.0)
                error = abs(actual_pos - 50.0)
                
                if error <= 10.0:
                    self.calib_status.config(text=f"✅ Calibration successful! (at {actual_pos:.1f}%)", 
                                           fg="green")
                    messagebox.showinfo("Success", 
                                      f"Calibration completed successfully!\n\n"
                                      f"Zero position: {zero_pos}\n"
                                      f"Current position: {actual_pos:.1f}%\n"
                                      f"Error: {error:.1f}%")
                else:
                    self.calib_status.config(text=f"⚠️ Calibration issue (error: {error:.1f}%)", 
                                           fg="orange")
                    messagebox.showwarning("Warning", 
                                         f"Calibration completed with issues\n\n"
                                         f"Expected: 50%\n"
                                         f"Actual: {actual_pos:.1f}%\n"
                                         f"Error: {error:.1f}%")
                
            except Exception as e:
                print(f"❌ Calibration failed: {e}")
                self.calib_status.config(text=f"❌ Calibration failed: {str(e)[:40]}...", fg="red")
                messagebox.showerror("Calibration Error", 
                                   f"Calibration failed:\n\n{str(e)}")
            
            finally:
                # Clean up hardware connection
                try:
                    if self.hw_gripper:
                        self.hw_gripper.release()
                    if self.hw_connection and hasattr(self.hw_connection, 'port'):
                        self.hw_connection.port.close()
                except:
                    pass
                
                self.hw_connection = None
                self.hw_gripper = None
                self.calibrating = False
                self.calibrate_btn.config(state=tk.NORMAL, text="🔧 Calibrate Gripper")
                print("🔧 Calibration sequence complete\n")
        
        # Start calibration thread
        thread = threading.Thread(target=calibrate_thread, daemon=True)
        thread.start()
    
    def run(self):
        self.window.mainloop()

if __name__ == '__main__':
    import sys
    side = sys.argv[1] if len(sys.argv) > 1 else 'left'
    device = sys.argv[2] if len(sys.argv) > 2 else '/dev/ttyUSB0'
    
    print(f"Starting GUI for {side} gripper...")
    print(f"Device: {device}")
    print("\n=== DDS Control ===")
    print("Commands sent to: rt/dex1/{}/cmd".format(side))
    print("State received from: rt/dex1/{}/state".format(side))
    print("\n=== Command Modes ===")
    print("  • Continuous Mode (default): Sends at 200Hz like G1 teleoperation")
    print("  • On-Demand Mode: Sends only on button clicks/slider changes")
    print("\n=== GraspManager Force Management ===")
    print("  • MOVING: 80% force (fast movement)")
    print("  • CONTACT: 30% force (settling)")
    print("  • GRASPING: 30% force (holding)")
    print("\n=== Direct Hardware Calibration ===")
    print("Use the 'Calibrate Gripper' button to run calibration")
    print("This bypasses DDS and connects directly to hardware")
    print("\nUse the slider or buttons to control gripper position via DDS.\n")
    
    gui = GripperControlGUI(side, device)
    gui.run()
