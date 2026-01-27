# Vision-Guided Gripper Control Board
## Integrated Black Pill + Pi Zero 2W System Design

**Document Version:** 1.0  
**Date:** January 2026  
**Status:** Preliminary Design

---

## 1. SYSTEM OVERVIEW

### 1.1 Architecture
Dual-processor system combining real-time servo control with vision processing for intelligent robotic gripping applications.

```
┌─────────────────────────────────────────────────────────────┐
│                    MAIN CONTROL BOARD                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐         ┌──────────────────┐        │
│  │  Pi Zero 2W      │  UART   │  Black Pill      │        │
│  │  Vision Layer    │◄───────►│  Control Layer   │        │
│  │  (BCM2710A1)     │         │  (STM32F411CEU6) │        │
│  └────────┬─────────┘         └────────┬─────────┘        │
│           │                            │                   │
│      CSI Camera                   Dynamixel Bus            │
│           │                            │                   │
└───────────┼────────────────────────────┼───────────────────┘
            │                            │
      ┌─────▼─────┐              ┌───────▼────────┐
      │  OV9281   │              │  EZGripper     │
      │  1MP GS   │              │  Servo Motor   │
      │  Camera   │              │  (MX-64/106)   │
      └───────────┘              └────────────────┘
```

### 1.2 Key Features
- **Vision Processing:** 1MP global shutter, 30-60 FPS object detection
- **Real-time Control:** 1kHz servo control loop, <500μs latency
- **Hybrid Control:** Position + torque modes with force feedback
- **Communication:** DDS/ROS2 interface to host system
- **Power:** Single 12V input, onboard regulation
- **Form Factor:** Compact design for robotic arm mounting

---

## 2. FUNCTIONAL BLOCKS

### 2.1 Vision Processing Module (Pi Zero 2W)
**Processor:** Broadcom BCM2710A1 (Quad-core ARM Cortex-A53 @ 1GHz)

**Functions:**
- Image acquisition via CSI-2 interface
- Object detection and pose estimation (OpenCV/TensorFlow Lite)
- Grasp point calculation
- High-level command generation
- DDS/ROS2 communication to host

**Interfaces:**
- CSI-2 camera input (15-pin FFC)
- UART to Black Pill (115200 baud)
- USB OTG for host communication
- GPIO for status LEDs

### 2.2 Real-Time Control Module (Black Pill)
**Processor:** STM32F411CEU6 (ARM Cortex-M4F @ 100MHz)

**Functions:**
- 1kHz servo control loop
- Hybrid position/torque control
- Current sensing and force estimation
- Safety limit enforcement
- Dynamixel protocol implementation

**Interfaces:**
- UART2 to Dynamixel (half-duplex, 1Mbps)
- UART1 to Pi Zero (115200 baud)
- ADC for current sensing
- GPIO for direction control

---

## 3. HARDWARE SPECIFICATIONS

### 3.1 Power System
| Rail | Voltage | Current | Regulator | Purpose |
|------|---------|---------|-----------|---------|
| VIN  | 12V     | 2A max  | Input     | Main power |
| 5V   | 5.0V    | 2.5A    | Buck (MP2315) | Pi Zero, Camera |
| 3.3V | 3.3V    | 500mA   | LDO (AMS1117) | Black Pill, Logic |
| 12V  | 12V     | 2A      | Pass-through | Dynamixel servo |

**Protection:** Reverse polarity, overcurrent (PTC fuse), ESD (TVS diodes)

### 3.2 Camera Interface
- **Connector:** 15-pin 1.0mm FFC (Pi Zero CSI)
- **Camera:** OV9281 1MP global shutter module
- **Resolution:** 1280x800 @ 60 FPS
- **Interface:** MIPI CSI-2, 2-lane
- **Power:** 3.3V from Pi Zero header

### 3.3 Dynamixel Interface
- **Connector:** 3-pin Molex (or JST-XH)
- **Protocol:** TTL half-duplex UART
- **Baud Rate:** 1 Mbps (configurable)
- **Direction Control:** GPIO-controlled tri-state buffer (74LVC1G125)
- **Current Sensing:** INA219 on power rail (optional)

### 3.4 Inter-Processor Communication
- **Physical:** UART (3.3V logic)
- **Baud Rate:** 115200 baud
- **Protocol:** Simple ASCII command/response
- **Latency:** <1ms typical

