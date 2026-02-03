# Testing Guide - EZGripper DDS Integration

## Quick Start

### Automated Test (Recommended)
```bash
# Test left gripper on /dev/ttyUSB0
./test_dds_integration.sh left /dev/ttyUSB0

# Test right gripper on /dev/ttyUSB1
./test_dds_integration.sh right /dev/ttyUSB1
```

This will:
1. Start the DDS driver
2. Launch the GUI controller
3. Clean up on exit

### Manual Test

#### Terminal 1: Start the DDS Driver
```bash
python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0 --log-level INFO
```

#### Terminal 2: Start the GUI Controller
```bash
python3 grasp_control_gui.py left /dev/ttyUSB0
```

## GUI Features

### DDS Control (Main Testing Interface)
- **Slider:** Continuous position control (0-100%)
- **Quick Buttons:** 
  - Fully Open (100%)
  - Half Open (50%)
  - Closed (0%)
- **State Display:** Real-time feedback from DDS (position, force)

### Direct Hardware Calibration
- **Device Entry:** Specify serial device path
- **Calibrate Button:** Run calibration sequence
  - Bypasses DDS
  - Connects directly to hardware
  - Saves calibration to device config
  - Verifies calibration accuracy

## What to Test

### 1. Basic DDS Communication
- [ ] Move slider - gripper should respond
- [ ] State display updates in real-time
- [ ] Position feedback matches commanded position

### 2. GraspManager State Machine
- [ ] **IDLE → MOVING:** Move slider, watch logs for state transition
- [ ] **MOVING → CONTACT:** Close gripper on object, watch for contact detection
- [ ] **CONTACT → GRASPING:** Wait for settling (10 cycles), transitions to GRASPING
- [ ] **GRASPING → MOVING:** Open gripper, releases object

### 3. Force Management
Watch driver logs for force changes:
- **MOVING:** 80% force (fast movement)
- **CONTACT:** 30% force (settling period)
- **GRASPING:** 30% force (holding)

### 4. Error 128 Prevention
- [ ] Servo reboot on startup (check logs)
- [ ] Safe position range (5-95%) prevents stalls
- [ ] Proper shutdown (Ctrl+C should clean up gracefully)

### 5. Heartbeat Timeout
- [ ] Stop GUI (close window)
- [ ] Driver should detect heartbeat loss within 250ms
- [ ] Driver logs: "Teleop heartbeat lost. Standing by..."

### 6. Calibration
- [ ] Click "Calibrate Gripper" button
- [ ] Watch status messages
- [ ] Verify success dialog shows zero position
- [ ] Check that calibration persists (restart driver, position should be accurate)

## Expected Behavior

### Normal Operation
```
Driver logs (30Hz control loop):
📥 DDS CMD: q=2.700 rad → 50.0%
🎯 DDS INPUT: pos=50.0%, effort=100.0%
🎯 MANAGED GOAL: pos=50.0%, effort=80.0%
📊 SENSOR: raw=2048, pct=50.0%
📤 PUBLISH: actual_pos=50.0% → DDS_q=2.700rad
```

### State Transitions
```
→ MOVING to 20.0%
✋ Contact: current spike 65% (3 consecutive)
→ CONTACT at 22.3%
→ GRASPING (settled after 10 cycles)
→ MOVING (release from grasp)
```

### Calibration
```
🔧 Starting calibration on /dev/ttyUSB0...
📍 Running calibration...
✅ Calibration complete! Zero position: 1234
✅ Calibration successful! (at 50.2%)
```

## Monitoring Points

### Driver Terminal
- DDS command reception (📥)
- GraspManager state transitions (→)
- Contact detection (✋)
- Sensor readings (📊)
- State publishing (📤)
- Health monitoring (📊 Monitor)

### GUI
- Position slider movement
- State display updates
- Calibration status messages

## Troubleshooting

### No DDS Communication
```bash
# Check if driver is running
ps aux | grep ezgripper_dds_driver

# Check DDS topics
ros2 topic list  # or equivalent for CycloneDDS
```

### Device Not Found
```bash
# List available devices
ls -l /dev/ttyUSB*

# Check permissions
sudo chmod 666 /dev/ttyUSB0

# Add user to dialout group (permanent fix)
sudo usermod -a -G dialout $USER
# Then logout and login
```

### Error 128 on Startup
- Check logs for servo reboot sequence
- Verify 1-second delay after connection
- Ensure proper shutdown of previous session

### Calibration Fails
- Check device path is correct
- Ensure driver is NOT running (calibration needs exclusive access)
- Verify gripper can physically close
- Check for mechanical obstructions

### State Not Updating
- Verify driver is publishing at 200Hz (check logs)
- Check GUI is subscribed to correct topic
- Verify DDS domain matches (default: 0)

## Performance Metrics

### Expected Rates
- **Control Loop:** 30Hz (33.3ms period)
- **State Publishing:** 200Hz (5ms period)
- **GUI Updates:** 20Hz (50ms period)

### Monitor Output (Every 5 seconds)
```
📊 Monitor: State=200.0Hz | Cmd=50.0% | Actual=50.2% | Err=0.2%
```

## Test Scenarios

### Scenario 1: Open/Close Cycle
1. Start at 50%
2. Move to 100% (fully open)
3. Move to 0% (fully closed)
4. Return to 50%

**Expected:** Smooth movement, no errors, accurate position feedback

### Scenario 2: Contact Detection
1. Place object in gripper path
2. Command close (0%)
3. Watch for contact detection
4. Verify force reduces to 30%
5. Verify gripper holds position

**Expected:** Contact detected, state transitions to GRASPING, object held securely

### Scenario 3: Release Object
1. While grasping object
2. Command open (100%)
3. Watch for state transition to MOVING

**Expected:** Gripper releases, opens fully, returns to IDLE

### Scenario 4: Heartbeat Loss
1. Close GUI window
2. Watch driver logs

**Expected:** "Teleop heartbeat lost" within 250ms, driver stands by

### Scenario 5: Shutdown/Restart
1. Stop driver (Ctrl+C)
2. Restart driver
3. Verify no Error 128
4. Verify calibration persists

**Expected:** Clean startup, servo reboot clears errors, position accurate

## Success Criteria

- ✅ DDS communication works bidirectionally
- ✅ GraspManager state machine transitions correctly
- ✅ Contact detection works reliably
- ✅ Force management adapts based on state
- ✅ Heartbeat timeout prevents phantom movements
- ✅ Error 128 prevention works (no locked servos)
- ✅ Calibration saves and persists
- ✅ Shutdown is clean (no locked serial port)
- ✅ Performance meets targets (30Hz control, 200Hz state)

## Next Steps

After successful testing:
1. Test with G1 teleoperation stack
2. Test dual-gripper coordination (left + right)
3. Long-duration testing (24+ hours)
4. Object manipulation scenarios
5. Error recovery testing (disconnect/reconnect)
