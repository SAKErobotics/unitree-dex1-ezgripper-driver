#!/usr/bin/env python3
"""
Multi-gripper driver: all 3 EZGripper servos in one process, sharing a
single serial port FD protected by the bus lock in USB2Dynamixel_Device.

Why a separate file (not merged into the repo):
  - Experimental single-process architecture
  - 3-process launch in bridge.launch.py is the committed baseline
  - Switch to this once calibration robustness is verified

Servo layout:
  left   → servo ID 1
  right  → servo ID 2
  center → servo ID 3

Usage:
  python3 multi_gripper_driver.py [--device /dev/serial/by-path/...] [--domain 0]
"""

import argparse
import logging
import signal
import sys
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from libezgripper import create_connection
from ezgripper_dds_driver import CorrectedEZGripperDriver

SERIAL_BY_PATH = (
    "/dev/serial/by-path/pci-0000:00:14.0-usb-0:1.2:1.0-port0"
)

GRIPPER_MAP = [
    # (side, servo_id)
    ("left",   1),
    ("right",  2),
    ("center", 3),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("multi_gripper")


def parse_args():
    p = argparse.ArgumentParser(description="Multi-gripper single-process driver")
    p.add_argument("--device", default=SERIAL_BY_PATH,
                   help="Serial port (by-path preferred)")
    p.add_argument("--domain", type=int, default=0,
                   help="CycloneDDS domain ID")
    p.add_argument("--no-calibrate", action="store_true",
                   help="Skip startup calibration")
    return p.parse_args()


def main():
    args = parse_args()

    # --- One serial connection for all three grippers ---
    log.info(f"Opening serial port: {args.device}")
    connection = create_connection(dev_name=args.device, baudrate=1000000)
    log.info("Serial port open. Waiting for bus to settle...")
    time.sleep(2.0)

    # --- One ChannelFactoryInitialize for the whole process ---
    log.info(f"Initializing CycloneDDS (domain {args.domain})...")
    ChannelFactoryInitialize(args.domain)

    # --- Build drivers sharing the connection ---
    drivers = []
    for side, servo_id in GRIPPER_MAP:
        log.info(f"  Creating driver: {side} (servo {servo_id})")
        d = CorrectedEZGripperDriver(
            side=side,
            device=args.device,
            domain=args.domain,
            servo_id=servo_id,
            connection=connection,       # shared FD, protected by RLock
            dds_initialized=True,        # ChannelFactoryInitialize already called
        )
        drivers.append(d)

    # --- Startup calibration (sequential — one servo at a time, no contention) ---
    if not args.no_calibrate:
        for d in drivers:
            log.info(f"Calibrating {d.side} gripper...")
            try:
                ok = d.calibrate()
                if ok:
                    log.info(f"  {d.side}: calibration OK")
                else:
                    log.warning(f"  {d.side}: calibration reported an issue — continuing")
            except Exception as e:
                log.error(f"  {d.side}: calibration exception: {e} — continuing")
    else:
        log.info("Startup calibration skipped (--no-calibrate).")

    # --- Signal handling ---
    def _shutdown(signum, frame):
        log.info(f"Signal {signum} received — stopping all drivers...")
        for d in drivers:
            d.running = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT,  _shutdown)

    # --- Launch all driver threads ---
    log.info("Starting all gripper threads...")
    for d in drivers:
        d.start()
    log.info("All drivers running. Press Ctrl+C to stop.")

    # --- Wait until all drivers stop ---
    try:
        while any(d.running for d in drivers):
            time.sleep(0.1)
    except (KeyboardInterrupt, SystemExit):
        log.info("Interrupt received — stopping...")
        for d in drivers:
            d.running = False
        # Give threads a moment to notice
        time.sleep(0.5)

    # --- Join threads (don't let each driver close the shared port) ---
    log.info("Joining driver threads...")
    for d in drivers:
        for t, timeout in [
            (d.command_thread, 1.5),
            (d.control_thread, 1.5),
            (d.state_thread,   1.0),
            (d.admin_thread,   1.0),
        ]:
            if t and t.is_alive():
                t.join(timeout=timeout)
        # Null out connection so shutdown() won't try to close the shared port
        d.connection = None
        d.shutdown()

    # --- Close the port once, from here ---
    log.info("Closing serial port...")
    try:
        connection.portHandler.closePort()
    except Exception as e:
        log.debug(f"Port close: {e}")

    log.info("Multi-gripper driver stopped cleanly.")


if __name__ == "__main__":
    main()
