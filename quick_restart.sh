#!/bin/bash
killall -9 python3 2>&1 | grep -v "Operation not permitted" || true
cd /home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver
PYTHONDONTWRITEBYTECODE=1 python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0 --log-level INFO > /tmp/driver_output.log 2>&1 &
echo "Driver restarted. Wait 8 seconds then run GUI:"
echo "  python3 grasp_control_gui.py left /dev/ttyUSB0"
