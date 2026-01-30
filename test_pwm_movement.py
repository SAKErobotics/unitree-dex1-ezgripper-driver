#!/usr/bin/env python3
"""Test direct servo movement using Goal PWM commands."""

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

        logging.info("Ensuring torque is enabled and in PWM mode...")
        servo.write_word(config.reg_torque_enable, 1)
        servo.write_word(config.reg_operating_mode, 16) # PWM Control Mode
        time.sleep(0.1)

        # Get initial position
        start_pos = servo.read_word_signed(config.reg_present_position)
        logging.info(f"Starting raw position: {start_pos}")

        # Test loop
        for i in range(3):
            logging.info(f"\n--- Cycle {i+1}/3 ---")

            # Move with positive PWM
            logging.info("Moving with Goal PWM = 150...")
            servo.write_word(config.reg_goal_pwm, 150)
            time.sleep(1)
            pos_plus = servo.read_word_signed(config.reg_present_position)
            logging.info(f"  Position after +150 PWM: {pos_plus} (Moved: {pos_plus - start_pos})")

            # Move with negative PWM
            logging.info("Moving with Goal PWM = -150...")
            servo.write_word(config.reg_goal_pwm, -150)
            time.sleep(1)
            pos_minus = servo.read_word_signed(config.reg_present_position)
            logging.info(f"  Position after -150 PWM: {pos_minus} (Moved: {pos_minus - start_pos})")

        # Stop movement
        logging.info("\nStopping movement (Goal PWM = 0)...")
        servo.write_word(config.reg_goal_pwm, 0)
        time.sleep(0.5)
        final_pos = servo.read_word_signed(config.reg_present_position)
        logging.info(f"Final position: {final_pos}")

        logging.info("\nTest complete.")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
