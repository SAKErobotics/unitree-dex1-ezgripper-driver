#!/usr/bin/env python3
"""Test special handling for full open and full close commands."""

import time
import logging
import argparse
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_

def send_dds_command(publisher, q_radians):
    """Send a DDS command with the given q value."""
    motor_cmd = unitree_go_msg_dds__MotorCmd_()
    motor_cmd.q = q_radians
    motor_cmd.kp = 5.0
    motor_cmd.kd = 0.05
    motor_cmds = MotorCmds_()
    motor_cmds.cmds = [motor_cmd]
    publisher.Write(motor_cmds)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Test full open/close commands.")
    parser.add_argument("--side", required=True, choices=["left", "right"], help="Gripper side")
    parser.add_argument("--domain", type=int, default=1, help="DDS domain")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

    # Initialize DDS
    ChannelFactoryInitialize(args.domain)
    cmd_topic = f'rt/dex1/{args.side}/cmd'
    publisher = ChannelPublisher(cmd_topic, MotorCmds_)
    publisher.Init()

    try:
        logging.info("Starting test...")

        # 1. Command to 50%
        logging.info("Moving to 50%...")
        send_dds_command(publisher, 1.0) # q=1.0 is approx 50%
        time.sleep(3)

        # 2. Command to Full Close (100%)
        logging.info("Commanding Full Close (100%)...")
        send_dds_command(publisher, 1.94) # q=1.94 is 100%
        time.sleep(3)

        # 3. Command to Full Open (0%)
        logging.info("Commanding Full Open (0%)...")
        send_dds_command(publisher, 0.0)
        time.sleep(3)

        # 4. Command back to 50%
        logging.info("Moving back to 50%...")
        send_dds_command(publisher, 1.0)
        time.sleep(3)

        logging.info("Test complete.")

    finally:
        publisher.Close()

if __name__ == "__main__":
    main()
