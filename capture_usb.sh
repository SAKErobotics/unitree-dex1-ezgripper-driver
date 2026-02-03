#!/bin/bash
# Capture USB traffic to analyze Dynamixel Wizard communication

echo "🔍 USB Traffic Capture for Dynamixel Protocol"
echo "=============================================="
echo ""

# Find USB device
USB_DEV=$(ls -la /dev/ttyUSB0 | grep -o "188, [0-9]*" | cut -d' ' -f2)
echo "USB device: /dev/ttyUSB0 (minor: $USB_DEV)"

# Method 1: strace on the process
echo ""
echo "Method 1: Using strace to capture read/write calls"
echo "---------------------------------------------------"
echo "1. Start Dynamixel Wizard"
echo "2. Press Enter when ready to capture"
read

echo "Finding Dynamixel Wizard process..."
PID=$(ps aux | grep -i dynamixel | grep -v grep | awk '{print $2}' | head -1)

if [ -z "$PID" ]; then
    echo "❌ Dynamixel Wizard not found"
    echo ""
    echo "Method 2: Capture our driver's traffic instead"
    echo "This will show what our code sends vs what works"
    echo ""
    echo "Run: sudo strace -e trace=read,write,ioctl -s 1000 -xx python3 ezgripper_dds_driver.py --side left 2>&1 | tee /tmp/usb_trace.log"
    exit 1
fi

echo "Found PID: $PID"
echo "Capturing for 10 seconds..."
echo ""

sudo timeout 10 strace -e trace=read,write,ioctl -s 1000 -xx -p $PID 2>&1 | tee /tmp/dynamixel_wizard_trace.log

echo ""
echo "✅ Capture complete: /tmp/dynamixel_wizard_trace.log"
echo ""
echo "To analyze:"
echo "  grep 'write.*ttyUSB' /tmp/dynamixel_wizard_trace.log"
echo "  grep 'read.*ttyUSB' /tmp/dynamixel_wizard_trace.log"