### 3.5 Host Communication
- **Primary:** USB OTG (Pi Zero)
- **Protocol:** DDS/ROS2 over USB Ethernet (CDC-ECM)
- **Backup:** WiFi (via USB WiFi dongle)

---

## 4. BOARD LAYOUT

### 4.1 Option A: Single Board (Recommended)
**Dimensions:** 80mm x 60mm x 20mm (with modules)

**Layout:**
```
┌────────────────────────────────────────┐
│  [Camera FFC]                          │
│                                        │
│  ┌──────────────┐    ┌──────────┐    │
│  │  Pi Zero 2W  │    │ Black    │    │
│  │  (Socket)    │    │ Pill     │    │
│  │              │    │ (Socket) │    │
│  └──────────────┘    └──────────┘    │
│                                        │
│  [Buck 5V] [LDO 3.3V]  [Level Shift] │
│                                        │
│  [USB]  [12V In]  [Dynamixel Out]    │
└────────────────────────────────────────┘
```

### 4.2 Option B: Two-Board Stack
**Main Board:** 60mm x 40mm (control electronics)  
**Carrier Board:** 60mm x 40mm (Pi Zero + camera)

**Advantages:** Easier assembly, modular upgrades  
**Connection:** 2x20 pin header (Pi GPIO) + 6-pin control header

---

## 5. SUPPORT CIRCUITRY

### 5.1 Required Components
- **Power:** MP2315 buck converter, AMS1117 LDO, protection diodes
- **Level Shifting:** 74LVC1G125 (Dynamixel direction), 74LVC2G34 (UART)
- **Current Sensing:** INA219 I2C current/voltage monitor (optional)
- **Status:** 3x LEDs (power, vision active, control active)
- **Connectors:** USB Micro (Pi), 12V barrel jack, 3-pin Dynamixel, 15-pin FFC

### 5.2 Optional Features
- **IMU:** MPU6050 on I2C (object motion detection)
- **Force Sensors:** 2x FSR on ADC inputs (fingertip force)
- **EEPROM:** 24LC256 for calibration storage
- **Debug:** SWD header (Black Pill), UART header (Pi)

---

## 6. COMMUNICATION PROTOCOL

### 6.1 Pi Zero → Black Pill (Command)
```
GRIP <position> <force> <mode>\n
  position: 0-100 (%)
  force: 0-100 (% of max)
  mode: 0=position, 1=torque, 2=hybrid
  
Example: GRIP 45 60 2\n
```

### 6.2 Black Pill → Pi Zero (Status)
```
STAT <position> <force> <current> <state>\n
  position: 0-100 (actual %)
  force: 0-100 (estimated %)
  current: 0-1023 (raw ADC)
  state: 0=idle, 1=moving, 2=gripping, 3=error
  
Example: STAT 45.2 58 412 2\n
```

**Update Rate:** 100 Hz (10ms period)

### 6.3 Host ↔ Pi Zero (DDS/ROS2)
Standard ROS2 messages:
- `sensor_msgs/JointState` (gripper state)
- `control_msgs/GripperCommand` (gripper commands)
- `sensor_msgs/Image` (camera feed)

---

## 7. PERFORMANCE SPECIFICATIONS

| Parameter | Specification | Notes |
|-----------|---------------|-------|
| Vision Frame Rate | 30-60 FPS | Depends on processing load |
| Control Loop Rate | 1000 Hz | Deterministic, <10μs jitter |
| Command Latency | <5ms | Vision → Servo response |
| Position Accuracy | ±1% | With calibration |
| Force Resolution | ~1% | Via current sensing |
| Power Consumption | <10W typical | 15W max with servo active |
| Operating Temp | 0-50°C | With heatsinks |

---

## 8. DEVELOPMENT & PRODUCTION

### 8.1 Bill of Materials (Estimated)
- Pi Zero 2W: $15
- Black Pill (STM32F411): $5
- OV9281 Camera: $25
- PCB (4-layer): $15 (qty 5)
- Components: $20
- **Total per unit:** ~$80 (low volume)

### 8.2 Software Stack
- **Pi Zero:** Linux (Raspberry Pi OS Lite), Python 3.9+, OpenCV, ROS2
- **Black Pill:** FreeRTOS or bare-metal, C/C++, STM32 HAL
- **Development:** STM32CubeIDE, VS Code, PlatformIO

### 8.3 Next Steps
1. Detailed schematic design
2. PCB layout (KiCad)
3. Prototype firmware (Black Pill)
4. Vision processing pipeline (Pi Zero)
5. Integration testing
6. Production design review

---

**Document End**
