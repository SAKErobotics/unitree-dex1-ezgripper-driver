#!/usr/bin/env python3
"""
Test script for EZGripper functionality
Tests calibration and basic open/close movements for both grippers
"""

import time
import argparse
import logging
import sys
import os

# Set CYCLONEDDS_HOME before importing cyclonedds
os.environ['CYCLONEDDS_HOME'] = '/opt/cyclonedds-0.10.2'

# Add unitree_sdk2_python to path
sys.path.insert(0, '/home/kavi/CascadeProjects/unitree_sdk2_python')

from libezgripper import create_connection, Gripper


def setup_logging():
    """Setup logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def test_gripper(device: str, side: str, iterations: int = 3):
    """Run test sequence on a single gripper"""
    logger = logging.getLogger(__name__)
    
    logger.info("")
    logger.info("="*60)
    logger.info(f"Testing {side.upper()} Gripper")
    logger.info("="*60)
    logger.info(f"Device: {device}")
    logger.info(f"Iterations: {iterations}")
    logger.info("")
    
    try:
        # Connect to gripper
        logger.info(f"Connecting to {side} gripper on {device}...")
        connection = create_connection(dev_name=device, baudrate=57600)
        gripper = Gripper(connection)
        
        # Calibrate
        logger.info("Step 1: Calibrating...")
        gripper.calibrate()
        logger.info("Calibration complete")
        logger.info("")
        
        # Test sequence
        for i in range(iterations):
            logger.info(f"="*60)
            logger.info(f"Iteration {i+1}/{iterations}")
            logger.info("="*60)
            
            # Open
            logger.info("Step 2: Opening gripper...")
            gripper.move_with_torque_management(100.0, 50.0)
            logger.info("Waiting 2 seconds...")
            time.sleep(2)
            
            # Close
            logger.info("Step 3: Closing gripper...")
            gripper.move_with_torque_management(0.0, 50.0)
            logger.info("Waiting 2 seconds...")
            time.sleep(2)
            
            logger.info("")
        
        # Move to 50%
        logger.info("="*60)
        logger.info(f"Final Position: 50% open")
        logger.info("="*60)
        gripper.move_with_torque_management(50.0, 30.0)
        logger.info(f"{side.upper()} gripper test complete - at 50%")
        
        return True
        
    except Exception as e:
        logger.error(f"{side.upper()} gripper test failed: {e}")
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="EZGripper Test Script")
    parser.add_argument("--right-dev", required=True,
                       help="Right gripper device path (e.g., /dev/ttyUSB0)")
    parser.add_argument("--left-dev", required=True,
                       help="Left gripper device path (e.g., /dev/ttyUSB1)")
    parser.add_argument("--iterations", type=int, default=3,
                       help="Number of open/close cycles (default: 3)")
    
    args = parser.parse_args()
    
    setup_logging()
    
    logger = logging.getLogger(__name__)
    
    # Test right gripper first
    logger.info("="*60)
    logger.info("EZGripper Test Sequence")
    logger.info("="*60)
    logger.info("Testing RIGHT gripper first, then LEFT gripper")
    logger.info("This helps verify correct mapping")
    logger.info("")
    
    # Test right gripper
    right_success = test_gripper(args.right_dev, "right", args.iterations)
    
    # Test left gripper
    left_success = test_gripper(args.left_dev, "left", args.iterations)
    
    # Summary
    logger.info("")
    logger.info("="*60)
    logger.info("Test Summary")
    logger.info("="*60)
    logger.info(f"Right gripper: {'✅ PASS' if right_success else '❌ FAIL'}")
    logger.info(f"Left gripper: {'✅ PASS' if left_success else '❌ FAIL'}")
    
    if right_success and left_success:
        logger.info("")
        logger.info("✅ All tests completed successfully")
        logger.info("")
        logger.info("Verify the grippers moved correctly:")
        logger.info("- Right gripper should be on the RIGHT side of the robot")
        logger.info("- Left gripper should be on the LEFT side of the robot")
        logger.info("")
        logger.info("If mapping is incorrect, swap the device paths and re-run")
        sys.exit(0)
    else:
        logger.info("")
        logger.info("❌ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
