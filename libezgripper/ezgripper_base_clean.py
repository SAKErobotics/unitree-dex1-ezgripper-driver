##
# Copyright (c) 2016, The Regents of the University of California.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the The Regents of the University of California
#       nor the names of its contributors may be used to endorse or promote
#       products derived from this software without specific prior written
#       permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDERS OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
##

from typing import Dict, Any, Optional
from .lib_robotis import Robotis_Servo
from .config import Config
from .collision_reactions import CollisionReaction, CalibrationReaction
from dynamixel_sdk import GroupSyncRead, GroupSyncWrite, COMM_SUCCESS
import time
import logging


def remap(x, in_min, in_max, out_min, out_max):
    """Linear mapping function"""
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


class Gripper:
    """Modern EZGripper with position control and bulk operations"""

    def __init__(self, connection, name, servo_ids, config: Config, collision_reaction: Optional[CollisionReaction] = None):
        """Initialize gripper with minimal setup"""
        self.name = name
        self.config = config
        self.connection = connection
        self.servo_ids = servo_ids
        self.servos = [Robotis_Servo(connection, servo_id) for servo_id in servo_ids]
        
        # Initialize zero positions to 0
        # Will be set to actual zero during calibration
        self.zero_positions = [0] * len(servo_ids)
        
        # Collision detection and reaction system
        self.collision_reaction = collision_reaction  # Pluggable reaction strategy
        self.collision_monitoring_enabled = True  # Enable collision detection by default
        self.collision_detected = False
        self.calibration_active = False
        self._last_position = None
        self.cached_sensor_data = None
        
        # Initialize bulk read/write objects
        self._setup_bulk_operations()
        
        print(f"=== INITIALIZATION FOR {name} ===")
        print(f"  Zero positions initialized: {self.zero_positions}")
        print(f"  Servo IDs: {servo_ids}")
        print(f"  Number of servos: {len(self.servos)}")
        print("  Zero positions will be set during calibration")
        print("=" * 50)
        
        # Minimal hardware setup - position control mode only
        self._setup_position_control()

    def _setup_bulk_operations(self):
        """Setup GroupSyncRead and GroupSyncWrite for bulk operations"""
        # Get portHandler and packetHandler from connection
        port_handler = self.connection.portHandler
        packet_handler = self.connection.packetHandler
        
        # Bulk read for sensor data (position, current, temp, voltage, error)
        # Read contiguous block from register 126 (current) to 146 (temp) = 21 bytes
        self.bulk_read = GroupSyncRead(port_handler, packet_handler, 126, 21)
        for servo_id in self.servo_ids:
            self.bulk_read.addParam(servo_id)
        
        # Bulk write for Goal PWM (register 100, 2 bytes) - force control
        self.bulk_write_pwm = GroupSyncWrite(port_handler, packet_handler, 100, 2)
        
        # Bulk write for goal position (register 116, 4 bytes)
        self.bulk_write_position = GroupSyncWrite(port_handler, packet_handler, 116, 4)

    def _setup_position_control(self):
        """Setup servos for position control - apply all settings from config"""
        print("  Setup - applying Dynamixel settings from config...")
        
        # Register addresses for Dynamixel settings (MX-64 Protocol 2.0)
        REGISTER_MAP = {
            'operating_mode': 11,        # EEPROM, 1-byte
            'current_limit': 38,          # RAM, 2-byte
            'velocity_limit': 44,         # EEPROM, 4-byte
            'profile_acceleration': 108,  # RAM, 4-byte
            'profile_velocity': 112,      # RAM, 4-byte
            'return_delay_time': 9,       # EEPROM, 1-byte (verified from Dynamixel Wizard)
            'status_return_level': 68     # EEPROM, 1-byte
        }
        
        # 1-byte registers
        ONE_BYTE_REGISTERS = {9, 11, 68}
        
        # EEPROM registers require torque disabled
        EEPROM_REGISTERS = {11, 44, 9, 68}
        
        # Get settings from config
        config_settings = self.config._config.get('servo', {}).get('dynamixel_settings', {})
        if not config_settings:
            print("    ⚠️  No dynamixel_settings in config - using defaults")
            return
        
        for i, servo in enumerate(self.servos):
            # Read current torque status
            torque_status = servo.read_word(64)
            print(f"    Initial torque enable: {torque_status}")
            
            # Apply each setting from config
            for setting_name, target_value in config_settings.items():
                if setting_name not in REGISTER_MAP:
                    continue
                
                register_addr = REGISTER_MAP[setting_name]
                is_eeprom = register_addr in EEPROM_REGISTERS
                is_one_byte = register_addr in ONE_BYTE_REGISTERS
                
                # Read current value with correct method
                if is_one_byte:
                    current_value = servo.read_byte(register_addr)
                else:
                    current_value = servo.read_word(register_addr)
                
                # Check if update needed
                if current_value == target_value:
                    print(f"    ✅ {setting_name}: {current_value} (already correct)")
                    continue
                
                print(f"    Updating {setting_name}: {current_value} -> {target_value}")
                
                # Disable torque if writing to EEPROM
                if is_eeprom and torque_status != 0:
                    servo.write_address(64, [0])
                    torque_status = 0
                    time.sleep(0.05)
                
                # Write new value
                try:
                    servo.write_word(register_addr, target_value)
                    time.sleep(0.05)
                    
                    # Verify write with correct read method
                    if is_one_byte:
                        verify_value = servo.read_byte(register_addr)
                    else:
                        verify_value = servo.read_word(register_addr)
                    
                    if verify_value == target_value:
                        print(f"    ✅ {setting_name} updated (verified: {verify_value})")
                    else:
                        print(f"    ❌ {setting_name} write failed (read back: {verify_value})")
                except Exception as e:
                    print(f"    ❌ {setting_name} write error: {e}")
            
            # Ensure torque is enabled for operation
            if torque_status != 1:
                print(f"    Enabling torque for operation...")
                servo.write_address(64, [1])
                time.sleep(0.05)
                print(f"    ✅ Torque enabled")
        
        print("  Setup complete - all settings applied")

    def scale(self, n, to_max):
        """Scale from 0..100 to 0..to_max"""
        result = int(n * to_max / 100)
        if result > to_max: result = to_max
        if result < 0: result = 0
        return result

    def down_scale(self, n, to_max):
        """Scale from 0..to_max to 0..100"""
        result = int(round(n * 100.0 / to_max))
        if result > 100: result = 100
        if result < 0: result = 0
        return result

    def update_main_loop(self):
        """
        Main 30Hz loop - bulk read and collision detection
        Writes are done by goto_position() only
        
        Returns:
            dict: Current sensor data, collision status, and reaction result
        """
        try:
            loop_start = time.time()
            
            # Step 1: Bulk read all sensor data
            read_start = time.time()
            sensor_data = self.bulk_read_sensor_data(0)
            read_time = (time.time() - read_start) * 1000  # ms
            self.cached_sensor_data = sensor_data
            
            # Step 2: Collision detection (if monitoring enabled)
            detect_time = 0
            handle_time = 0
            reaction_result = None
            
            if self.collision_monitoring_enabled and self.collision_reaction:
                detect_start = time.time()
                collision = self._detect_collision(sensor_data)
                detect_time = (time.time() - detect_start) * 1000  # ms
                
                if collision:
                    handle_start = time.time()
                    # Call pluggable reaction strategy
                    reaction_result = self.collision_reaction.on_collision(self, sensor_data)
                    handle_time = (time.time() - handle_start) * 1000  # ms
                    
                    # Check if reaction wants to stop monitoring
                    if reaction_result and reaction_result.get('stop_monitoring', False):
                        self.collision_monitoring_enabled = False
            
            loop_time = (time.time() - loop_start) * 1000  # ms
            
            # Note: No bulk write here - only goto_position() writes to servo
            
            return {
                'sensor_data': sensor_data,
                'collision_detected': self.collision_detected,
                'collision_monitoring_enabled': self.collision_monitoring_enabled,
                'calibration_active': self.calibration_active,
                'reaction_result': reaction_result,
                'timing': {
                    'read_ms': read_time,
                    'detect_ms': detect_time,
                    'handle_ms': handle_time,
                    'total_ms': loop_time
                }
            }
            
        except Exception as e:
            print(f"Main loop error: {e}")
            return None

    def _detect_collision(self, sensor_data):
        """Detect collision - immediate response on EITHER condition"""
        stagnation_threshold = 2   # From config
        current_threshold = 150     # Lower threshold for finger contact
        
        current_position = sensor_data.get('position_raw', 0)
        current_current = abs(sensor_data.get('current', 0))
        
        # Always log during calibration for monitoring
        if self.calibration_active:
            print(f"    Monitor: pos={current_position}, current={current_current}mA", end="")
        
        # Check 1: Current spike (IMMEDIATE collision detection)
        if current_current > current_threshold:
            print(f"\n    ✅ COLLISION DETECTED: Current spike {current_current}mA > {current_threshold}mA!")
            
            # IMMEDIATE STOP: Set PWM to 0 to stop servo instantly
            self.bulk_write_pwm.clearParam()
            pwm_param = [0, 0]  # PWM = 0
            self.bulk_write_pwm.addParam(self.servo_ids[0], pwm_param)
            self.bulk_write_pwm.txPacket()
            print(f"    ⚡ IMMEDIATE STOP: PWM=0 sent")
            
            return True
        
        # Check 2: Position stagnation (IMMEDIATE collision detection)
        if hasattr(self, '_last_position') and self._last_position is not None:
            movement = abs(current_position - self._last_position)
            if self.calibration_active:
                print(f", movement={movement}", end="")
            if movement < stagnation_threshold:
                print(f"\n    ✅ COLLISION DETECTED: Position stagnation movement={movement} < {stagnation_threshold}!")
                return True
        
        if self.calibration_active:
            print()  # Newline after monitoring output
        
        self._last_position = current_position
        return False

    def enable_collision_monitoring(self, reaction: Optional[CollisionReaction] = None):
        """Enable collision detection with optional reaction strategy"""
        if reaction:
            self.collision_reaction = reaction
        self.collision_monitoring_enabled = True
        self.collision_detected = False
        self._last_position = None
        print(f"  ✅ Collision monitoring enabled with {self.collision_reaction.__class__.__name__}")
    
    def disable_collision_monitoring(self):
        """Disable collision detection"""
        self.collision_monitoring_enabled = False
        print(f"  ⏸️  Collision monitoring disabled")
    
    def set_collision_reaction(self, reaction: CollisionReaction):
        """Change the collision reaction strategy"""
        self.collision_reaction = reaction
        print(f"  🔄 Collision reaction changed to {reaction.__class__.__name__}")

    def bulk_read_sensor_data(self, servo_num=0):
        """
        Read sensor data using TRUE bulk read (single USB transaction)
        
        Returns:
            dict: {
                'position': position_pct,
                'position_raw': raw_position,
                'current': current_ma,
                'temperature': temp_c,
                'voltage': voltage_v,
                'error': error_code
            }
        """
        sensor_data = {}
        
        try:
            # Execute bulk read - SINGLE USB transaction
            result = self.bulk_read.txRxPacket()
            if result != COMM_SUCCESS:
                raise Exception(f"Bulk read communication failed: {result}")
            
            servo_id = self.servo_ids[servo_num]
            
            # Check if data is available
            if not self.bulk_read.isAvailable(servo_id, 126, 21):
                raise Exception(f"Bulk read data not available for servo {servo_id}")
            
            # Extract data from bulk read buffer (all in one transaction)
            # Register 126: present_current (2 bytes)
            current_raw = self.bulk_read.getData(servo_id, 126, 2)
            
            # Register 132: present_position (4 bytes)
            position_raw = self.bulk_read.getData(servo_id, 132, 4)
            
            # Register 144: present_voltage (2 bytes)
            voltage_raw = self.bulk_read.getData(servo_id, 144, 2)
            
            # Register 146: present_temperature (1 byte)
            temperature = self.bulk_read.getData(servo_id, 146, 1)
            
            # Parse position with software offset
            sensor_data['position_raw'] = position_raw
            servo_position = position_raw - self.zero_positions[servo_num]
            # 0% = closed (position 0), 100% = open (position 2500)
            raw_pct = self.down_scale(servo_position, 2500)  # grip_max from config
            sensor_data['position'] = min(100.0, raw_pct)  # Clamp max to 100%, negative OK
            
            # Parse current
            sensor_data['current'] = self._sign_extend_16bit(current_raw)
            
            # Parse temperature
            sensor_data['temperature'] = temperature
            
            # Parse voltage
            sensor_data['voltage'] = voltage_raw / 10.0
            
            # Error is not in contiguous block, skip for now
            sensor_data['error'] = 0
            
        except Exception as e:
            raise Exception(f"Bulk read sensor data failed: {e}")
        
        return sensor_data

    def bulk_write_control_data(self):
        """
        Write control data using GroupSyncWrite bulk operations
        
        Writes BOTH Goal PWM and goal_position using two bulk operations.
        This is more efficient than individual writes and uses our bulk infrastructure.
        
        Position translation for grasping:
        - User command 0 (fully closed) → internal target -50
        - This ensures gripper goes beyond calibrated zero into grasp operational space
        """
        # Translate position for grasping
        internal_position = self.target_position
        if self.target_position == 0:
            internal_position = -50
            print(f"    🎯 Position translation: user 0% → internal -50% (grasp operational space)")
        
        # Calculate goal values - UNCLAMPED
        scaled_position = int(int(internal_position) * 2500 / 100)
        goal_pwm = int(int(self.target_effort) * 885 / 100)  # Scale effort to PWM (0-885 for MX-64)
        
        # Clear previous bulk write params
        self.bulk_write_pwm.clearParam()
        self.bulk_write_position.clearParam()
        
        # Add parameters for each servo
        for i in range(len(self.servos)):
            target_raw_pos = self.zero_positions[i] + scaled_position
            
            # Add Goal PWM (2 bytes)
            pwm_param = [
                goal_pwm & 0xFF,
                (goal_pwm >> 8) & 0xFF
            ]
            self.bulk_write_pwm.addParam(self.servo_ids[i], pwm_param)
            
            # Add goal_position (4 bytes)
            pos_param = [
                target_raw_pos & 0xFF,
                (target_raw_pos >> 8) & 0xFF,
                (target_raw_pos >> 16) & 0xFF,
                (target_raw_pos >> 24) & 0xFF
            ]
            self.bulk_write_position.addParam(self.servo_ids[i], pos_param)
            
            print(f"    ✍️  WRITE servo: pos={self.target_position}%→{target_raw_pos}, pwm={self.target_effort}%→{goal_pwm}")
        
        # Execute bulk writes (2 USB transactions)
        from dynamixel_sdk import COMM_SUCCESS
        
        # Write Goal PWM first
        result = self.bulk_write_pwm.txPacket()
        if result != COMM_SUCCESS:
            raise Exception(f"Bulk write PWM failed: {result}")
        
        # Write goal_position second
        result = self.bulk_write_position.txPacket()
        if result != COMM_SUCCESS:
            raise Exception(f"Bulk write position failed: {result}")

    def _goto_position_unclamped(self, position_pct, effort_pct):
        """
        Set target position without clamping AND apply current to force contact
        
        Args:
            position_pct: Target position (can be negative to force beyond limit)
            effort_pct: Effort/current limit (0-100%)
        """
        # Calculate without clamping
        # 0% = closed (position 0), 100% = open (position 2500)
        scaled_position = int(int(position_pct) * 2500 / 100)  # No clamping, no inversion
        
        # Set target directly (bypass normal goto_position)
        self.target_position = position_pct
        self.target_effort = effort_pct
        
        # Write directly to servo for immediate effect
        target_raw_pos = self.zero_positions[0] + scaled_position
        self.servos[0].write_word(116, target_raw_pos)  # goal_position register
        print(f"  UNCLAMPED write: position={position_pct}% → raw={target_raw_pos}")
        
        # Note: Multi-turn mode allows going beyond normal position limits
        # No current control needed for now - multi-turn should handle it

    def goto_position(self, position_pct, effort_pct):
        """
        Set target position - ALWAYS UNCLAMPED, goes until destination or collision
        
        Args:
            position_pct: Target position (0% = fully open, 100% = fully closed, can be negative)
            effort_pct: Effort/current limit (0-100%)
        """
        self.target_position = position_pct
        self.target_effort = effort_pct
        print(f"  Target set: position={position_pct}%, effort={effort_pct}%")
        
        # Actually write to servo
        self.bulk_write_control_data()

    def calibrate_with_collision_detection(self):
        """
        Simple calibration - close until collision detected
        
        Strategy:
        1. Reset zero_positions to 0 (ensures proper wrap-around)
        2. goto_position(-300, 100) - Force beyond closed until collision
        3. Wrap-around is REQUIRED for winch/tendon tightening
        4. CalibrationReaction sets actual zero and relaxes when collision detected
        """
        # Read current position and command relative movement to ensure closing
        # This prevents direction ambiguity in Extended Position Control Mode
        pos_bytes = self.servos[0].read_address(132, 4)
        current_pos = pos_bytes[0] + (pos_bytes[1] << 8) + (pos_bytes[2] << 16) + (pos_bytes[3] << 24)
        if current_pos & 0x80000000:
            current_pos = current_pos - 0x100000000
        
        # Reset state and zero positions
        self.collision_detected = False
        self.calibration_active = True
        self.zero_positions[0] = 0
        
        # Command position well below current to ensure closing direction
        target_pos = current_pos - 15000  # Beyond close limit (-12567)
        target_pct = int(target_pos * 100 / 2500)
        
        print(f"  📍 Current: {current_pos}, Target: {target_pos} ({target_pct}%)")
        
        # Close with 100% PWM for fast movement
        # Immediate PWM=0 stop on collision prevents overload
        self.goto_position(target_pct, 100)
        
        # Wait for movement to start (skip first 5 cycles = ~165ms)
        # This prevents false collision detection from residual current
        for _ in range(5):
            self.update_main_loop()
            time.sleep(0.033)
        
        # Now enable collision monitoring after movement has started
        self.enable_collision_monitoring(CalibrationReaction())
        
        # Monitor until collision (150 cycles = ~5 seconds max)
        for _ in range(150):
            self.update_main_loop()
            if self.collision_detected:
                # Collision detected and reaction completed (PWM dropped to 15%)
                # Now open to 50% with 100% PWM
                print(f"  🔓 Opening to 50% with 100% PWM...")
                self.goto_position(50, 100)
                time.sleep(0.5)  # Wait for movement
                
                # Release gripper (PWM=0) to prevent false collision on next calibration
                print(f"  🔓 Releasing gripper (PWM=0)...")
                self.bulk_write_pwm.clearParam()
                pwm_param = [0, 0]
                self.bulk_write_pwm.addParam(self.servo_ids[0], pwm_param)
                self.bulk_write_pwm.txPacket()
                
                print(f"  ✅ Calibration complete")
                return True
            time.sleep(0.033)
        
        self.calibration_active = False
        return False

    def calibrate(self):
        """Modern calibration using goto_position with collision detection"""
        # Set calibration reaction
        self.collision_reaction = CalibrationReaction()
        return self.calibrate_with_collision_detection()

    def get_position(self):
        """Get current position in percent (for DDS interface) - uses cached data"""
        if self.cached_sensor_data:
            return self.cached_sensor_data.get('position', 0.0)
        return 0.0

    def _sign_extend_16bit(self, value):
        """Sign extend 16-bit value"""
        if value & 0x8000:
            return value - 0x10000
        return value


# Sample usage
if __name__ == '__main__':
    try:
        conn = create_connection('/dev/ttyUSB0')
        config = Config('config_default.json')
        gripper = Gripper(conn, 'test', [1], config)
        
        print("Testing modern calibration...")
        result = gripper.calibrate()
        print(f"Calibration result: {result}")
        
        print("Testing goto_position...")
        gripper.goto_position(0, 50)  # Close
        time.sleep(2.0)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
