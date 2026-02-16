#!/usr/bin/python

#####################################################################
# Software License Agreement (BSD License)
#
# Copyright (c) 2016, SAKE Robotics
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the copyright holder nor the names of its
#      contributors may be used to endorse or promote products derived from
#      this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
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
from .servo_init import smart_init_servo, log_eeprom_optimization
from dynamixel_sdk import GroupSyncRead, COMM_SUCCESS
import time
import logging


def set_torque_mode(servo, val):
    """
    Set operating mode for Protocol 2.0
    
    Operating Mode values:
    - 0: Current (Torque) Control Mode
    - 3: Position Control Mode (default)
    """
    if val:
        servo.write_address(11, [0])  # Protocol 2.0: Operating Mode = Current Control
    else:
        servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control

def wait_for_stop(servo):
    wait_start = time.time()
    last_position = 1000000 # read_encoder() cannot return more than 65536
    while True:
        current_position = servo.read_encoder()
        if current_position == last_position:
            break
        last_position = current_position
        time.sleep(0.1)

        if time.time() - wait_start > 5:
            break

def remap(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / \
            (in_max - in_min) + out_min

class Gripper:
    """Gripper control with configuration-based parameters"""

    def __init__(self, connection, name, servo_ids, config: Config):
        self.name = name
        self.config = config
        self.servos = [Robotis_Servo( connection, servo_id ) for servo_id in servo_ids]
        
        # Initialize zero positions (software-managed, set during calibration)
        self.zero_positions = [0] * len(servo_ids)
        
        # Validate zero positions start at zero (software-managed)
        print(f"=== INITIALIZATION FOR {name} ===")
        print(f"  Zero positions initialized: {self.zero_positions}")
        print(f"  Servo IDs: {servo_ids}")
        print(f"  Number of servos: {len(self.servos)}")
        print("  Zero positions will be set during calibration")
        print("=" * 50)
        
        # Smart EEPROM initialization (read before write to prevent wear)
        # TEMPORARILY DISABLED FOR TESTING
        # if config.comm_smart_init:
        #     for servo in self.servos:
        #         results = smart_init_servo(servo, config)
        #         log_eeprom_optimization(results)
        
        # Protocol 2.0: Set operating mode and current limit (must disable torque first)
        for i, servo in enumerate(self.servos):
            print(f"  Disabling torque for initialization...")
            servo.write_address(config.reg_torque_enable, [0])  # Disable torque
            time.sleep(0.05)
            
            # Check operating mode before writing (EEPROM register 11)
            print(f"  Checking operating mode...")
            current_mode = servo.read_word(config.reg_operating_mode)
            if current_mode != config.operating_mode:
                print(f"Updating operating mode: {current_mode} -> {config.operating_mode}")
                servo.ensure_byte_set(config.reg_operating_mode, config.operating_mode)
            else:
                print(f"Operating mode already correct: {config.operating_mode}")
            
            # Check current limit before writing (EEPROM register 38)
            print(f"  Checking current limit...")
            current_limit = servo.read_word(config.reg_current_limit)
            if current_limit != config.max_current:
                print(f"Updating current limit: {current_limit} -> {config.max_current}")
                servo.write_word(config.reg_current_limit, config.max_current)
            else:
                print(f"Current limit already correct: {config.max_current}")
            
            # Check PWM limit if in PWM mode (EEPROM register 36)
            if config.operating_mode == 16:
                print(f"  Checking PWM limit...")
                pwm_limit = servo.read_word(config.reg_pwm_limit)
                if pwm_limit != config.pwm_limit:
                    print(f"Updating PWM limit: {pwm_limit} -> {config.pwm_limit}")
                    servo.write_word(config.reg_pwm_limit, config.pwm_limit)
                else:
                    print(f"PWM limit already correct: {config.pwm_limit}")
            
            print(f"  Re-enabling torque...")
            servo.write_address(config.reg_torque_enable, [1])  # Re-enable torque
            time.sleep(0.05)
            
            print("  Initialization complete")

    def scale(self, n, to_max):
        # Scale from 0..100 to 0..to_max
        result = int(n * to_max / 100)
        if result > to_max: result = to_max
        if result < 0: result = 0
        return result

    def down_scale (self, n, to_max):
        # Scale from 0..to_max to 0..100
        result = int(round(n * 100.0 / to_max))
        if result > 100: result = 100
        if result < 0: result = 0
        return result

    def log_error(self, f, step, data):
        """Log detailed error information"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        f.write(f"[{timestamp}] {step}\n")
        for key, value in data.items():
            f.write(f"  {key}: {value}\n")
        f.write("\n")
        f.flush()  # Ensure it's written immediately

    def calibrate_with_collision_detection(self):
        """
        Modern calibration using goto_position with collision detection.
        
        Strategy:
        1. Use goto_position(-300, 100) - Move to huge negative destination (close gripper)
        2. Detect collision using OR of current spike OR position stagnation
        3. When collision detected - immediately record offset position
        4. Move to position 50 - take load off gripper
        """
        print("\n=== MODERN CALIBRATION WITH COLLISION DETECTION ===")
        
        # Ensure torque is enabled
        for servo in self.servos:
            servo.write_address(self.config.reg_torque_enable, [1])
        
        time.sleep(0.1)
        
        # Step 1: Move to negative position to find collision
        print("  Step 1: Moving to negative position to detect collision...")
        print("  Command: goto_position(-300, 100)")
        
        # Start movement
        self.goto_position(-300, 100)
        
        # Step 2: Monitor for collision using bulk read @ 30Hz
        print("  Step 2: Monitoring for collision (position stagnation OR current spike)...")
        
        collision_detected = False
        last_position = None
        position_stagnant_time = 0
        check_interval = 0.033  # 30Hz = 33ms
        stagnation_threshold = 2  # Consider stagnant if moved < 2 units
        stagnation_time_threshold = 0.1  # 100ms of stagnation = collision
        current_threshold = 800  # Current spike threshold
        
        start_time = time.time()
        
        while not collision_detected and (time.time() - start_time) < 5.0:  # 5 second timeout
            time.sleep(check_interval)
            
            try:
                # Bulk read all sensor data
                sensor_data = self.bulk_read_sensor_data(0)
                current_position = sensor_data.get('position_raw', 0)
                current_current = abs(sensor_data.get('current', 0))
                
                # Collision detection logic (OR condition)
                collision_reason = None
                
                # Check 1: Position stagnation
                if last_position is not None:
                    movement = abs(current_position - last_position)
                    if movement < stagnation_threshold:
                        position_stagnant_time += check_interval
                        if position_stagnant_time >= stagnation_time_threshold:
                            collision_reason = f"position stagnation for {position_stagnant_time:.3f}s"
                            collision_detected = True
                    else:
                        position_stagnant_time = 0  # Reset if moving
                
                # Check 2: Current spike
                if current_current > current_threshold:
                    collision_reason = f"current spike: {current_current}mA > {current_threshold}mA"
                    collision_detected = True
                
                # Debug output
                if time.time() - start_time < 1.0:  # Only show first second
                    print(f"    Pos: {current_position}, Current: {current_current}mA, Movement: {movement if last_position else 'N/A'}")
                
                last_position = current_position
                
                if collision_detected:
                    print(f"  ✅ COLLISION DETECTED: {collision_reason}")
                    print(f"     Position at collision: {current_position}")
                    break
                    
            except Exception as e:
                print(f"    Error reading sensor data: {e}")
                break
        
        if not collision_detected:
            print("  ⚠️  No collision detected within 5 seconds")
            return False
        
        # Step 3: Record zero position from collision point
        print("  Step 3: Recording zero position from collision...")
        for i in range(len(self.servos)):
            try:
                sensor_data = self.bulk_read_sensor_data(i)
                collision_position = sensor_data.get('position_raw', 0)
                self.zero_positions[i] = collision_position
                print(f"  Servo {i+1}: zero position set to {self.zero_positions[i]} (collision point)")
            except Exception as e:
                print(f"  ERROR: Could not record zero position: {e}")
                return False
        
        # Step 4: Move to position 50 to take load off gripper
        print("  Step 4: Moving to position 50 to take load off gripper...")
        self.goto_position(50, 100)
        
        # Wait for movement to complete
        time.sleep(0.5)
        
        # Verify final position
        try:
            final_data = self.bulk_read_sensor_data(0)
            final_position = final_data.get('position', 0)
            print(f"  Final position: {final_position:.1f}%")
        except Exception as e:
            print(f"  Warning: Could not verify final position: {e}")
        
        print("  ✅ Modern calibration complete!")

def calibrate(self):
        """Modern calibration using goto_position with collision detection"""
        return self.calibrate_with_collision_detection()

    def goto_position(self, position_pct, effort_pct):
        """
        Go to a position with a given effort.
        
        Args:
            position_pct: Target position (0% = fully open, 100% = fully closed)
            effort_pct: Effort/current limit (0-100%)
        """
        # Invert: 0% = fully open (grip_max), 100% = fully closed (0)
        # This matches the physical operation where opening increases raw position
        inverted_pct = 100 - int(position_pct)
        scaled_position = self.scale(inverted_pct, self.config.grip_max)
        
        # Calculate goal current
        goal_current = self.scale(int(effort_pct), self.config.max_current)
        
        # BULK WRITE: Send current limit and position in single USB transaction
        for i in range(len(self.servos)):
            target_raw_pos = self.zero_positions[i] + scaled_position
            
            # Use regWrite for bulk operations (Protocol 2.0)
            # Step 1: Register write operations (no USB transmission yet)
            self.servos[i].dyn.packetHandler.regWrite(
                self.servos[i].dyn.portHandler,
                self.servos[i].servo_id,
                self.config.reg_goal_current,  # Address
                2,  # Data length (2 bytes for current)
                goal_current & 0xFF,  # Low byte
                (goal_current >> 8) & 0xFF  # High byte
            )
            
            self.servos[i].dyn.packetHandler.regWrite(
                self.servos[i].dyn.portHandler,
                self.servos[i].servo_id,
                self.config.reg_goal_position,  # Address
                4,  # Data length (4 bytes for position)
                target_raw_pos & 0xFF,  # Byte 0
                (target_raw_pos >> 8) & 0xFF,  # Byte 1
                (target_raw_pos >> 16) & 0xFF,  # Byte 2
                (target_raw_pos >> 24) & 0xFF   # Byte 3
            )
            
            # Step 2: Execute all registered writes in single USB transaction
            self.servos[i].dyn.packetHandler.action(
                self.servos[i].dyn.portHandler
            )

    
    
    def bulk_read_sensor_data(self, servo_num=0):
        """
        Read all sensor data in single USB transaction for efficiency
        
        ⚠️ WARNING: 'current' value is NOT real current measurement on MX series!
        It's the target current from PID controller, not actual current draw.
        Do NOT use for safety decisions or overload detection.
        
        Returns:
            dict: {
                'position': position_pct,           # Real encoder position
                'current': current_ma,              # ESTIMATED - NOT REAL on MX series
                'temperature': temp_c,              # Real temperature sensor
                'voltage': voltage_v,               # Real voltage measurement
                'error': error_code                 # Real hardware error status
            }
        """
        # TRUE BULK READ: Read all operational and status data in one transaction
        # Read all sensor data needed for 30Hz operation
        group_sync_read = GroupSyncRead(
            self.servos[servo_num].dyn.portHandler,
            self.servos[servo_num].dyn.packetHandler,
            self.config.reg_present_position,  # Start with position
            2  # Position is 2 bytes
        )
        
        # Add parameter for servo
        param = GroupSyncRead.addParam(group_sync_read, self.servos[servo_num].servo_id)
        
        # Execute single bulk read transaction
        comm_result = group_sync_read.txRxPacket()
        
        if comm_result != COMM_SUCCESS:
            # No fallback - let the error propagate to identify real issues
            raise Exception(f"Bulk read failed with comm_result: {comm_result}")
        
        # Parse all results from single transaction
        sensor_data = {}
        try:
            # Get all operational data in single bulk read transaction
            position_data = group_sync_read.getData(param, self.config.reg_present_position, 2)
            current_data = group_sync_read.getData(param, self.config.reg_present_current, 2)
            temperature_data = group_sync_read.getData(param, self.config.reg_present_temperature, 1)
            voltage_data = group_sync_read.getData(param, self.config.reg_present_voltage, 2)
            error_data = group_sync_read.getData(param, self.config.reg_hardware_error, 2)
            
            # Check if we got valid data
            if None in [position_data, current_data, temperature_data, voltage_data, error_data]:
                raise Exception("No data returned from bulk read")
            
            # Parse position (2 bytes) - servo position is raw, offset managed in software
            if isinstance(position_data, int):
                position_raw = position_data
            else:
                position_raw = (position_data[1] << 8) | position_data[0]
            
            # Apply software offset for normal operation
            servo_position = position_raw - self.zero_positions[servo_num]
            raw_pct = self.down_scale(servo_position, self.config.grip_max)
            sensor_data['position'] = 100 - raw_pct  # Inverted
            
            # Parse current (2 bytes)
            if isinstance(current_data, int):
                current_raw = current_data
            else:
                current_raw = (current_data[1] << 8) | current_data[0]
            sensor_data['current'] = self._sign_extend_16bit(current_raw)
            
            # Parse temperature (1 byte)
            sensor_data['temperature'] = temperature_data[0] if isinstance(temperature_data, list) else temperature_data
            
            # Parse voltage (2 bytes)
            if isinstance(voltage_data, int):
                voltage_raw = voltage_data
            else:
                voltage_raw = (voltage_data[1] << 8) | voltage_data[0]
            sensor_data['voltage'] = voltage_raw / 10.0  # Convert to volts
            
            # Parse error (2 bytes)
            if isinstance(error_data, int):
                error_raw = error_data
            else:
                error_raw = (error_data[1] << 8) | error_data[0]
            sensor_data['error'] = error_raw
            sensor_data['error_details'] = self._parse_error_bits(error_raw)
            
        except Exception as e:
            # No fallback - let the error propagate to identify real issues
            raise Exception(f"Bulk read data parsing failed: {e}")
        finally:
            # Clean up
            group_sync_read.clearParam()
            
        return sensor_data

    def _sign_extend_16bit(self, value):
        """Convert 16-bit signed value from servo to Python int"""
        if value & 0x8000:
            return value - 0x10000
        return value

    def _parse_error_bits(self, error_code):
        """Parse Dynamixel error register bits into human-readable descriptions"""
        error_details = {
            'raw_error': error_code,
            'has_error': error_code != 0,
            'errors': []  # Just list the errors for logging
        }
        
        if error_code == 0:
            return error_details
            
        # Parse each error bit - SIMPLE: any error = torque off
        if error_code & 0x01:
            error_details['errors'].append('Input Voltage Error')
            
        if error_code & 0x02:
            error_details['errors'].append('Overheating Error')
            
        if error_code & 0x04:
            error_details['errors'].append('Motor Encoder Error')
            
        if error_code & 0x08:
            error_details['errors'].append('Circuit Electrical Shock Error')
            
        if error_code & 0x10:
            error_details['errors'].append('Overload Error')
            
        if error_code & 0x20:
            error_details['errors'].append('Stalled Error')
            
        if error_code & 0x40:
            error_details['errors'].append('Invalid Instruction Error')
            
        if error_code & 0x80:
            error_details['errors'].append('Invalid CRC Error')
            
        return error_details

    def disable_torque(self):
        """Set torque to zero - simple protection"""
        # BULK WRITE: Use regWrite + action for all servos
        for i in range(len(self.servos)):
            # Use regWrite for bulk operations (no USB transmission yet)
            self.servos[i].dyn.packetHandler.regWrite(
                self.servos[i].dyn.portHandler,
                self.servos[i].servo_id,
                self.config.reg_torque_enable,  # Address
                1,  # Data length (1 byte for torque enable)
                0   # Disable torque
            )
        
        # Execute all writes in single USB transaction
        for servo in self.servos:
            servo.dyn.packetHandler.action(servo.dyn.portHandler)

    
    
        
    
    def move_with_torque_management(self, position, closing_torque, \
            use_percentages = True, gripper_module = 'dual_gen1'):
        # Simplified movement - always use position control
        # position: 0..100, 0 - close, 100 - open
        # closing_torque: 0..100 (legacy parameter, not used)

        if not use_percentages:
            # Convert from Dex1 radians to percentage
            position = remap(position, \
                self.config.dex1_open_radians, self.config.dex1_close_radians, 100, 0)

        print("move_to_position(%d)"%(position))
        
        # Always move at maximum current for FAST movement
        self.goto_position(position, 100)
        
        print("move_to_position done")

    
    def release(self):
        # Release by setting current to 0 (no torque) - BULK WRITE
        for i in range(len(self.servos)):
            # Use regWrite for bulk operations (no USB transmission yet)
            self.servos[i].dyn.packetHandler.regWrite(
                self.servos[i].dyn.portHandler,
                self.servos[i].servo_id,
                self.config.reg_goal_current,  # Address
                2,  # Data length (2 bytes for current)
                0,  # Low byte
                0   # High byte
            )
        
        # Execute all writes in single USB transaction
        for servo in self.servos:
            servo.dyn.packetHandler.action(servo.dyn.portHandler)

    def open(self):
        self.move_with_torque_management(100, 100)

    def get_temperatures(self):
        # Use bulk read for all servos - extract temperature from sensor data
        temperatures = []
        for i in range(len(self.servos)):
            sensor_data = self.bulk_read_sensor_data(i)
            temperatures.append(sensor_data['temperature'])
        return temperatures

if __name__ == '__main__':
    # Sample code
    connection = create_connection(dev_name='/dev/ttyUSB0', baudrate=57600)
    #connection = create_connection(dev_name='hwgrep://0403:6001', baudrate=57600)
    #connection = create_connection(dev_name='socket://127.0.0.1:4000', baudrate=57600)
    gripper = Gripper(connection, 'gripper1', [1])
    #gripper = Gripper(connection, 'gripper1', [1,2])

    # Use bulk read for sensor data
    sensor_data = gripper.bulk_read_sensor_data()
    print("sensor data:", sensor_data)

    gripper.calibrate()
    gripper.goto_position(100, 100) # open
    time.sleep(2.0)
    sensor_data = gripper.bulk_read_sensor_data()
    print("sensor data after open:", sensor_data)
    gripper.goto_position(0, 50) # close
    time.sleep(2.0)
    sensor_data = gripper.bulk_read_sensor_data()
    print("sensor data after close:", sensor_data)
    gripper.goto_position(100, 50) # open
    time.sleep(2.0)
    gripper.goto_position(70, 100) # position 70
    sensor_data = gripper.bulk_read_sensor_data()
    print("sensor data at 70%:", sensor_data)
    print("DONE")
