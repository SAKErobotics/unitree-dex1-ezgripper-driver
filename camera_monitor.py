#!/usr/bin/env python3
"""
Camera monitor for gripper operation
Captures images during key gripper events for visual analysis
"""

import cv2
import time
import os
import subprocess
import threading
from datetime import datetime

class GripperCameraMonitor:
    def __init__(self, device="/dev/video4"):
        self.device = device
        self.cap = None
        self.recording = False
        self.frame_count = 0
        self.output_dir = f"/tmp/gripper_camera_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.output_dir, exist_ok=True)
        
    def initialize(self):
        """Initialize camera"""
        try:
            self.cap = cv2.VideoCapture(self.device)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            if not self.cap.isOpened():
                print(f"Failed to open camera {self.device}")
                return False
                
            # Test capture
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to capture test frame")
                return False
                
            print(f"✅ Camera initialized: {self.device}")
            print(f"   Resolution: {int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
            print(f"   FPS: {self.cap.get(cv2.CAP_PROP_FPS)}")
            print(f"   Output directory: {self.output_dir}")
            return True
            
        except Exception as e:
            print(f"Camera initialization failed: {e}")
            return False
    
    def capture_event(self, event_name):
        """Capture an image for a specific event"""
        if not self.cap or not self.cap.isOpened():
            return False
            
        try:
            ret, frame = self.cap.read()
            if ret:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
                filename = f"{self.output_dir}/{event_name}_{timestamp}.jpg"
                cv2.imwrite(filename, frame)
                print(f"📸 Captured: {event_name} -> {filename}")
                self.frame_count += 1
                return True
            else:
                print(f"Failed to capture frame for event: {event_name}")
                return False
                
        except Exception as e:
            print(f"Error capturing {event_name}: {e}")
            return False
    
    def start_continuous_monitoring(self, interval=0.5):
        """Start continuous monitoring with event detection"""
        if not self.initialize():
            return False
            
        self.recording = True
        print(f"🎥 Starting continuous monitoring (every {interval}s)")
        print("   Press Ctrl+C to stop")
        
        def monitor_thread():
            last_log_size = 0
            resistance_count = 0
            
            while self.recording:
                try:
                    # Check gripper log for events
                    log_file = "/tmp/gripper_debug.log"
                    if os.path.exists(log_file):
                        current_size = os.path.getsize(log_file)
                        
                        if current_size > last_log_size:
                            # Read new log entries
                            with open(log_file, 'r') as f:
                                f.seek(last_log_size)
                                new_lines = f.read()
                            
                            # Check for key events
                            if "Resistance detected" in new_lines:
                                resistance_count += 1
                                self.capture_event(f"resistance_{resistance_count}")
                            
                            if "Torque mode:" in new_lines and "resistance detected at" in new_lines:
                                self.capture_event(f"torque_entry_{resistance_count}")
                            
                            if "Torque pulse complete" in new_lines:
                                self.capture_event(f"torque_exit_{resistance_count}")
                            
                            # Capture periodic samples
                            if self.frame_count % 10 == 0:
                                self.capture_event(f"periodic_{self.frame_count}")
                            
                            last_log_size = current_size
                    
                    time.sleep(interval)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"Monitor error: {e}")
                    time.sleep(interval)
        
        # Start monitoring in background
        monitor = threading.Thread(target=monitor_thread)
        monitor.daemon = True
        monitor.start()
        
        try:
            # Keep main thread alive
            while self.recording:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping monitoring...")
            self.recording = False
            
        self.cleanup()
        return True
    
    def capture_sequence(self, duration=30, interval=0.5):
        """Capture a timed sequence"""
        if not self.initialize():
            return False
            
        print(f"🎬 Capturing sequence for {duration}s (every {interval}s)")
        
        start_time = time.time()
        while time.time() - start_time < duration:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
            elapsed = time.time() - start_time
            filename = f"{self.output_dir}/sequence_{elapsed:05.1f}s_{timestamp}.jpg"
            
            ret, frame = self.cap.read()
            if ret:
                cv2.imwrite(filename, frame)
                print(f"📸 {elapsed:05.1f}s: {filename}")
                self.frame_count += 1
            
            time.sleep(interval)
        
        self.cleanup()
        return True
    
    def cleanup(self):
        """Clean up resources"""
        if self.cap:
            self.cap.release()
        print(f"🏁 Monitoring complete. Captured {self.frame_count} images in {self.output_dir}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Gripper Camera Monitor")
    parser.add_argument("--device", default="/dev/video4", help="Camera device")
    parser.add_argument("--mode", choices=["monitor", "sequence"], default="monitor", help="Monitoring mode")
    parser.add_argument("--duration", type=int, default=30, help="Duration for sequence mode")
    parser.add_argument("--interval", type=float, default=0.5, help="Capture interval")
    
    args = parser.parse_args()
    
    monitor = GripperCameraMonitor(args.device)
    
    if args.mode == "monitor":
        monitor.start_continuous_monitoring(args.interval)
    else:
        monitor.capture_sequence(args.duration, args.interval)

if __name__ == "__main__":
    main()
