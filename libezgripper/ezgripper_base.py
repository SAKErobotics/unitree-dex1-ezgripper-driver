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
        
        # Check initial servo state before doing anything
        print(f"=== INITIAL SERVO STATE CHECK FOR {name} ===")
        for i, servo in enumerate(self.servos):
            print(f"Servo {i+1} (ID {servo_ids[i]}):")
            try:
                pos = servo.read_word_signed(config.reg_present_position)
                temp = servo.read_word(config.reg_present_temperature)
                voltage = servo.read_word(config.reg_present_voltage) / 10.0
                current = servo.read_word_signed(config.reg_present_current)
                error = servo.read_word(config.reg_hardware_error)
                torque = servo.read_word(config.reg_torque_enable)
                mode = servo.read_word(config.reg_operating_mode)
                
                print(f"  Position: {pos}")
                print(f"  Temperature: {temp}°C")
                print(f"  Voltage: {voltage}V")
                print(f"  Current: {current}")
                print(f"  Hardware Error: {error}")
                if error != 0:
                    print(f"    ERROR BITS: {error:08b}")
                    if error & 0x01: print("      - Input Voltage Error")
                    if error & 0x02: print("      - Overheating Error")
                    if error & 0x04: print("      - Motor Encoder Error")
                    if error & 0x08: print("      - Circuit Electrical Shock Error")
                    if error & 0x10: print("      - Overload Error")
                    if error & 0x20: print("      - Stalled Error")
                    if error & 0x40: print("      - Invalid Instruction Error")
                    if error & 0x80: print("      - Invalid CRC Error")
                    
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
        for servo in self.servos:
            # Monitor before initialization
            try:
                pos = servo.read_word_signed(config.reg_present_position)
                temp = servo.read_word(config.reg_present_temperature)
                voltage = servo.read_word(config.reg_present_voltage) / 10.0
                current = servo.read_word_signed(config.reg_present_current)
                error = servo.read_word(config.reg_hardware_error)
                print(f"  Pre-init status: pos={pos}, temp={temp}°C, volt={voltage}V, current={current}, error={error}")
            except Exception as e:
                print(f"  Warning: Could not read pre-init status: {e}")
            
            print(f"  Disabling torque for initialization...")
            servo.write_address(config.reg_torque_enable, [0])  # Disable torque
            time.sleep(0.05)
            
            # Check status after torque disable
            try:
                error = servo.read_word(config.reg_hardware_error)
                print(f"  Status after torque disable: error={error}")
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
            
            # Final status check
            try:
                error = servo.read_word(config.reg_hardware_error)
                print(f"  Final init status: error={error}")
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

        for servo in self.servos:
            # Monitor before calibration
            try:
                pos = servo.read_word_signed(self.config.reg_present_position)
                temp = servo.read_word(self.config.reg_present_temperature)
                voltage = servo.read_word(self.config.reg_present_voltage) / 10.0
                current = servo.read_word_signed(self.config.reg_present_current)
                error = servo.read_word(self.config.reg_hardware_error)
                print(f"  Pre-calibration status: pos={pos}, temp={temp}°C, volt={voltage}V, current={current}, error={error}")
                
                # Log pre-calibration status
                with open(error_log, 'a') as f:
                    self.log_error(f, "PRE-CALIBRATION", {
                        'position': pos,
                        'temperature': temp,
                        'voltage': voltage,
                        'current': current,
                        'hardware_error': error,
                        'error_bits': f"{error:08b}" if error else "0"
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

        # Check final status after calibration
        print("\n=== POST-CALIBRATION STATUS CHECK ===")
        for i, servo in enumerate(self.servos):
            print(f"Servo {i+1}:")
            try:
                error = servo.read_word(self.config.reg_hardware_error)
                temp = servo.read_word(self.config.reg_present_temperature)
                pos = servo.read_word_signed(self.config.reg_present_position)
                current = servo.read_word_signed(self.config.reg_present_current)
                
                print(f"  Hardware Error: {error}")
                if error != 0:
                    print(f"    ERROR BITS: {error:08b}")
                    if error & 0x01: print("      - Input Voltage Error")
                    if error & 0x02: print("      - Overheating Error")
                    if error & 0x04: print("      - Motor Encoder Error")
                    if error & 0x08: print("      - Circuit Electrical Shock Error")
                    if error & 0x10: print("      - Overload Error")
                    if error & 0x20: print("      - Stalled Error")
                    if error & 0x40: print("      - Invalid Instruction Error")
                    if error & 0x80: print("      - Invalid CRC Error")
                print(f"  Temperature: {temp}°C")
                print(f"  Position: {pos}")
                print(f"  Current: {current}")
            except Exception as e:
                print(f"  ERROR reading post-calibration status: {e}")
        print("=" * 50)
        
        print("calibration done")

    def set_max_effort(self, max_effort):
        # Protocol 2.0: Use Goal Current (RAM) for dynamic current control
        # range 0-100% (0-100)
        # Goal Current (register 102) is RAM - can write with torque enabled, no EEPROM wear

        goal_current = self.scale(max_effort, self.config.max_current)

        print("set_max_effort(%d): goal current: %d (position control)"%(max_effort, goal_current))
        for servo in self.servos:
            # Write to Goal Current (RAM register - 2 bytes, fast, no EEPROM wear)
            data = [goal_current & 0xFF, (goal_current >> 8) & 0xFF]
            servo.write_address(self.config.reg_goal_current, data)

    def _goto_position(self, position):
        # Operating mode already set to Position Control (3) during initialization
        # No need to call set_torque_mode - it would require torque disabled (EEPROM write)
        for i in range(len(self.servos)):
            self.servos[i].write_word(self.config.reg_goal_position, self.zero_positions[i] + position)
        # wait_for_stop removed for non-blocking teleoperation control

    # _close_with_torque removed - always use position control

    def get_position(self, servo_num=0, \
            use_percentages = True, gripper_module = 'dual_gen1'):

        servo_position = self.servos[servo_num].read_word_signed(self.config.reg_present_position) - self.zero_positions[servo_num]
        current_position = self.down_scale(servo_position, self.config.grip_max)

        if not use_percentages:
            # Use Dex1 mapping from config
            current_position = remap(current_position, \
                100.0, 0.0, self.config.dex1_open_radians, self.config.dex1_close_radians)

        return current_position

    def get_positions(self):
        positions = []
        for i in range(len(self.servos)):
            positions.append(self.get_position(i))
        return positions

    def move_with_torque_management(self, position, closing_torque, \
            use_percentages = True, gripper_module = 'dual_gen1'):
        # Simplified movement - always use position control
        # position: 0..100, 0 - close, 100 - open
        # closing_torque: 0..100 (legacy parameter, not used)

        if not use_percentages:
            # Convert from Dex1 radians to percentage
            position = remap(position, \
                self.config.dex1_open_radians, self.config.dex1_close_radians, 100, 0)

        servo_position = self.scale(position, self.config.grip_max)
        print("move_to_position(%d): servo position %d"%(position, servo_position))
        
        # Always move at maximum current for FAST movement
        self.set_max_effort(100)
        self._goto_position(servo_position)
        
        print("move_to_position done")

    
    def release(self):
        # Release by setting current to 0 (no torque)
        for servo in self.servos:
            data = [0 & 0xFF, (0 >> 8) & 0xFF]
            servo.write_address(self.config.reg_goal_current, data)

    def open(self):
        self.move_with_torque_management(100, 100)

    def get_temperatures(self):
        temperatures = []
        for servo in self.servos:
            temperatures.append(servo.read_temperature())
        return temperatures

if __name__ == '__main__':
    # Sample code
    connection = create_connection(dev_name='/dev/ttyUSB0', baudrate=57600)
    #connection = create_connection(dev_name='hwgrep://0403:6001', baudrate=57600)
    #connection = create_connection(dev_name='socket://127.0.0.1:4000', baudrate=57600)
    gripper = Gripper(connection, 'gripper1', [1])
    #gripper = Gripper(connection, 'gripper1', [1,2])

    print("temperatures:", gripper.get_temperatures())

    gripper.calibrate()
    gripper.goto_position(100, 100) # open
    time.sleep(2.0)
    print("positions:", gripper.get_positions())
    gripper.goto_position(0, 50) # close
    time.sleep(2.0)
    print("positions:", gripper.get_positions())
    gripper.goto_position(100, 50) # open
    time.sleep(2.0)
    gripper.goto_position(70, 100) # position 70
    print("positions:", gripper.get_positions())
    print("position:", gripper.get_position())
    print("DONE")
