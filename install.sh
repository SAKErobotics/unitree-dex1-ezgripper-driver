#!/bin/bash
# EZGripper Driver Installation Script
# Installs dependencies and sets up real-time capabilities

set -e  # Exit on error

echo "======================================"
echo "EZGripper Driver Installation"
echo "======================================"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo "Please do not run as root. Run as normal user with sudo access."
    exit 1
fi

# Detect Python version
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python 3 not found. Please install Python 3.8 or later."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Found Python: $PYTHON_CMD (version $PYTHON_VERSION)"
echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
$PYTHON_CMD -m pip install --user -r requirements.txt
echo "✓ Python dependencies installed"
echo ""

# Install Dynamixel SDK
echo "Installing Dynamixel SDK..."
if ! $PYTHON_CMD -c "import dynamixel_sdk" 2>/dev/null; then
    $PYTHON_CMD -m pip install --user dynamixel-sdk
    echo "✓ Dynamixel SDK installed"
else
    echo "✓ Dynamixel SDK already installed"
fi
echo ""

# Install CycloneDDS Python bindings
echo "Installing CycloneDDS..."
if ! $PYTHON_CMD -c "import cyclonedds" 2>/dev/null; then
    $PYTHON_CMD -m pip install --user cyclonedds
    echo "✓ CycloneDDS installed"
else
    echo "✓ CycloneDDS already installed"
fi
echo ""

# Set up real-time capabilities
echo "======================================"
echo "Setting up real-time capabilities"
echo "======================================"
echo ""
echo "This allows the driver to run with real-time priority for"
echo "deterministic control loop timing (30 Hz with low jitter)."
echo ""
echo "This requires sudo access to:"
echo "  1. Add CAP_SYS_NICE capability to Python interpreter"
echo "  2. Configure system limits for real-time scheduling"
echo ""
read -p "Set up real-time capabilities? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Get Python executable path
    PYTHON_PATH=$(which $PYTHON_CMD)
    echo "Python path: $PYTHON_PATH"
    echo ""
    
    # Add CAP_SYS_NICE capability
    echo "Adding CAP_SYS_NICE capability to Python..."
    sudo setcap cap_sys_nice+ep "$PYTHON_PATH" || {
        echo "Warning: Could not set capability. You may need to run driver with sudo."
    }
    
    # Verify capability was set
    if getcap "$PYTHON_PATH" | grep -q "cap_sys_nice"; then
        echo "✓ Real-time capability added to Python"
    else
        echo "⚠ Warning: Capability not set. Driver will run without real-time priority."
    fi
    echo ""
    
    # Configure system limits for real-time scheduling
    echo "Configuring system limits for real-time scheduling..."
    
    # Check if realtime group exists
    if ! getent group realtime > /dev/null 2>&1; then
        echo "Creating 'realtime' group..."
        sudo groupadd realtime
    fi
    
    # Add current user to realtime group
    echo "Adding $USER to 'realtime' group..."
    sudo usermod -a -G realtime $USER
    
    # Configure limits
    LIMITS_FILE="/etc/security/limits.d/99-realtime.conf"
    echo "Creating $LIMITS_FILE..."
    sudo tee "$LIMITS_FILE" > /dev/null << EOF
# Real-time scheduling limits for EZGripper driver
@realtime soft rtprio 99
@realtime hard rtprio 99
@realtime soft memlock unlimited
@realtime hard memlock unlimited
EOF
    
    echo "✓ System limits configured"
    echo ""
    echo "⚠ IMPORTANT: You need to log out and log back in for group changes to take effect."
    echo ""
else
    echo "Skipping real-time setup. Driver will run with normal priority."
    echo "You can run this script again later to enable real-time capabilities."
    echo ""
fi

# Set up udev rules for USB serial devices
echo "======================================"
echo "Setting up USB serial device access"
echo "======================================"
echo ""
read -p "Set up udev rules for USB serial devices? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    UDEV_RULE="/etc/udev/rules.d/99-ezgripper.rules"
    echo "Creating $UDEV_RULE..."
    sudo tee "$UDEV_RULE" > /dev/null << 'EOF'
