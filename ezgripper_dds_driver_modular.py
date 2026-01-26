#!/usr/bin/env python3
"""
Modular EZGripper DDS Driver

Single-threaded architecture with separate modules:
- DDS Interface: Handles Dex1 protocol communication
- Hardware Controller: Handles gripper control

Benefits:
- Clean separation of concerns
- No lock contention (single-threaded)
- Fast DDS response (cached state)
- Easy to test and maintain
"""

import time
import argparse
import logging
import sys
import os
import serial.tools.list_ports
import json

from dds_interface import Dex1DDSInterface
from hardware_controller import EZGripperHardwareController


def discover_ezgripper_devices():
    """Auto-discover EZGripper devices by scanning USB ports"""
    devices = []
    ports = serial.tools.list_ports.comports()
    
    for port in ports:
        if 'FTDI' in port.description or 'USB' in port.description:
            devices.append({
                'device': port.device,
                'serial': port.serial_number,
                'description': port.description
            })
    
    return devices


def get_device_config():
    """Get or create device configuration"""
    config_file = '/tmp/ezgripper_device_config.json'
    
    # Try to load existing config
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Verify devices still exist
            if 'left' in config and 'right' in config:
                if os.path.exists(config['left']) and os.path.exists(config['right']):
                    return config
        except Exception as e:
            logging.warning(f"Failed to load config: {e}")
    
    # Auto-discover devices
    devices = discover_ezgripper_devices()
    
    if len(devices) < 2:
        logging.error(f"Found {len(devices)} devices, need 2 for left and right grippers")
        return None
    
    # Create new config
    config = {
        'left': devices[0]['device'],
        'left_serial': devices[0]['serial'],
        'right': devices[1]['device'],
        'right_serial': devices[1]['serial']
    }
    
    # Save config
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logging.warning(f"Failed to save config: {e}")
    
    return config


class ModularEZGripperDriver:
    """
    Modular EZGripper driver with separate DDS and hardware modules.
    
    Single-threaded design for simplicity and performance.
    """
    
    def __init__(self, side: str, device: str, domain: int = 0):
        """
        Initialize modular driver.
        
        Args:
            side: Gripper side ('left' or 'right')
            device: Serial device path
            domain: DDS domain ID
        """
        self.side = side
        self.logger = logging.getLogger(f"driver_{side}")
        
        # Initialize modules
        self.dds = Dex1DDSInterface(side=side, domain=domain)
        self.hardware = EZGripperHardwareController(device=device, side=side)
        
        # Control loop state
        self.running = True
        self.command_count = 0
        self.position_read_interval = 10  # Read position every N cycles
        self.last_status_publish_time = 0
        self.status_publish_interval = 0.5  # Publish at 2Hz
        
        self.logger.info(f"Modular driver ready: {side} side")
    
    def run(self):
        """Main single-threaded control loop"""
        self.logger.info("Starting modular EZGripper driver...")
        
        try:
            while self.running:
                # Priority 1: Receive latest command from DDS
                cmd = self.dds.receive_command()
                
                # Priority 2: Execute command if available
                if cmd:
                    position_pct, effort_pct = cmd
                    self.hardware.execute_command(position_pct, effort_pct)
                    self.command_count += 1
                    
                    # Log occasionally
                    if self.command_count % 50 == 0:
                        if position_pct <= 5.0:
                            mode = "CLOSE"
                        elif position_pct >= 95.0:
                            mode = "OPEN"
                        else:
                            mode = f"POSITION {position_pct:.1f}%"
                        self.logger.info(f"Executing: {mode} (effort={effort_pct:.0f}%)")
                
                # Priority 3: Read position periodically (not every cycle)
                if self.command_count % self.position_read_interval == 0:
                    actual_pos = self.hardware.read_position()
                    actual_effort = self.hardware.get_cached_effort()
                    
                    # Update DDS cached state
                    self.dds.update_cached_state(actual_pos, actual_effort)
                
                # Priority 4: Publish status at fixed rate (2Hz)
                current_time = time.time()
                if current_time - self.last_status_publish_time >= self.status_publish_interval:
                    self.dds.publish_state()
                    self.last_status_publish_time = current_time
                
                # Minimal sleep to prevent CPU spinning (50Hz loop)
                time.sleep(0.02)
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down modular driver...")
        except Exception as e:
            self.logger.error(f"Driver error: {e}")
            raise
        finally:
            self.shutdown()
    
    def calibrate(self):
        """Run calibration"""
        return self.hardware.calibrate()
    
    def shutdown(self):
        """Clean shutdown"""
        self.logger.info("Shutting down...")
        self.running = False
        self.hardware.shutdown()
        self.dds.shutdown()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Modular EZGripper DDS Driver")
    parser.add_argument("--side", required=True, choices=["left", "right"],
                       help="Gripper side (left/right)")
    parser.add_argument("--dev", default=None,
                       help="EZGripper device path (auto-discover if not specified)")
    parser.add_argument("--domain", type=int, default=0,
                       help="DDS domain")
    parser.add_argument("--calibrate", action="store_true",
                       help="Calibrate on startup")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Get device path
    if args.dev:
        device = args.dev
    else:
        # Auto-discover device
        config = get_device_config()
        if config is None:
            logging.error("Failed to auto-discover devices. Please specify --dev manually.")
            sys.exit(1)
        
        device = config.get(args.side)
        if device is None:
            logging.error(f"No device configured for {args.side} side. Please specify --dev manually.")
            sys.exit(1)
        
        logging.info(f"Auto-discovered device for {args.side}: {device}")
    
    # Create and run driver
    driver = ModularEZGripperDriver(
        side=args.side,
        device=device,
        domain=args.domain
    )
    
    # Calibrate if requested
    if args.calibrate:
        driver.calibrate()
    
    try:
        driver.run()
    except KeyboardInterrupt:
        pass
    finally:
        driver.shutdown()


if __name__ == "__main__":
    main()
