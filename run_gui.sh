#!/bin/bash
# Launcher for the EZGripper Web GUI

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUI_DIR="$SCRIPT_DIR/ezgripper-gui"

# Check if GUI is installed
if [ ! -d "$GUI_DIR" ]; then
    echo "Error: EZGripper GUI is not installed. Please run install.sh and choose 'y' to install the GUI."
    exit 1
fi

# Find CycloneDDS installation
CYCLONE_INSTALL_PATH=""
if [ -d "/home/sokul/CascadeProjects/cyclonedds/install" ]; then
    CYCLONE_INSTALL_PATH="/home/sokul/CascadeProjects/cyclonedds/install"
elif [ -d "/usr/local" ]; then
    # Fallback to a common system-wide install location
    CYCLONE_INSTALL_PATH="/usr/local"
fi

if [ -z "$CYCLONE_INSTALL_PATH" ]; then
    echo "Error: Could not find CycloneDDS installation. Set CYCLONEDDS_HOME manually."
    exit 1
fi

echo "Using CycloneDDS from: $CYCLONE_INSTALL_PATH"

# Run the GUI backend server
export CYCLONEDDS_HOME=$CYCLONE_INSTALL_PATH
cd "$GUI_DIR"

echo "Starting EZGripper GUI server..."
echo "Access the interface at http://127.0.0.1:8000"

./venv/bin/python backend/main.py