# EZGripper USB serial device rules
# FTDI USB-to-Serial adapter
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", MODE="0666", GROUP="dialout"
# Generic USB-to-Serial adapters
SUBSYSTEM=="tty", ATTRS{idVendor}=="067b", MODE="0666", GROUP="dialout"
EOF
    
    # Add user to dialout group
    echo "Adding $USER to 'dialout' group..."
    sudo usermod -a -G dialout $USER
    
    # Reload udev rules
    echo "Reloading udev rules..."
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    
    echo "✓ USB serial device access configured"
    echo ""
    echo "⚠ IMPORTANT: You need to log out and log back in for group changes to take effect."
    echo ""
else
    echo "Skipping udev setup."
    echo ""
fi

# Create systemd service file (optional)
echo "======================================"
echo "Systemd Service Setup (Optional)"
echo "======================================"
echo ""
echo "Would you like to create a systemd service to run the driver at boot?"
read -p "Create systemd service? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    SERVICE_FILE="/etc/systemd/system/ezgripper-dds.service"
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    echo "Creating $SERVICE_FILE..."
    sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=EZGripper DDS Driver
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$PYTHON_PATH $SCRIPT_DIR/ezgripper_dds_driver.py --side left --domain 1
Restart=on-failure
RestartSec=5

# Real-time capabilities
AmbientCapabilities=CAP_SYS_NICE
LimitMEMLOCK=infinity

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    echo "✓ Systemd service created"
    echo ""
    echo "To enable the service:"
    echo "  sudo systemctl enable ezgripper-dds.service"
    echo ""
    echo "To start the service:"
    echo "  sudo systemctl start ezgripper-dds.service"
    echo ""
    echo "To view logs:"
    echo "  sudo journalctl -u ezgripper-dds.service -f"
    echo ""
else
    echo "Skipping systemd service creation."
    echo ""
fi

# Install EZGripper GUI (optional)
echo "======================================"
echo "EZGripper Web GUI Setup (Optional)"
echo "======================================"
echo ""
echo "Would you like to install the web-based GUI for manual control?"
read -p "Install EZGripper GUI? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing EZGripper GUI..."
    
    # Check for git
    if ! command -v git &> /dev/null; then
        echo "Error: git is not installed. Please install git to continue."
    else
        # Clone the GUI repository
        if [ -d "ezgripper-gui" ]; then
            echo "✓ EZGripper GUI repository already exists."
        else
            echo "Cloning GUI repository..."
            git clone https://github.com/SAKErobotics/EZGripper-gui.git ezgripper-gui
        fi
        
        # Create virtual environment
        echo "Creating Python virtual environment for GUI..."
        $PYTHON_CMD -m venv ezgripper-gui/venv
        
        # Install GUI dependencies
        echo "Installing GUI dependencies..."
        # Attempt to find the CycloneDDS installation directory
        CYCLONE_INSTALL_PATH=""
        if [ -d "/home/sokul/CascadeProjects/cyclonedds/install" ]; then
            CYCLONE_INSTALL_PATH="/home/sokul/CascadeProjects/cyclonedds/install"
        fi

        if [ -n "$CYCLONE_INSTALL_PATH" ]; then
            echo "Found CycloneDDS at: $CYCLONE_INSTALL_PATH"
            CYCLONEDDS_HOME=$CYCLONE_INSTALL_PATH ./ezgripper-gui/venv/bin/pip install -r ezgripper-gui/backend/requirements.txt
        else
            echo "Warning: Could not automatically find a local CycloneDDS build."
            echo "The GUI might fail to install if the system-wide library is not found."
            ./ezgripper-gui/venv/bin/pip install -r ezgripper-gui/backend/requirements.txt
        fi

        echo "✓ EZGripper GUI installed."
        echo ""
    fi
else
    echo "Skipping GUI installation."
fi
echo ""

# Installation complete
echo "======================================"
echo "Installation Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Log out and log back in (for group changes to take effect)"
echo ""
echo "2. Test the driver:"
echo "   $PYTHON_CMD ezgripper_dds_driver.py --side left --domain 1"
echo ""
echo "3. Run the 3-phase test:"
echo "   $PYTHON_CMD test_3phase_pattern.py --side left --domain 1"
echo ""
echo "For more information, see README.md"
echo ""
