#!/usr/bin/env python3
"""
Thermal Grasp Test via DDS Interface

Measures power consumption during static grasp via temperature rise.
Communicates ONLY through DDS - requires ezgripper_dds_driver to be running.

Usage:
    # Terminal 1: Start DDS driver
    python3 ezgripper_dds_driver.py --side left
    
    # Terminal 2: Run test
    python3 thermal_grasp_dds.py --side left --base-force 15
"""

import argparse
import time
import csv
import json
import logging
import signal
import sys
import subprocess
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_, MotorStates_, MotorState_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_


@dataclass
class DetailedMeasurement:
    """Detailed measurement point during test"""
    timestamp: float
    elapsed_sec: float
    force_pct: float
    position_pct: float
    temperature_c: float
    grasp_state: str
    velocity: float
    torque: float
    lost: int
    reserve: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ThermalTestResult:
    """Result from one thermal test"""
    force_pct: float
    force_multiplier: float
    
    start_temp_c: float
    end_temp_c: float
    temp_rise_c: float
    
    wall_time_sec: float
    heating_rate_c_per_sec: float
    
    relative_power: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ThermalGraspDDS:
    """Thermal grasp test using DDS interface only"""
    
    def __init__(self, side: str):
        self.side = side
        self._shutdown_requested = False
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            force=True
        )
        self.logger = logging.getLogger(__name__)
        
        # Test state
        self.test_results: List[ThermalTestResult] = []
        self.detailed_measurements: List[DetailedMeasurement] = []
        self.test_start_time = time.time()
        
        # Driver process management
        self.driver_process = None
        self.config_file = '/home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver/config_default.json'
        
        # DDS topics
        self.cmd_topic = f"rt/dex1/{side}/cmd"
        self.state_topic = f"rt/dex1/{side}/state"
        
        # DDS publishers/subscribers (initialized later)
        self.cmd_publisher = None
        self.state_subscriber = None
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info(f"Initializing DDS thermal grasp test for {side} gripper...")
        
        # Initialize DDS
        ChannelFactoryInitialize(0)
        
        # Setup DDS connection
        self._setup_dds()
        
        self.logger.info("✅ DDS initialized")
        self.logger.info(f"   Publishing commands to: {self.cmd_topic}")
        self.logger.info(f"   Subscribing to states from: {self.state_topic}")
    
    def send_position_command(self, position_pct: float, effort_pct: float = 50.0):
        """Send position command via DDS"""
        # Convert position % to radians (0% = 0 rad, 100% = 5.4 rad)
        q_radians = (position_pct / 100.0) * 5.4
        
        # Create motor command
        motor_cmd = unitree_go_msg_dds__MotorCmd_()
        motor_cmd.q = q_radians
        motor_cmd.dq = 0.0
        motor_cmd.tau = 0.0  # Not used in position mode
        motor_cmd.kp = 0.0
        motor_cmd.kd = 0.0
        
        # Create motor commands message
        msg = MotorCmds_()
        msg.cmds = [motor_cmd]
        
        # Publish
        self.cmd_publisher.Write(msg)
    
    def read_state(self) -> Dict[str, Any]:
        """Read latest state from DDS"""
        state_msg = self.state_subscriber.Read()
        
        if state_msg and hasattr(state_msg, 'states') and state_msg.states and len(state_msg.states) > 0:
            motor_state = state_msg.states[0]
            
            # Convert radians to percentage (0 rad = 0%, 5.4 rad = 100%)
            position_pct = (motor_state.q / 5.4) * 100.0
            
            # Extract ALL data from DDS state
            state = {
                'position': position_pct,
                'temperature': int(motor_state.temperature),
                'velocity': motor_state.dq,
                'torque': motor_state.tau_est,
                'lost': motor_state.lost,
                'reserve': motor_state.reserve
            }
            
            self.latest_state = state
            return state
        
        # Return last known state if no new message
        if self.latest_state:
            return self.latest_state
        
        # Default state
        return {
            'position': 0.0,
            'temperature': 25,
            'velocity': 0.0,
            'torque': 0.0,
            'lost': 0,
            'reserve': 0
        }
    
    def _validate_connection(self):
        """Validate DDS connection to gripper"""
        self.logger.info("Validating DDS connection to gripper...")
        
        # Wait for driver to start publishing
        time.sleep(2.0)
        
        # Try to read state
        max_attempts = 5
        for attempt in range(max_attempts):
            state_msg = self.state_subscriber.Read()
            
            if state_msg and hasattr(state_msg, 'states') and state_msg.states and len(state_msg.states) > 0:
                motor_state = state_msg.states[0]
                position_pct = (motor_state.q / 5.4) * 100.0
                temp = motor_state.temperature
                
                self.logger.info(f"✅ Connected to gripper")
                self.logger.info(f"   Position: {position_pct:.1f}%")
                self.logger.info(f"   Temperature: {temp}°C")
                self.logger.info(f"   DDS driver is running and responding")
                return
            
            if attempt < max_attempts - 1:
                self.logger.warning(f"No data received (attempt {attempt+1}/{max_attempts}), retrying...")
                time.sleep(1.0)
        
        # Connection failed
        self.logger.error("❌ Failed to connect to gripper via DDS")
        self.logger.error("")
        self.logger.error("Possible issues:")
        self.logger.error("  1. DDS driver not running")
        self.logger.error("  2. Wrong USB device (gripper may have changed port after repower)")
        self.logger.error("  3. Gripper not powered")
        self.logger.error("  4. Calibration not complete")
        self.logger.error("")
        self.logger.error("To fix:")
        self.logger.error("  1. Check USB device: ls -la /dev/ttyUSB*")
        self.logger.error("  2. Restart DDS driver: python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0")
        self.logger.error("  3. Wait for calibration to complete")
        raise RuntimeError("DDS connection validation failed")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info("\n\n⚠️  Shutdown signal received")
        self._emergency_stop("User interrupt")
        self._stop_driver()
        sys.exit(0)
    
    def _emergency_stop(self, reason: str):
        """Emergency stop - open gripper immediately"""
        self.logger.error(f"\n🚨 EMERGENCY STOP: {reason}")
        self.logger.info("Opening gripper to 30%...")
        
        # Send open commands for 2 seconds
        for _ in range(60):
            self.send_position_command(30.0, 30.0)
            time.sleep(1.0 / 30.0)
        
        self.logger.info("Emergency stop complete")
    
    def _update_config_force(self, grasping_force_pct: float):
        """Update config file with new grasping_force_pct"""
        self.logger.info(f"Updating config: grasping_force_pct = {grasping_force_pct}%")
        
        with open(self.config_file, 'r') as f:
            config = json.load(f)
        
        config['servo']['force_management']['grasping_force_pct'] = grasping_force_pct
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        self.logger.info("Config updated")
    
    def _stop_driver(self):
        """Stop the DDS driver process"""
        if self.driver_process:
            self.logger.info("Stopping DDS driver...")
            self.driver_process.terminate()
            try:
                self.driver_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.driver_process.kill()
            self.driver_process = None
        else:
            # Kill any existing driver process
            subprocess.run(['pkill', '-f', 'ezgripper_dds_driver'], check=False)
        
        time.sleep(2.0)
        self.logger.info("Driver stopped")
    
    def _start_driver(self, device: str = '/dev/ttyUSB0'):
        """Start the DDS driver process"""
        self.logger.info("Starting DDS driver...")
        
        cmd = [
            '/usr/bin/python3',
            '/home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver/ezgripper_dds_driver.py',
            '--side', self.side,
            '--dev', device
        ]
        
        # Start driver without capturing output so we can see errors
        self.driver_process = subprocess.Popen(cmd)
        
        # Wait longer for driver to initialize (calibration takes time)
        self.logger.info("Waiting for driver to initialize (calibration may take 10-15s)...")
        time.sleep(15.0)
        
        # Check if driver is still running
        if self.driver_process.poll() is not None:
            raise RuntimeError(f"Driver process exited with code {self.driver_process.returncode}")
        
        self.logger.info("Driver started")
    
    def _restart_driver_with_force(self, grasping_force_pct: float, device: str = '/dev/ttyUSB0'):
        """Restart driver with updated force configuration"""
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Restarting driver with grasping_force_pct = {grasping_force_pct}%")
        self.logger.info(f"{'='*70}")
        
        # Stop existing driver
        self._stop_driver()
        
        # Update config
        self._update_config_force(grasping_force_pct)
        
        # Start driver with new config
        self._start_driver(device)
        
        # Reinitialize DDS connection
        self._setup_dds()
        self._validate_connection()
        
        self.logger.info("Driver restart complete\n")
    
    def _setup_dds(self):
        """Setup DDS connection"""
        self.cmd_publisher = ChannelPublisher(self.cmd_topic, MotorCmds_)
        self.cmd_publisher.Init()
        
        self.state_subscriber = ChannelSubscriber(self.state_topic, MotorStates_)
        self.state_subscriber.Init()
    
    def run_thermal_test(self, force_pct: float, force_multiplier: float,
                        temp_rise_target: float = 5.0, closing_force_pct: float = 15.0) -> ThermalTestResult:
        """
        Run one thermal test via DDS
        
        1. Command open to 30%
        2. Command close to 0% with closing_force_pct (default 15%)
        3. Switch to holding force (force_pct)
        4. Monitor temperature rise
        5. Record wall time
        
        Safety aborts:
        - Temperature > 75°C (critical)
        - Communication errors (lost > 0)
        - Starting temperature > 50°C (requires cooldown)
        """
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Thermal Test: {force_pct}% force ({force_multiplier}x)")
        self.logger.info(f"Closing force: {closing_force_pct}%, Holding force: {force_pct}%")
        self.logger.info(f"Target temp rise: {temp_rise_target}°C")
        self.logger.info(f"{'='*70}")
        
        # Move to 30% starting position
        self.logger.info("Moving to start position (30%)...")
        for i in range(90):  # 3 seconds at 30Hz
            self.send_position_command(30.0, 30.0)
            time.sleep(1.0 / 30.0)
        
        time.sleep(1.0)
        
        # Record starting temperature
        start_state = self.read_state()
        start_temp = start_state['temperature']
        target_temp = start_temp + temp_rise_target
        
        # SAFETY: Pre-test temperature validation
        if start_temp > 50:
            self.logger.error(f"⚠️  ABORT: Starting temperature {start_temp}°C exceeds 50°C safety limit")
            self.logger.error("Gripper requires additional cooldown before testing.")
            raise RuntimeError(f"Starting temperature too high: {start_temp}°C > 50°C")
        
        # SAFETY: Check for absolute maximum
        if start_temp > 70:
            self._emergency_stop(f"Starting temperature {start_temp}°C exceeds 70°C operating limit")
            raise RuntimeError(f"Temperature exceeds operating limit: {start_temp}°C")
        
        self.logger.info(f"\nStart temperature: {start_temp:.1f}°C ✅")
        self.logger.info(f"Target temperature: {target_temp:.1f}°C")
        
        # Close to 0% with closing force
        self.logger.info(f"\nClosing to 0% (contact) with {closing_force_pct}% force...")
        for i in range(90):  # 3 seconds
            self.send_position_command(0.0, closing_force_pct)
            state = self.read_state()
            
            # SAFETY: Communication error check
            if state['lost'] > 0:
                self._emergency_stop(f"Communication error detected (lost={state['lost']})")
                raise RuntimeError("DDS communication failure")
            
            if i % 15 == 0:  # Log every 0.5 seconds
                self.logger.info(f"  Position: {state['position']:.1f}%, Temp: {state['temperature']:.1f}°C")
            
            if state['position'] < 3.0:
                self.logger.info(f"  ✅ Contact at {state['position']:.1f}%, Temp: {state['temperature']:.1f}°C")
                break
            
            time.sleep(1.0 / 30.0)
        
        # Transition to holding force
        if closing_force_pct != force_pct:
            self.logger.info(f"\nTransitioning to holding force: {force_pct}%...")
            for i in range(30):  # 1 second transition
                self.send_position_command(0.0, force_pct)
                time.sleep(1.0 / 30.0)
            
            # Check position after transition
            state = self.read_state()
            self.logger.info(f"  Position after transition: {state['position']:.1f}%, Temp: {state['temperature']:.1f}°C")
        
        # Hold and wait for temperature rise
        self.logger.info(f"\nHolding at 0% with {force_pct}% force...")
        self.logger.info(f"Waiting for temperature to rise {temp_rise_target}°C...")
        self.logger.info(f"Start: {start_temp:.1f}°C → Target: {target_temp:.1f}°C")
        self.logger.info("")
        
        test_start = time.time()
        last_log_time = test_start
        # Initialize position tracking from first hold state (not start_state which was at 30%)
        last_position = None
        last_temp = start_temp
        
        # Equilibrium detection variables
        stable_temp_history = []  # List of stable temperature readings
        equilibrium_threshold = 0.5  # Temperature variation threshold (°C)
        equilibrium_duration = 300   # 5 minutes in seconds
        equilibrium_start_time = None
        
        while True:
            # Send hold command
            self.send_position_command(0.0, force_pct)
            
            # Read state
            state = self.read_state()
            
            current_temp = state['temperature']
            temp_rise = current_temp - start_temp
            elapsed = time.time() - test_start
            remaining = temp_rise_target - temp_rise
            
            # SAFETY: Critical temperature limit
            if current_temp >= 75:
                self._emergency_stop(f"Temperature {current_temp}°C exceeds 75°C critical limit")
                raise RuntimeError(f"Temperature safety limit exceeded: {current_temp}°C >= 75°C")
            
            # SAFETY: Absolute maximum temperature
            if current_temp >= 80:
                self._emergency_stop(f"Temperature {current_temp}°C exceeds 80°C absolute maximum")
                raise RuntimeError(f"Temperature absolute maximum exceeded: {current_temp}°C >= 80°C")
            
            # SAFETY: Communication error check
            if state['lost'] > 0:
                self._emergency_stop(f"Communication error detected (lost={state['lost']})")
                raise RuntimeError("DDS communication failure")
            
            # EQUILIBRIUM DETECTION: Maintain stable temperature history
            if not stable_temp_history:
                # First reading - start history
                stable_temp_history.append(current_temp)
                equilibrium_start_time = time.time()
                self.logger.info(f"🌡️  Starting equilibrium detection at {current_temp:.1f}°C")
            else:
                # Check if current temp is within threshold of history
                avg_stable_temp = sum(stable_temp_history) / len(stable_temp_history)
                temp_variation = abs(current_temp - avg_stable_temp)
                
                if temp_variation <= equilibrium_threshold:
                    # Temperature is stable - add to history
                    stable_temp_history.append(current_temp)
                    
                    # Check if we've been stable for 5 minutes
                    if time.time() - equilibrium_start_time >= equilibrium_duration:
                        equilibrium_time = time.time() - equilibrium_start_time
                        final_avg_temp = sum(stable_temp_history) / len(stable_temp_history)
                        self.logger.info(f"✅ THERMAL EQUILIBRIUM REACHED after {equilibrium_time/60:.1f} minutes")
                        self.logger.info(f"   Stable temperature: {final_avg_temp:.1f}°C (±{equilibrium_threshold}°C for {equilibrium_duration/60:.0f} min)")
                        self.logger.info(f"   History size: {len(stable_temp_history)} readings")
                        wall_time = elapsed
                        break
                else:
                    # Temperature fluctuated - reset history
                    if len(stable_temp_history) > 10:  # Only log if we had substantial history
                        self.logger.info(f"🌡️  Temperature fluctuated {temp_variation:.1f}°C, resetting equilibrium history")
                        self.logger.info(f"   Was stable for {(time.time() - equilibrium_start_time)/60:.1f} minutes")
                    stable_temp_history = [current_temp]  # Restart with current temp
                    equilibrium_start_time = time.time()
            
            # SAFETY: Position stability check (warn only, only after initial position established)
            if last_position is not None and abs(state['position'] - last_position) > 5.0:
                self.logger.warning(f"⚠️  Position drift detected: {last_position:.1f}% → {state['position']:.1f}%")
                self.logger.warning("Possible mechanical issue or spring relaxation")
            
            # Initialize last_position on first iteration
            if last_position is None:
                last_position = state['position']
            
            # SAFETY: Temperature decrease check (warn only)
            if current_temp < last_temp - 2:
                self.logger.warning(f"⚠️  Temperature decreased: {last_temp}°C → {current_temp}°C")
                self.logger.warning("Possible sensor failure or thermal protection active")
            
            # SAFETY: Reserve field monitoring (warn only)
            if hasattr(state['reserve'], '__iter__') and any(state['reserve']):
                self.logger.warning(f"⚠️  Non-zero reserve field: {state['reserve']} (may contain error codes)")
            elif not hasattr(state['reserve'], '__iter__') and state['reserve'] != 0:
                self.logger.warning(f"⚠️  Non-zero reserve field: {state['reserve']} (may contain error codes)")
            
            # Record detailed measurement with ALL DDS state data
            measurement = DetailedMeasurement(
                timestamp=time.time(),
                elapsed_sec=elapsed,
                force_pct=force_pct,
                position_pct=state['position'],
                temperature_c=current_temp,
                grasp_state='holding',
                velocity=state['velocity'],
                torque=state['torque'],
                lost=state['lost'],
                reserve=state['reserve']
            )
            self.detailed_measurements.append(measurement)
            
            # Update tracking variables
            last_position = state['position']
            last_temp = current_temp
            
            # Log every 2 seconds
            if time.time() - last_log_time >= 2.0:
                progress_pct = (temp_rise / temp_rise_target) * 100
                self.logger.info(f"  {elapsed:6.1f}s | Pos: {state['position']:5.1f}% | Temp: {current_temp:5.1f}°C | "
                               f"Rise: {temp_rise:+5.2f}°C | Progress: {progress_pct:5.1f}%")
                last_log_time = time.time()
            
            # Check if target reached
            if temp_rise >= temp_rise_target:
                wall_time = time.time() - test_start
                self.logger.info(f"\n✅ Target reached in {wall_time:.1f}s")
                self.logger.info(f"   Start: {start_temp:.1f}°C → End: {current_temp:.1f}°C (Rise: {temp_rise:.2f}°C)")
                break
            
            # Safety timeout (10 minutes)
            if elapsed > 600:
                self.logger.warning("⚠️  Timeout after 10 minutes - test incomplete")
                wall_time = elapsed
                break
            
            time.sleep(1.0 / 30.0)
        
        # Calculate results
        end_temp = state['temperature']
        actual_temp_rise = end_temp - start_temp
        heating_rate = actual_temp_rise / wall_time if wall_time > 0 else 0
        
        result = ThermalTestResult(
            force_pct=force_pct,
            force_multiplier=force_multiplier,
            start_temp_c=start_temp,
            end_temp_c=end_temp,
            temp_rise_c=actual_temp_rise,
            wall_time_sec=wall_time,
            heating_rate_c_per_sec=heating_rate,
            relative_power=0.0
        )
        
        self.test_results.append(result)
        
        self.logger.info(f"{'='*70}")
        self.logger.info(f"Test Result: {force_pct}% force ({force_multiplier}x)")
        self.logger.info(f"  Wall time:     {wall_time:.1f}s")
        self.logger.info(f"  Temp rise:     {actual_temp_rise:.1f}°C")
        self.logger.info(f"  Heating rate:  {heating_rate:.4f}°C/s")
        self.logger.info(f"{'='*70}\n")
        
        # Return to 30%
        self.logger.info("Returning to 30%...")
        for _ in range(30):
            self.send_position_command(30.0, 30.0)
            time.sleep(1.0 / 30.0)
        
        return result
    
    def run_calibration(self, base_force: float = 15.0,
                       temp_rise: float = 5.0,
                       cooldown_time: int = 60,
                       device: str = '/dev/ttyUSB0'):
        """
        Run full thermal calibration
        
        Tests 3 force levels: 15%, 20%, 25% (conservative increments)
        Restarts driver with correct grasping_force_pct before each test
        """
        forces = [15.0, 20.0, 25.0]
        force_multipliers = [f / base_force for f in forces]
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Thermal Grasp Calibration (DDS)")
        self.logger.info(f"{'='*70}")
        self.logger.info(f"Base force: {base_force}%")
        self.logger.info(f"Force levels: {forces}")
        self.logger.info(f"Temp rise target: {temp_rise}°C")
        self.logger.info(f"{'='*70}\n")
        
        for i, (force, mult) in enumerate(zip(forces, force_multipliers)):
            self.logger.info(f"\n>>> Test {i+1}/3 <<<")
            
            # Restart driver with correct grasping force for this test
            self._restart_driver_with_force(force, device)
            
            result = self.run_thermal_test(force, mult, temp_rise)
            
            # Cooldown between tests (except after last test)
            if i < len(forces) - 1:
                self.logger.info(f"\nCooling down for {cooldown_time}s...")
                self.logger.info("(Gripper at 30%, low force)")
                self.logger.info("")
                
                cooldown_start = time.time()
                last_cooldown_log = cooldown_start
                while time.time() - cooldown_start < cooldown_time:
                    self.send_position_command(30.0, 10.0)
                    
                    # Log every 3 seconds
                    elapsed = time.time() - cooldown_start
                    if time.time() - last_cooldown_log >= 3.0:
                        state = self.read_state()
                        remaining = cooldown_time - elapsed
                        progress_pct = (elapsed / cooldown_time) * 100
                        self.logger.info(f"  {elapsed:5.1f}s | Temp: {state['temperature']:.1f}°C | "
                                       f"Position: {state['position']:.1f}% | "
                                       f"Remaining: {remaining:4.0f}s | Progress: {progress_pct:5.1f}%")
                        last_cooldown_log = time.time()
                    
                    time.sleep(1.0 / 30.0)
        
        # Analyze results
        self.analyze_results()
    
    def analyze_results(self):
        """Analyze thermal test results"""
        if len(self.test_results) < 2:
            self.logger.warning("Need at least 2 tests for analysis")
            return
        
        # Calculate relative power (normalized to first test)
        base_rate = self.test_results[0].heating_rate_c_per_sec
        for result in self.test_results:
            if base_rate > 0:
                result.relative_power = result.heating_rate_c_per_sec / base_rate
            else:
                result.relative_power = 0.0
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Thermal Calibration Analysis")
        self.logger.info(f"{'='*70}\n")
        
        # Display results table
        self.logger.info("Results Summary:")
        self.logger.info(f"  {'Force':<10} {'Mult':<8} {'Time':<12} {'Rate':<15} {'Rel Power':<12}")
        self.logger.info(f"  {'-'*10} {'-'*8} {'-'*12} {'-'*15} {'-'*12}")
        
        for result in self.test_results:
            self.logger.info(f"  {result.force_pct:6.1f}%    {result.force_multiplier:.1f}x      "
                           f"{result.wall_time_sec:8.1f}s       {result.heating_rate_c_per_sec:11.4f}°C/s       "
                           f"{result.relative_power:8.2f}x")
        
        self.logger.info("")
        self.logger.info("Key Findings:")
        if len(self.test_results) >= 2:
            actual_2x = self.test_results[1].relative_power
            expected_2x = 2.0
            error_2x = abs(actual_2x - expected_2x) / expected_2x * 100
            self.logger.info(f"  Doubling force → {actual_2x:.2f}x power")
            self.logger.info(f"  2x force: expected {expected_2x:.2f}x, actual {actual_2x:.2f}x (error: {error_2x:.1f}%)")
        
        if len(self.test_results) >= 3:
            actual_3x = self.test_results[2].relative_power
            expected_3x = 3.0
            error_3x = abs(actual_3x - expected_3x) / expected_3x * 100
            self.logger.info(f"  Tripling force → {actual_3x:.2f}x power")
            self.logger.info(f"  3x force: expected {expected_3x:.2f}x, actual {actual_3x:.2f}x (error: {error_3x:.1f}%)")
        
        self.logger.info(f"\n{'='*70}\n")
    
    def save_results(self, base_filename: str = None):
        """Save calibration results"""
        if not base_filename:
            base_filename = f"thermal_grasp_dds_{self.side}_{int(time.time())}"
        
        # Save detailed measurements
        measurements_file = f"{base_filename}_measurements.csv"
        with open(measurements_file, 'w', newline='') as f:
            if self.detailed_measurements:
                writer = csv.DictWriter(f, fieldnames=self.detailed_measurements[0].to_dict().keys())
                writer.writeheader()
                for measurement in self.detailed_measurements:
                    writer.writerow(measurement.to_dict())
        
        self.logger.info(f"💾 Saved {len(self.detailed_measurements)} detailed measurements to {measurements_file}")
        
        # Save results
        results_file = f"{base_filename}_results.csv"
        with open(results_file, 'w', newline='') as f:
            if self.test_results:
                writer = csv.DictWriter(f, fieldnames=self.test_results[0].to_dict().keys())
                writer.writeheader()
                for result in self.test_results:
                    writer.writerow(result.to_dict())
        
        self.logger.info(f"💾 Saved {len(self.test_results)} results to {results_file}")
        
        # Save summary
        summary = {
            'base_force': self.test_results[0].force_pct if self.test_results else 0,
            'forces': [r.force_pct for r in self.test_results],
            'wall_times': [r.wall_time_sec for r in self.test_results],
            'heating_rates': [r.heating_rate_c_per_sec for r in self.test_results],
            'relative_powers': [r.relative_power for r in self.test_results]
        }
        
        summary_file = f"{base_filename}_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        self.logger.info(f"💾 Saved summary to {summary_file}")


