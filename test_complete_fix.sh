#!/bin/bash
# Comprehensive test script to verify the get_error_details fix

echo "🧪 Testing get_error_details() Fix"
echo "===================================="
echo ""

# Kill any running driver
echo "1. Stopping any running driver..."
pkill -9 -f ezgripper_dds_driver
sleep 2

# Start driver with logging
echo "2. Starting driver with fix applied..."
cd /home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver
python3 ezgripper_dds_driver.py --side left --log-level INFO 2>&1 | tee /tmp/test_complete_fix.log &
DRIVER_PID=$!
echo "   Driver PID: $DRIVER_PID"

echo "3. Waiting 5 seconds for calibration..."
sleep 5

# Run the movement test
echo ""
echo "4. Running movement test..."
echo "===================================="
python3 test_gripper_movement.py left

echo ""
echo "===================================="
echo "5. Analyzing Results"
echo "===================================="
echo ""

# Check for the critical error
if grep -q "Communication error.*has_error" /tmp/test_complete_fix.log; then
    echo "❌ FAILED: Still getting 'has_error' exceptions"
    echo ""
    echo "Error samples:"
    grep "Communication error.*has_error" /tmp/test_complete_fix.log | head -3
    RESULT="FAILED"
else
    echo "✅ PASS: No 'has_error' exceptions found!"
    RESULT="PASS"
fi

echo ""

# Check if position updates are happening
if grep -q "🔄 READ: actual_position_pct" /tmp/test_complete_fix.log; then
    echo "✅ PASS: Position updates are happening!"
    echo ""
    echo "Sample position updates:"
    grep "🔄 READ: actual_position_pct" /tmp/test_complete_fix.log | head -5
else
    echo "❌ FAILED: Position updates NOT happening"
    RESULT="FAILED"
fi

echo ""

# Check sensor reads
echo "Sensor read samples:"
grep "📊 SENSOR:" /tmp/test_complete_fix.log | tail -5

echo ""
echo "===================================="
echo "6. Final Result: $RESULT"
echo "===================================="

if [ "$RESULT" = "PASS" ]; then
    echo ""
    echo "✅ Fix is working correctly!"
    echo ""
    echo "Next steps:"
    echo "  1. Commit the fix:"
    echo "     git add ezgripper_dds_driver.py apply_fix.py"
    echo "     git commit -m 'Fix get_error_details KeyError blocking position updates'"
    echo ""
    echo "  2. Test bidirectional movement:"
    echo "     python3 test_3phase_gripper.py left"
else
    echo ""
    echo "❌ Fix did not resolve the issue"
    echo "   Check /tmp/test_complete_fix.log for details"
fi

echo ""
echo "Stopping driver..."
kill -9 $DRIVER_PID 2>/dev/null

echo ""
echo "Full log: /tmp/test_complete_fix.log"
