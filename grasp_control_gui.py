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

class GripperControlGUI:
    def __init__(self, side='left', device=None, domain=0):
        self.side = side
        self.device = device or f"/dev/ttyUSB0"  # Default device
        self.domain = domain
        self.window = tk.Tk()
        self.window.title(f"EZGripper Control - {side.upper()}")
        self.window.geometry("600x550")
        
        # DDS setup using Unitree SDK2
        ChannelFactoryInitialize(self.domain)
        
        # Command publisher
        cmd_topic_name = f"rt/dex1/{side}/cmd"
        self.cmd_publisher = ChannelPublisher(cmd_topic_name, MotorCmds_)
        self.cmd_publisher.Init()
        
        # State subscriber
        state_topic_name = f"rt/dex1/{side}/state"
        self.state_subscriber = ChannelSubscriber(state_topic_name, MotorStates_)
        self.state_subscriber.Init()
        
        # Current state
        self.current_position = 50.0
        self.current_effort = 30.0
        
        # Direct hardware connection (for calibration only)
        self.hw_connection = None
        self.hw_gripper = None
        self.calibrating = False
        
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
        
        # Calibration section (direct hardware access)
        calib_frame = tk.LabelFrame(self.window, text="Calibration (Direct Hardware)", 
                                    padx=20, pady=20)
        calib_frame.pack(fill="x", padx=20, pady=10)
        
        # Device path input
        device_input_frame = tk.Frame(calib_frame)
        device_input_frame.pack(pady=5)
        tk.Label(device_input_frame, text="Device:", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        self.device_entry = tk.Entry(device_input_frame, width=20, font=("Arial", 10))
        self.device_entry.insert(0, self.device)
        self.device_entry.pack(side=tk.LEFT, padx=5)
        
        # Calibrate button
        self.calibrate_btn = tk.Button(calib_frame, text="🔧 Calibrate Gripper", 
                                       command=self._calibrate_hardware,
                                       font=("Arial", 11, "bold"),
                                       bg="#4CAF50", fg="white",
                                       width=20, height=2)
        self.calibrate_btn.pack(pady=10)
        
        self.calib_status = tk.Label(calib_frame, text="Ready to calibrate", 
                                     font=("Arial", 9), fg="gray")
        self.calib_status.pack()
        
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
        try:
            # Convert percentage (0-100) to radians (0-5.4)
            # 0% = fully closed = 0 rad
            # 100% = fully open = 5.4 rad
            q_rad = (self.current_position / 100.0) * 5.4
            
            # Effort is informational only - GraspManager manages force internally
            # Send nominal 30% effort (will be overridden by state machine)
            tau = 0.3
            
            print(f"\n🔵 _send_command() called: position={self.current_position:.0f}%")
            
            # Create MotorCmd_ for single motor
            motor_cmd = MotorCmd_(
                mode=0,
                q=q_rad,
                dq=0.0,
                tau=tau,
                kp=0.0,
                kd=0.0,
                reserve=[0, 0, 0]  # Required reserve field
            )
            print(f"✅ Created MotorCmd_: q={q_rad:.3f}, tau={tau}")
            
            # Create MotorCmds_ message
            motor_cmds = MotorCmds_()
            motor_cmds.cmds = [motor_cmd]
            print(f"✅ Created MotorCmds_ with {len(motor_cmds.cmds)} commands")
            
            # Publish command
            result = self.cmd_publisher.Write(motor_cmds)
            print(f"✅ Write() returned: {result}")
            print(f"📤 Sent: position={self.current_position:.0f}% ({q_rad:.2f}rad), effort={tau*100:.0f}%\n")
            
        except Exception as e:
            print(f"❌ Error in _send_command(): {e}")
            import traceback
            traceback.print_exc()
        
    def _start_state_monitor(self):
        def update_state():
            # Read state from DDS
            state_msg = self.state_subscriber.Read()
            
            if state_msg and hasattr(state_msg, 'states') and state_msg.states and len(state_msg.states) > 0:
                state = state_msg.states[0]
                # Convert radians back to percentage
                pos_pct = (state.q / 5.4) * 100.0
                effort_pct = state.tau_est * 100.0
                self.state_label.config(
                    text=f"Position: {pos_pct:.1f}%, Force: {effort_pct:.0f}%"
                )
            
            self.window.after(50, update_state)  # Update at 20 Hz
        
        update_state()
        
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
    print("\nGraspManager will automatically manage force based on state:")
    print("  • MOVING: 80% force (fast movement)")
    print("  • CONTACT: 30% force (settling)")
    print("  • GRASPING: 30% force (holding)")
    print("\n=== Direct Hardware Calibration ===")
    print("Use the 'Calibrate Gripper' button to run calibration")
    print("This bypasses DDS and connects directly to hardware")
    print("\nUse the slider or buttons to control gripper position via DDS.\n")
    
    gui = GripperControlGUI(side, device)
    gui.run()
