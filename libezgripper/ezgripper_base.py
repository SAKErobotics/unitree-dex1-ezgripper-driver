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
        
        # Check initial servo state using BULK READ (single USB transaction)
        print(f"=== INITIAL SERVO STATE CHECK FOR {name} ===")
        for i, servo in enumerate(self.servos):
            print(f"Servo {i+1} (ID {servo_ids[i]}):")
            try:
                # Use bulk read for all sensor data
                sensor_data = self.bulk_read_sensor_data(i)
                
                # Read remaining individual registers (torque and mode)
                torque = servo.read_word(config.reg_torque_enable)
                mode = servo.read_word(config.reg_operating_mode)
                
                print(f"  Position: {sensor_data['position']:.1f}%")
                print(f"  Temperature: {sensor_data['temperature']}°C")
                print(f"  Voltage: {sensor_data['voltage']:.1f}V")
                print(f"  Current: {sensor_data['current']}mA")
                print(f"  Hardware Error: {sensor_data['error']}")
                if sensor_data['error'] != 0:
                    print(f"    ERROR BITS: {sensor_data['error']:08b}")
                    for error_desc in sensor_data['error_details']['errors']:
                        print(f"      - {error_desc}")
                    
                    # Clear hardware error by writing 0 to error register
                    print(f"  Clearing hardware error...")
                    servo.write_word(config.reg_hardware_error, 0)
                    time.sleep(0.1)
                    
                    # Verify error cleared
                    new_error = servo.read_word(config.reg_hardware_error)
                    print(f"  Error after clear: {new_error}")
                    
                print(f"  Torque Enable: {torque}")
                print(f"  Operating Mode: {mode}")
            except Exception as e:
                print(f"  ERROR reading servo state: {e}")
        print("=" * 50)
        
        # Smart EEPROM initialization (read before write to prevent wear)
        # TEMPORARILY DISABLED FOR TESTING
        # if config.comm_smart_init:
        #     for servo in self.servos:
        #         results = smart_init_servo(servo, config)
        #         log_eeprom_optimization(results)
        
        # Protocol 2.0: Set operating mode and current limit (must disable torque first)
        for i, servo in enumerate(self.servos):
            # Monitor before initialization using BULK READ
            try:
                sensor_data = self.bulk_read_sensor_data(i)
                print(f"  Pre-init status: pos={sensor_data['position']:.1f}%, temp={sensor_data['temperature']}°C, volt={sensor_data['voltage']:.1f}V, current={sensor_data['current']}mA, error={sensor_data['error']}")
            except Exception as e:
                print(f"  Warning: Could not read pre-init status: {e}")
            
            print(f"  Disabling torque for initialization...")
            servo.write_address(config.reg_torque_enable, [0])  # Disable torque
            time.sleep(0.05)
            
            # Check status after torque disable using BULK READ
            try:
                sensor_data = self.bulk_read_sensor_data(i)
                print(f"  Status after torque disable: error={sensor_data['error']}")
            except Exception as e:
                print(f"  Warning: Could not read status after torque disable: {e}")
            
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
            
            # Final status check using BULK READ
            try:
                sensor_data = self.bulk_read_sensor_data(i)
                print(f"  Final init status: error={sensor_data['error']}")
            except Exception as e:
                print(f"  Warning: Could not read final status: {e}")
        self.zero_positions = [0] * len(self.servos)

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

    def calibrate(self):
        """Calibration on command - can be called by robot when needed"""
        print("calibrating: " + self.name)
        
        # Create error log file
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        error_log = f"/tmp/calibration_error_{self.name}_{timestamp}.log"
        
        with open(error_log, 'w') as f:
            f.write(f"Calibration Error Log - {self.name}\n")
            f.write(f"Timestamp: {datetime.datetime.now()}\n")
            f.write("=" * 50 + "\n\n")

        for i, servo in enumerate(self.servos):
            # Monitor before calibration using BULK READ
            try:
                sensor_data = self.bulk_read_sensor_data(i)
                print(f"  Pre-calibration status: pos={sensor_data['position']:.1f}%, temp={sensor_data['temperature']}°C, volt={sensor_data['voltage']:.1f}V, current={sensor_data['current']}mA, error={sensor_data['error']}")
                
                # Log pre-calibration status
                with open(error_log, 'a') as f:
                    self.log_error(f, "PRE-CALIBRATION", {
                        'position': sensor_data['position'],
                        'temperature': sensor_data['temperature'],
                        'voltage': sensor_data['voltage'],
                        'current': sensor_data['current'],
                        'hardware_error': sensor_data['error'],
                        'error_bits': f"{sensor_data['error']:08b}" if sensor_data['error'] else "0"
                    })
            except Exception as e:
                print(f"  Warning: Could not read pre-calibration status: {e}")
                with open(error_log, 'a') as f:
                    self.log_error(f, "PRE-CALIBRATION ERROR", {'exception': str(e)})
            
            # Protocol 2.0 registers - must disable torque before changing operating mode:
            print(f"  Disabling torque...")
            servo.write_address(self.config.reg_torque_enable, [0])
            time.sleep(0.1)
            
            # Check status after torque disable
            try:
                error = servo.read_word(self.config.reg_hardware_error)
                print(f"  Status after torque disable: error={error}")
            except Exception as e:
                print(f"  Warning: Could not read status after torque disable: {e}")
            
            # Keep current operating mode (should already be set during init)
            # In PWM mode (16), we use Goal PWM instead of Goal Position
            
            # Re-enable torque
            print(f"  Re-enabling torque...")
            servo.write_address(self.config.reg_torque_enable, [1])
            time.sleep(0.05)
            
            # Check status before movement
            try:
                error = servo.read_word(self.config.reg_hardware_error)
                print(f"  Status before movement: error={error}")
            except Exception as e:
                print(f"  Warning: Could not read status before movement: {e}")
            
            # Use PWM mode for gentle calibration
            if self.config.operating_mode == 16:
                # PWM mode - use gentle negative PWM to move toward closed position
                print(f"  Moving with PWM={-self.config.calibration_pwm} (gentle close)...")
                servo.write_word(self.config.reg_goal_pwm, -self.config.calibration_pwm)
            else:
                # Position mode - use goal position
                print(f"  Moving to calibration position {self.config.calibration_position}...")
                servo.write_word(self.config.reg_goal_position, self.config.calibration_position)
            
        # Monitor position until fingers stop moving for 0.5 seconds
        print(f"  Monitoring until fingers stop moving for 0.5s...")
        stopped_time = 0
        last_position = None
        check_interval = 0.05  # Check every 50ms
        movement_threshold = 2  # Consider stopped if moved less than 2 units
        
        for servo in self.servos:
            while stopped_time < 0.5:
                time.sleep(check_interval)
                
                try:
                    current_position = servo.read_word_signed(self.config.reg_present_position)
                    
                    if last_position is not None:
                        movement = abs(current_position - last_position)
                        
                        if movement < movement_threshold:
                            stopped_time += check_interval
                            print(f"    Position stable: {current_position} (stopped for {stopped_time:.2f}s)")
                        else:
                            stopped_time = 0
                            print(f"    Moving: {current_position} (moved {movement} units)")
                    
                    last_position = current_position
                    
                except Exception as e:
                    print(f"    Error reading position: {e}")
                    break
        
        # Stop PWM movement
        if self.config.operating_mode == 16:
            for servo in self.servos:
                print(f"  Stopping PWM movement...")
                servo.write_word(self.config.reg_goal_pwm, 0)

        for i in range(len(self.servos)):
            servo = self.servos[i]
            # Monitor before reading zero position
            try:
                error = servo.read_word(self.config.reg_hardware_error)
                print(f"  Status before reading zero position: error={error}")
            except Exception as e:
                print(f"  ERROR: Could not read status before zero position: {e}")
                continue
            
            # Read current position as zero point (no homing offset write)
            try:
                self.zero_positions[i] = servo.read_word_signed(self.config.reg_present_position)
                print(f"  Servo {i+1}: zero position set to {self.zero_positions[i]}")
            except Exception as e:
                print(f"  ERROR: Could not read zero position: {e}")

        # Check final status after calibration using BULK READ
        print("\n=== POST-CALIBRATION STATUS CHECK ===")
        for i, servo in enumerate(self.servos):
            print(f"Servo {i+1}:")
            try:
                sensor_data = self.bulk_read_sensor_data(i)
                
                print(f"  Hardware Error: {sensor_data['error']}")
                if sensor_data['error'] != 0:
                    print(f"    ERROR BITS: {sensor_data['error']:08b}")
                    for error_desc in sensor_data['error_details']['errors']:
                        print(f"      - {error_desc}")
                print(f"  Temperature: {sensor_data['temperature']}°C")
                print(f"  Position: {sensor_data['position']:.1f}%")
                print(f"  Current: {sensor_data['current']}mA")
            except Exception as e:
                print(f"  ERROR reading post-calibration status: {e}")
        print("=" * 50)
        
        print("calibration done")

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
        
        Returns:
            dict: {
                'position': position_pct,
                'current': current_ma,
                'temperature': temp_c,
                'voltage': voltage_v,
                'error': error_code
            }
        """
        # TRUE BULK READ: Read all registers in one transaction
        # Use individual register reads in single transaction
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
            # Get position data to test bulk read
            position_data = group_sync_read.getData(param, self.config.reg_present_position, 2)
            
            # Debug: Check what getData actually returns
            print(f"DEBUG: position_data type: {type(position_data)}, value: {position_data}")
            
            # Check if we got valid data
            if position_data is None:
                raise Exception("No position data returned from bulk read")
            
            # Handle different return types from getData
            if isinstance(position_data, int):
                # getData returned a single int, not a list
                position_raw = position_data
            else:
                # getData returned a list of bytes
                position_raw = (position_data[1] << 8) | position_data[0]
            servo_position = position_raw - self.zero_positions[servo_num]
            raw_pct = self.down_scale(servo_position, self.config.grip_max)
            sensor_data['position'] = 100 - raw_pct  # Inverted
            
            # For now, set other values to defaults
            sensor_data['current'] = 0
            sensor_data['temperature'] = 0
            sensor_data['voltage'] = 0
            sensor_data['error'] = 0
            sensor_data['error_details'] = self._parse_error_bits(0)
            
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
