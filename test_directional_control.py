#!/usr/bin/env python3
"""Verify correct directional movement after calibration."""

import time
import logging
import argparse
from libezgripper.config import load_config
from libezgripper import create_connection
from libezgripper.ezgripper_base import Gripper

def get_raw_position(gripper):
    """Get the raw servo position without any offsets."""
    return gripper.servos[0].read_word_signed(gripper.config.reg_present_position)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Test directional control after calibration.")
    parser.add_argument("--dev", default="/dev/ttyUSB0", help="Serial device")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

    try:
        # Setup
        config = load_config()
        conn = create_connection(args.dev, config.comm_baudrate)
        gripper = Gripper(conn, 'left', [1], config)

        # 1. Calibrate
        logging.info("Calibrating gripper...")
        gripper.calibrate()
        logging.info(f"Calibration complete. Logical zero (0% open) is at raw position {gripper.zero_positions[0]}")
        time.sleep(1)

        # 2. Go to 50%
        logging.info("Moving to 50%...")
        gripper.goto_position(50, 100)
        time.sleep(2)
        pos_50 = get_raw_position(gripper)
        pct_50 = gripper.get_position()
        logging.info(f"At 50%: raw_pos={pos_50}, pct={pct_50:.1f}%")

        # 3. Go to 0% (Full Open)
        logging.info("Moving to 0% (Full Open)...")
        gripper.goto_position(0, 100)
        time.sleep(2)
        pos_0 = get_raw_position(gripper)
        pct_0 = gripper.get_position()
        logging.info(f"At 0%: raw_pos={pos_0}, pct={pct_0:.1f}%")

        # 4. Go to 100% (Full Close)
        logging.info("Moving to 100% (Full Close)...")
        gripper.goto_position(100, 100)
        time.sleep(2)
        pos_100 = get_raw_position(gripper)
        pct_100 = gripper.get_position()
        logging.info(f"At 100%: raw_pos={pos_100}, pct={pct_100:.1f}%")

        # Verification
        logging.info("\n--- Verification ---")
        logging.info(f"Raw positions: Open={pos_0}, Mid={pos_50}, Close={pos_100}")
        if pos_0 > pos_50 > pos_100:
            logging.info("✓ SUCCESS: Gripper moved in the correct direction (raw position decreased as it closed).")
        else:
            logging.error("✗ FAILURE: Gripper moved in the wrong direction.")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
