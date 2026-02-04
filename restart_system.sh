#!/bin/bash
# Restart gripper driver and GUI with new telemetry code

echo "Killing all Python processes..."
killall -9 python3 2>&1 | grep -v "Operation not permitted" || true

echo "Clearing Python cache..."
find /home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find /home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver -name "*.pyc" -delete 2>/dev/null || true

echo "Starting driver..."
cd /home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver
PYTHONDONTWRITEBYTECODE=1 python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0 --log-level INFO > /tmp/driver_output.log 2>&1 &

echo "Waiting for driver to initialize..."
sleep 8

echo "Checking for GraspManager V2..."
grep "GraspManager V2" /tmp/driver_output.log || echo "WARNING: GraspManager V2 not found"

echo "Checking for telemetry..."
grep "📡 TELEMETRY" /tmp/driver_output.log | tail -3 || echo "WARNING: No telemetry found yet"

echo ""
echo "Driver started. To start GUI, run:"
echo "  python3 grasp_control_gui.py left /dev/ttyUSB0"
echo ""
echo "To monitor telemetry:"
echo "  tail -f /tmp/driver_output.log | grep TELEMETRY"
