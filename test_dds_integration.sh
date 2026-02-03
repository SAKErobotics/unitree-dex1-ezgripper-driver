#!/bin/bash
# Test script for EZGripper DDS integration
# Tests the complete stack: GUI -> DDS -> Driver -> Hardware

set -e

SIDE=${1:-left}
DEVICE=${2:-/dev/ttyUSB0}

echo "=========================================="
echo "EZGripper DDS Integration Test"
echo "=========================================="
echo "Side: $SIDE"
echo "Device: $DEVICE"
echo ""

# Check if device exists
if [ ! -e "$DEVICE" ]; then
    echo "❌ Error: Device $DEVICE not found"
    echo "Available devices:"
    ls -l /dev/ttyUSB* 2>/dev/null || echo "  No /dev/ttyUSB* devices found"
    exit 1
fi

echo "✅ Device found: $DEVICE"
echo ""

# Check permissions
if [ ! -r "$DEVICE" ] || [ ! -w "$DEVICE" ]; then
    echo "⚠️  Warning: No read/write permissions on $DEVICE"
    echo "You may need to run: sudo chmod 666 $DEVICE"
    echo "Or add user to dialout group: sudo usermod -a -G dialout $USER"
    echo ""
fi

echo "=========================================="
echo "Test Setup"
echo "=========================================="
echo ""
echo "This test will:"
echo "  1. Start the DDS driver (ezgripper_dds_driver.py)"
echo "  2. Start the GUI controller (grasp_control_gui.py)"
echo ""
echo "The GUI will:"
echo "  • Send position commands via DDS"
echo "  • Display gripper state from DDS feedback"
echo "  • Allow direct hardware calibration (bypasses DDS)"
echo ""
echo "The driver will:"
echo "  • Receive commands via DDS (30Hz)"
echo "  • Process through GraspManager state machine"
echo "  • Publish state via DDS (200Hz)"
echo "  • Monitor hardware health"
echo ""
echo "=========================================="
echo "Starting Test..."
echo "=========================================="
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "=========================================="
    echo "Cleaning up..."
    echo "=========================================="
    pkill -f "ezgripper_dds_driver.py --side $SIDE" || true
    pkill -f "grasp_control_gui.py $SIDE" || true
    sleep 1
    echo "✅ Cleanup complete"
}

trap cleanup EXIT INT TERM

# Start the DDS driver in background
echo "📡 Starting DDS driver..."
python3 ezgripper_dds_driver.py --side $SIDE --dev $DEVICE --log-level INFO &
DRIVER_PID=$!
echo "   Driver PID: $DRIVER_PID"
sleep 3  # Give driver time to initialize

# Check if driver is still running
if ! ps -p $DRIVER_PID > /dev/null; then
    echo "❌ Driver failed to start. Check logs above."
    exit 1
fi

echo "✅ Driver started successfully"
echo ""

# Start the GUI
echo "🖥️  Starting GUI controller..."
echo ""
python3 grasp_control_gui.py $SIDE $DEVICE

# GUI will block until closed
echo ""
echo "=========================================="
echo "Test Complete"
echo "=========================================="
