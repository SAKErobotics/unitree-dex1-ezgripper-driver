#!/usr/bin/env python3
"""Verify that the gripper opens passively when torque is disabled."""

import time
import logging
from libezgripper.config import load_config
from libezgripper import create_connection
from libezgripper.lib_robotis import Robotis_Servo

def main():
    """Main entry point"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

    try:
        # Setup
        config = load_config()
        conn = create_connection("/dev/ttyUSB0", config.comm_baudrate)
        servo = Robotis_Servo(conn, 1)

        # Ensure we are in PWM mode
        servo.write_word(config.reg_torque_enable, 0)
        time.sleep(0.1)
        servo.write_word(config.reg_operating_mode, 16)
        time.sleep(0.1)
        servo.write_word(config.reg_torque_enable, 1)
        time.sleep(0.1)

        # 1. Close the gripper part-way
        logging.info("Closing gripper part-way with PWM = 200...")
        servo.write_word(config.reg_goal_pwm, 200)
        time.sleep(1)
        pos_before = servo.read_word_signed(config.reg_present_position)
        logging.info(f"Position before release: {pos_before}")

        # 2. Disable torque to release
        logging.info("Disabling torque to release...")
        servo.write_word(config.reg_torque_enable, 0)
        time.sleep(2) # Allow time for springs to act

        # 3. Check position after release
        pos_after = servo.read_word_signed(config.reg_present_position)
        logging.info(f"Position after release: {pos_after}")

        # Verification
        movement = pos_after - pos_before
        logging.info(f"\n--- Verification ---")
        logging.info(f"Movement after torque release: {movement} units")
        if movement > 50: # Expecting a significant opening movement
            logging.info("✓ SUCCESS: Gripper opened passively as expected.")
        else:
            logging.error("✗ FAILURE: Gripper did not open significantly after torque release.")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
