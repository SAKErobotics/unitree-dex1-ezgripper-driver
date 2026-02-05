#!/bin/bash
# Run calibration with monitoring

echo "🔧 Running Calibration with Monitoring"
echo "======================================"
echo ""
echo "This will:"
echo "1. Kill any running driver"
echo "2. Start driver with calibration"
echo "3. Monitor collision detection"
echo ""

pkill -9 -f ezgripper
sleep 1

cd /home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver

# Start driver - it will auto-calibrate
python3 << 'EOF'
import sys
import time
sys.path.insert(0, 'libezgripper')
from lib_robotis import create_connection
from libezgripper import create_gripper
from libezgripper.config import load_config

print("Connecting...")
connection = create_connection(dev_name='/dev/ttyUSB0', baudrate=1000000)
time.sleep(1.0)

print("Creating gripper...")
config = load_config()
gripper = create_gripper(connection, 'test', [1], config)

print("\nStarting calibration - watch for collision detection...")
print("=" * 60)

start = time.time()
success = gripper.calibrate()
elapsed = time.time() - start

print("=" * 60)
print(f"Calibration {'SUCCESS' if success else 'FAILED'}")
print(f"Time: {elapsed:.2f} seconds")
print(f"Zero position: {gripper.zero_positions[0]}")
print("=" * 60)
EOF
