# EZGripper GUI

A modern, web-based interface for controlling the SAKE Robotics EZGripper.

This application provides a platform-independent GUI that communicates with the `ezgripper_dds_driver` via a Python backend.

## Architecture

- **Frontend**: A simple HTML, CSS, and JavaScript single-page application that runs in any modern web browser.
- **Backend**: A Python server using FastAPI and WebSockets to bridge the web interface with the CycloneDDS network.

## Prerequisites

- The `unitree-dex1-ezgripper-driver` must be installed and the `ezgripper_dds_driver.py` script must be running.
- Python 3.6+

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/SAKErobotics/EZGripper-gui.git
   cd EZGripper-gui
   ```

2. Install Python dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

## Usage

1. Start the backend server:
   ```bash
   python backend/main.py
   ```

2. Open a web browser and navigate to `http://127.0.0.1:8000`.
