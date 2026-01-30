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
import time
import logging
from .error_manager import create_error_manager


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

    GRIP_MAX = 2500 # maximum open position for grippers
    TORQUE_MAX = 1023 # maximum torque - full Dynamixel range (was 800)
    TORQUE_HOLD = 13 # This is percentage of TORQUE_MAX. In absolute units: holding torque - MX-64=100, MX-106=80

    OPEN_DUAL_GEN1_POS = 1.5707
    CLOSE_DUAL_GEN1_POS = -0.27

    OPEN_DUAL_GEN2_POS = 0.0
    CLOSE_DUAL_GEN2_POS = 1.94

    OPEN_DUAL_GEN2_SINGLE_MOUNT_POS = -1.5707
    CLOSE_DUAL_GEN2_SINGLE_MOUNT_POS = 0.27

    OPEN_DUAL_GEN2_TRIPLE_MOUNT_POS = -1.5707
    CLOSE_DUAL_GEN2_TRIPLE_MOUNT_POS = 0.27

    OPEN_QUAD_POS = 1.5707
    CLOSE_QUAD_POS = -0.27

    MIN_SIMULATED_EFFORT = 0.0
    MAX_SIMULATED_EFFORT = 1.0

    def __init__(self, connection, name, servo_ids, enable_error_manager=True):
        self.name = name
        self.servos = [Robotis_Servo( connection, servo_id ) for servo_id in servo_ids]
        
        # Initialize error managers for each servo
        self.error_managers = []
        if enable_error_manager:
            for servo in self.servos:
                try:
                    error_mgr = create_error_manager(servo, auto_recover=True, max_recovery_attempts=3)
                    self.error_managers.append(error_mgr)
                    
                    # Check and clear any existing errors
                    error_code, description, severity = error_mgr.check_hardware_errors()
                    if error_code is not None and error_code != 0:
                        logging.warning(f"Servo {servo.servo_id}: {description} - attempting recovery")
                        if error_mgr.attempt_recovery(error_code):
                            logging.info(f"Servo {servo.servo_id}: Recovery successful")
                        else:
                            logging.error(f"Servo {servo.servo_id}: Recovery failed - manual intervention may be required")
                except Exception as e:
                    logging.error(f"Failed to initialize error manager for servo {servo.servo_id}: {e}")
                    # Continue without error manager for this servo
        
        # Protocol 2.0: Set operating mode (must disable torque first)
        for servo in self.servos:
            servo.write_address(64, [0])  # Disable torque
            time.sleep(0.05)
            servo.ensure_byte_set(11, 3)  # Operating Mode = 3 (Position Control)
            servo.write_address(64, [1])  # Re-enable torque
            time.sleep(0.05)
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

    def calibrate(self):
        print("calibrating: " + self.name)

        for servo in self.servos:
            # Protocol 2.0 registers - must disable torque before changing operating mode:
            servo.write_address(64, [0])               # 1) "Torque Enable" to OFF
            time.sleep(0.1)                            # Wait for torque to disable
            servo.write_address(11, [4])               # 2) "Operating Mode" = 4 (Extended Position Control for multi-turn)
            servo.write_word(38, 1941)                 # 3) "Current Limit" to max (6521.76 mA)
            servo.write_address(64, [1])               # 4) "Torque Enable" to ON
            time.sleep(0.1)                            # Wait for torque to enable
            servo.write_word(116, -10000)              # 5) "Goal Position" - large negative to close

        time.sleep(3.0)                                # 6) Wait for gripper to reach hard stop and stall

        for i in range(len(self.servos)):
            servo = self.servos[i]
            servo.write_address(64, [0])               # Disable torque to set homing offset
            time.sleep(0.1)
            servo.write_word(20, 0)                    # 7) "Homing Offset" to 0
            self.zero_positions[i] = servo.read_word_signed(132) # 8) Read "Present Position" as zero point
            servo.write_address(64, [1])               # Re-enable torque
            time.sleep(0.1)

        print("calibration done")

    def set_max_effort(self, max_effort):
        # Protocol 2.0: Use Current Limit (register 38) instead of Torque Limit
        # range 0-100% (0-100)
        # max current limit is 1941 (6521.76 mA)

        moving_current = self.scale(max_effort, 1941)

        print("set_max_effort(%d): current limit: %d (position control)"%(max_effort, moving_current))
        for servo in self.servos:
            servo.write_word(38, moving_current) # Current Limit for position control mode

    def _goto_position(self, position):
        for servo in self.servos:
            set_torque_mode(servo, False)
        for i in range(len(self.servos)):
            self.servos[i].write_word(116, self.zero_positions[i] + position)  # Protocol 2.0: Goal Position = 116
        # wait_for_stop removed for non-blocking teleoperation control

    def _close_with_torque(self):
        for servo in self.servos:
            set_torque_mode(servo, True)
        wait_for_stop(self.servos[0])  # Keep wait_for_stop for torque-based closing

    def get_position(self, servo_num=0, \
            use_percentages = True, gripper_module = 'dual_gen1'):

        servo_position = self.servos[servo_num].read_word_signed(132) - self.zero_positions[servo_num]  # Protocol 2.0: Present Position = 132
        current_position = self.down_scale(servo_position, self.GRIP_MAX)

        if not use_percentages:

            if gripper_module == 'dual_gen1':
                current_position = remap(current_position, \
                    100.0, 0.0, self.OPEN_DUAL_GEN1_POS, self.CLOSE_DUAL_GEN1_POS)

            elif gripper_module == 'dual_gen2':
                current_position = remap(current_position, \
                    100.0, 0.0, self.OPEN_DUAL_GEN2_POS, self.CLOSE_DUAL_GEN2_POS)

            elif gripper_module == 'dual_gen2_single_mount':
                current_position = remap(current_position, \
                    100.0, 0.0, self.OPEN_DUAL_GEN2_SINGLE_MOUNT_POS, self.CLOSE_DUAL_GEN2_SINGLE_MOUNT_POS)

            elif gripper_module == 'dual_gen2_triple_mount':
                current_position = remap(current_position, \
                    100.0, 0.0, self.OPEN_DUAL_GEN2_TRIPLE_MOUNT_POS, self.CLOSE_DUAL_GEN2_TRIPLE_MOUNT_POS)

            elif gripper_module == 'quad':
                current_position = remap(current_position, \
                    100.0, 0.0, self.OPEN_QUAD_POS, self.CLOSE_QUAD_POS)

        return current_position

    def get_positions(self):
        positions = []
        for i in range(len(self.servos)):
            positions.append(self.get_position(i))
        return positions

    def move_with_torque_management(self, position, closing_torque, \
            use_percentages = True, gripper_module = 'dual_gen1'):
        # High-level movement with torque management - NOT a simple goto command
        # This function manages torque and may affect position reference
        # position: 0..100, 0 - close, 100 - open
        # closing_torque: 0..100

        if not use_percentages:

            closing_torque = remap(closing_torque, \
                self.MIN_SIMULATED_EFFORT, self.MAX_SIMULATED_EFFORT, 0, 100)

            if gripper_module == 'dual_gen1':
                position = remap(position, \
                    self.OPEN_DUAL_GEN1_POS, self.CLOSE_DUAL_GEN1_POS, 100, 0)

            elif gripper_module == 'dual_gen2':
                position = remap(position, \
                    self.OPEN_DUAL_GEN2_POS, self.CLOSE_DUAL_GEN2_POS, 100, 0)

            elif gripper_module == 'dual_gen2_single_mount':
                position = remap(position, \
                    self.OPEN_DUAL_GEN2_SINGLE_MOUNT_POS, self.CLOSE_DUAL_GEN2_SINGLE_MOUNT_POS, 100, 0)

            elif gripper_module == 'dual_gen2_triple_mount':
                position = remap(position, \
                    self.OPEN_DUAL_GEN2_TRIPLE_MOUNT_POS, self.CLOSE_DUAL_GEN2_TRIPLE_MOUNT_POS, 100, 0)

            elif gripper_module == 'quad':
                position = remap(position, \
                    self.OPEN_QUAD_POS, self.CLOSE_QUAD_POS, 100, 0)

        servo_position = self.scale(position, self.GRIP_MAX)
        print("move_with_torque_management(%d, %d): servo position %d"%(position, closing_torque, servo_position))
        self.set_max_effort(closing_torque)  # essentially sets velocity of movement, but also sets max_effort for initial half second of grasp.

        if position == 0:
            self._close_with_torque()
        else:
            self._goto_position(servo_position)

        # Sets torque to keep gripper in position, but does not apply torque if there is no load.
        # This does not provide continuous grasping torque.
        holding_torque = min(self.TORQUE_HOLD, closing_torque)
        self.set_max_effort(holding_torque)
        print("move_with_torque_management done")

    
    def release(self):
        for servo in self.servos:
            set_torque_mode(servo, False)

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
