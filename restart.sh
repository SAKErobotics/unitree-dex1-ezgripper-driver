#!/bin/bash
# Fast restart script - kills all processes and restarts driver

pkill -9 -f ezgripper
pkill -9 -f test_3phase
pkill -9 python3
sleep 1
cd /home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver
python3 ezgripper_dds_driver.py --side left --log-level INFO &
echo "Driver restarted. PID: $!"
