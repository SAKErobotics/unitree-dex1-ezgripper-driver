#!/bin/bash

# Simple GUI Launcher for EZGripper
# Independent overlay that connects to existing DDS interfaces

echo "Starting EZGripper GUI Server..."

# Set up environment
export CYCLONEDDS_HOME="${CYCLONEDDS_HOME:-/usr/lib/x86_64-linux-gnu}"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if frontend directory exists
if [ ! -d "gui_frontend" ]; then
    echo "Error: gui_frontend directory not found"
    exit 1
fi

# Start the GUI server
python3 gui_server.py --side left --domain 0 --port 8000

echo "GUI server stopped"
