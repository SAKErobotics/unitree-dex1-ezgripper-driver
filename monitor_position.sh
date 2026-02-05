#!/bin/bash
# Monitor gripper position at all points in the flow

echo "=========================================="
echo "GRIPPER POSITION MONITORING"
echo "=========================================="
echo ""
echo "Monitoring points:"
echo "1. Driver sensor readings (📊 SENSOR)"
echo "2. Driver actual position (🔄 READ)"
echo "3. DDS state publishing (📤 PUBLISH)"
echo ""
echo "Manually move the gripper now..."
echo "Press Ctrl+C to stop"
echo ""
echo "=========================================="
echo ""

tail -f /tmp/driver_output.log | grep --line-buffered -E "(📊 SENSOR|🔄 READ|📤 PUBLISH)" | while read line; do
    timestamp=$(echo "$line" | cut -d' ' -f1-2)
    content=$(echo "$line" | grep -oP "(📊 SENSOR|🔄 READ|📤 PUBLISH).*")
    
    if [[ $content == *"📊 SENSOR"* ]]; then
        echo "[SENSOR] $content"
    elif [[ $content == *"🔄 READ"* ]]; then
        echo "[DRIVER] $content"
    elif [[ $content == *"📤 PUBLISH"* ]]; then
        echo "[DDS   ] $content"
    fi
done
