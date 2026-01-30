#!/usr/bin/env python3
"""Test direct servo movement in a small range (+-60 units)."""

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

        logging.info("Ensuring torque is enabled...")
        servo.write_word(config.reg_torque_enable, 1)
        time.sleep(0.1)

        # Get initial position
        start_pos = servo.read_word_signed(config.reg_present_position)
        logging.info(f"Starting raw position: {start_pos}")

        # Test loop
        for i in range(5):
            logging.info(f"\n--- Cycle {i+1}/5 ---")

            # Move +60
            target_plus = start_pos + 60
            logging.info(f"Moving to {target_plus} (+60)...")
            servo.write_word(config.reg_goal_position, target_plus)
            time.sleep(1)
            pos_plus = servo.read_word_signed(config.reg_present_position)
            logging.info(f"  Position after +60: {pos_plus} (Moved: {pos_plus - start_pos})")

            # Move -60
            target_minus = start_pos - 60
            logging.info(f"Moving to {target_minus} (-60)...")
            servo.write_word(config.reg_goal_position, target_minus)
            time.sleep(1)
            pos_minus = servo.read_word_signed(config.reg_present_position)
            logging.info(f"  Position after -60: {pos_minus} (Moved: {pos_minus - start_pos})")

            # Return to start
            logging.info(f"Returning to start position {start_pos}...")
            servo.write_word(config.reg_goal_position, start_pos)
            time.sleep(1)

        logging.info("\nTest complete.")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
