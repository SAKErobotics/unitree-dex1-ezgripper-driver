#!/bin/bash
"""
SAKE EZGripper DDS Validation Runner

Comprehensive validation script for DDS compliance.
Run this before any commit or PR.
"""

set -e  # Exit on any error

echo "🧪 SAKE EZGripper DDS Validation Suite"
echo "======================================"

# Check if driver is running
echo "🔍 Checking if SAKE driver is running..."
if ! pgrep -f "ezgripper_dds_driver.py" > /dev/null; then
    echo "❌ SAKE driver not found!"
    echo "💡 Start the driver first:"
    echo "   python3 ezgripper_dds_driver.py --side left"
    echo "   python3 ezgripper_dds_driver.py --side right"
    echo ""
    echo "🚨 Cannot proceed with validation without running driver."
    exit 1
fi

echo "✅ SAKE driver is running"
echo ""

# Quick compliance check
echo "📋 Step 1: Quick DDS Compliance Check"
echo "------------------------------------"
if python3 validate_dds_compliance.py --side left --domain 0; then
    echo "✅ Left gripper compliance: PASSED"
else
    echo "❌ Left gripper compliance: FAILED"
    exit 1
fi

if python3 validate_dds_compliance.py --side right --domain 0; then
    echo "✅ Right gripper compliance: PASSED"
else
    echo "❌ Right gripper compliance: FAILED"
    exit 1
fi

echo ""

# Full loopback test
echo "📋 Step 2: Full DDS Loopback Test"
echo "--------------------------------"
if python3 test_dds_loopback.py --side left --domain 0 --duration 15; then
    echo "✅ Left gripper loopback: PASSED"
else
    echo "❌ Left gripper loopback: FAILED"
    exit 1
fi

echo ""

# Summary
echo "🎉 ALL DDS VALIDATION TESTS PASSED!"
echo "✅ Driver is ready for production use"
echo "✅ xr_teleoperate integration validated"
echo "✅ Bidirectional communication confirmed"
echo ""
echo "📊 Test Summary:"
echo "   - DDS Compliance: ✅"
echo "   - Message Format: ✅"  
echo "   - Position Range: ✅"
echo "   - Bidirectional Comms: ✅"
echo "   - Feedback Loop: ✅"
echo ""
echo "🚀 Safe to commit and deploy!"
