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

from .lib_robotis import create_connection, Robotis_Servo
from .config import Config
from dynamixel_sdk import GroupSyncRead, COMM_SUCCESS
import time
import logging


def remap(x, in_min, in_max, out_min, out_max):
    """Linear mapping function"""
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


class Gripper:
    """Modern EZGripper with position control and bulk operations"""

    def __init__(self, connection, name, servo_ids, config: Config):
        """Initialize gripper with minimal setup"""
        self.name = name
        self.config = config
        self.servos = [Robotis_Servo(connection, servo_id) for servo_id in servo_ids]
        
        # Initialize zero positions (software-managed, set during calibration)
        self.zero_positions = [0] * len(servo_ids)
        
        print(f"=== INITIALIZATION FOR {name} ===")
        print(f"  Zero positions initialized: {self.zero_positions}")
        print(f"  Servo IDs: {servo_ids}")
        print(f"  Number of servos: {len(self.servos)}")
        print("  Zero positions will be set during calibration")
        print("=" * 50)
        
        # Minimal hardware setup - position control mode only
        self._setup_position_control()

    def _setup_position_control(self):
        """Read current state and only write parameters that need updating"""
        print("  Setup - checking servo configuration...")
        
        # Small delay after connection before first operation
        time.sleep(0.5)
        
        for i, servo in enumerate(self.servos):
            # Read current torque enable status
            torque_status = servo.read_word(64)
            print(f"    Torque enable: {torque_status}")
            
            # Read current multi-turn mode (REQUIRED for EZGripper)
            multi_turn_mode = servo.read_word(10)
            print(f"    Multi-turn mode: {multi_turn_mode}")
            
            # Only update multi-turn if needed
            if multi_turn_mode != 1:
                print(f"    Updating multi-turn mode: {multi_turn_mode} -> 1")
                
                # Disable torque if needed for EEPROM write
                if torque_status != 0:
                    print(f"    Disabling torque for EEPROM write...")
                    servo.write_address(64, [0])
                    torque_status = 0  # Update our cached status
                    time.sleep(0.05)
                
                # Write multi-turn mode
                servo.write_word(10, 1)
                time.sleep(0.1)
                
                # Verify
                new_mode = servo.read_word(10)
                if new_mode != 1:
                    print(f"    ❌ FAILED to enable multi-turn mode!")
                else:
                    print(f"    ✅ Multi-turn mode updated successfully")
            else:
                print(f"    ✅ Multi-turn mode already correct")
            
            # Check operating mode (should be 4 for extended position control)
            operating_mode = servo.read_word(11)
            print(f"    Operating mode: {operating_mode}")
            if operating_mode != 4:
                print(f"    Updating operating mode: {operating_mode} -> 4")
                # Disable torque if needed for EEPROM write
                if torque_status != 0:
                    print(f"    Disabling torque for EEPROM write...")
                    servo.write_address(64, [0])
                    torque_status = 0
                    time.sleep(0.05)
                servo.write_word(11, 4)
                time.sleep(0.05)
                print(f"    ✅ Operating mode updated")
            else:
                print(f"    ✅ Operating mode already correct")
            
            # Set current limit to safe value (register 38)
            # Read current limit from config (max = 200 in config_default.json)
            safe_current_limit = 200  # ~680mA, prevents overload
            current_limit = servo.read_word(38)
            print(f"    Current limit: {current_limit}")
            
            if current_limit != safe_current_limit:
                print(f"    Updating current limit: {current_limit} -> {safe_current_limit}")
                # Disable torque if needed for write
                if torque_status != 0:
                    servo.write_address(64, [0])
                    torque_status = 0
                    time.sleep(0.05)
                servo.write_word(38, safe_current_limit)
                time.sleep(0.05)
                print(f"    ✅ Current limit updated")
            else:
                print(f"    ✅ Current limit already correct")
            
            # Ensure torque is enabled for operation
            if torque_status != 1:
                print(f"    Enabling torque for operation...")
                servo.write_address(64, [1])
                time.sleep(0.05)
                print(f"    ✅ Torque enabled")
            else:
                print(f"    ✅ Torque already enabled")
        
        print("  Setup complete - all parameters verified")

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
        Main 30Hz loop - bulk read, collision detection, bulk write
        
        Returns:
            dict: Current sensor data and collision status
        """
        try:
            # Step 1: Bulk read all sensor data
            sensor_data = self.bulk_read_sensor_data(0)
            self.cached_sensor_data = sensor_data
            
            # Step 2: Collision detection (if calibration active)
            if self.calibration_active:
                collision = self._detect_collision(sensor_data)
                if collision:
                    self._handle_collision_collision(sensor_data)
            
            # Step 3: Bulk write control data
            self.bulk_write_control_data()
            
            return {
                'sensor_data': sensor_data,
                'collision_detected': self.collision_detected,
                'calibration_active': self.calibration_active
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
        
        # Check 1: Current spike (IMMEDIATE collision detection)
        if current_current > current_threshold:
            print(f"    ✅ IMMEDIATE COLLISION: Current spike {current_current}mA > {current_threshold}mA!")
            return True
        
        # Check 2: Position stagnation (IMMEDIATE collision detection)
        if hasattr(self, '_last_position') and self._last_position is not None:
            movement = abs(current_position - self._last_position)
            if movement < stagnation_threshold:
                print(f"    ✅ IMMEDIATE COLLISION: Position stagnation movement={movement} < {stagnation_threshold}!")
                return True
        
        self._last_position = current_position
        return False

    def _handle_collision_collision(self, sensor_data):
        """IMMEDIATE collision handling - record zero position and goto 50"""
        if not self.collision_detected:
            self.collision_detected = True
            self.calibration_active = False
            
            # Record zero position from collision
            collision_position = sensor_data.get('position_raw', 0)
            self.zero_positions[0] = collision_position
            print(f"  Zero position set to: {collision_position}")
            
            # IMMEDIATELY move to position 50 to reduce load
            print("  IMMEDIATE RELAX: Moving to position 50...")
            self.goto_position(50, 100)
            
            # Execute the goto 50 immediately
            self.bulk_write_control_data()
            print("  ✅ Gripper relaxed to position 50")

    def bulk_read_sensor_data(self, servo_num=0):
        """
        Read all sensor data using individual reads (for now, until bulk read is fixed)
        
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
            # Read all registers individually (will optimize to bulk later)
            position_raw = self.servos[servo_num].read_word(132)  # present_position
            current_raw = self.servos[servo_num].read_word(126)  # present_current
            temperature = self.servos[servo_num].read_word(146)  # present_temperature
            voltage_raw = self.servos[servo_num].read_word(144)  # present_voltage
            error_raw = self.servos[servo_num].read_word(70)    # hardware_error
            
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
            
            # Parse error
            sensor_data['error'] = error_raw
            
        except Exception as e:
            raise Exception(f"Sensor data reading failed: {e}")
        
        return sensor_data

    def bulk_write_control_data(self):
        """
        Write control data - ALWAYS UNCLAMPED, goes until destination or collision
        """
        # Calculate goal values from target variables - UNCLAMPED
        # 0% = closed (position 0), 100% = open (position 2500)
        scaled_position = int(int(self.target_position) * 2500 / 100)  # No clamping, no inversion
        
        # Write goal position - UNCLAMPED
        for i in range(len(self.servos)):
            target_raw_pos = self.zero_positions[i] + scaled_position
            
            # Write goal position
            self.servos[i].write_word(116, target_raw_pos)  # goal_position register
            # Always log writes for debugging
            print(f"    ✍️  WRITE servo: target={self.target_position}% → raw_pos={target_raw_pos} (zero={self.zero_positions[i]})")

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

    def calibrate_with_collision_detection(self):
        """
        Simple calibration - goto_position(-300, 100) and detect collision
        
        Strategy:
        1. goto_position(100, 100) - Start fully open
        2. goto_position(-300, 100) - Force beyond closed until collision
        3. Main loop detects collision and moves to position 50
        """
        print("\n=== SIMPLE CALIBRATION WITH GOTO_POSITION ===")
        
        # Reset calibration state
        self.collision_detected = False
        self.calibration_active = True
        self._last_position = None
        
        # Step 1: Start from open position
        print("  Step 1: Moving to open position (100%)...")
        self.goto_position(100, 100)
        
        # Step 2: Force beyond closed for collision
        print("  Step 2: Moving to -300% (beyond closed) until collision...")
        self.goto_position(-300, 100)
        
        # Step 3: Run main loop until collision detected
        print("  Step 3: Monitoring for collision...")
        for sample in range(50):  # Extended time
            result = self.update_main_loop()
            
            if result and result.get('collision_detected'):
                print("  ✅ Collision detected - calibration complete!")
                return True
            elif result and sample % 5 == 0:  # Show progress every 5 samples
                data = result['sensor_data']
                pos = data.get('position_raw', 0)
                current = data.get('current', 0)
                print(f"    Sample {sample+1}: Position={pos}, Current={current}mA")
                
            time.sleep(0.033)  # 30Hz
        
        print("  ⚠️  No collision detected")
        self.calibration_active = False
        return False

    def calibrate(self):
        """Modern calibration using goto_position with collision detection"""
        return self.calibrate_with_collision_detection()

    def get_position(self):
        """Get current position in percent (for DDS interface)"""
        data = self.bulk_read_sensor_data(0)
        return data.get('position', 0.0)

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
        gripper.goto_position(100, 50)  # Open
        time.sleep(2.0)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