def main():
    parser = argparse.ArgumentParser(description='Thermal Grasp Test via DDS')
    parser.add_argument('--side', required=True, choices=['left', 'right'])
    parser.add_argument('--base-force', type=float, default=15.0,
                       help='Base force level (default: 15%%)')
    parser.add_argument('--temp-rise', type=float, default=5.0,
                       help='Temperature rise target (default: 5°C)')
    parser.add_argument('--dev', default='/dev/ttyUSB0',
                       help='USB device (default: /dev/ttyUSB0)')
    parser.add_argument('--output', default=None)
    parser.add_argument('--single-force', type=float,
                       help='Run single test at specified force level (e.g., 15, 20, 25)')
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("THERMAL GRASP TEST VIA DDS")
    print("="*70)
    print(f"Side: {args.side}")
    print(f"Base force: {args.base_force}%")
    print(f"Temp rise target: {args.temp_rise}°C")
    
    if args.single_force:
        print(f"Single test mode: {args.single_force}% force")
        print("")
        print("NOTE: Make sure driver is running with grasping_force_pct")
        print(f"      set to {args.single_force}% in config file!")
    else:
        print("")
        print("NOTE: Driver will be automatically restarted with correct force")
        print("      settings for each test level.")
    print("="*70 + "\n")
    
    test = ThermalGraspDDS(side=args.side)
    
    if args.single_force:
        # Run single test without driver restart
        result = test.run_thermal_test(args.single_force, 
                                      args.single_force / args.base_force,
                                      args.temp_rise)
        test.test_results = [result]
        test.save_results(base_filename=args.output)
    else:
        # Run full calibration with automatic driver restarts
        test.run_calibration(base_force=args.base_force,
                            temp_rise=args.temp_rise,
                            device=args.dev)
        test.save_results(base_filename=args.output)


if __name__ == '__main__':
    main()
