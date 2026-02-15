#!/usr/bin/env python3
"""
Thermal Cycling Test via DDS Interface

Measures power consumption during rapid cycling via temperature rise.
Communicates ONLY through DDS - requires ezgripper_dds_driver to be running.

Usage:
    # Terminal 1: Start DDS driver
    python3 ezgripper_dds_driver.py --side left
    
    # Terminal 2: Run test
    python3 thermal_cycling_dds.py --side left --base-force 15 --duration 120
"""

import argparse
import time
import csv
import json
import logging
import signal
import sys
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_, MotorStates_, MotorState_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_


@dataclass
class CyclingMeasurement:
    """Single measurement during cycling test"""
    timestamp: float
    elapsed_sec: float
    force_pct: float
    cycle_number: int
    position_pct: float
    target_position_pct: float
    temperature_c: float
    phase: str
    velocity: float
    torque: float
    lost: int
    reserve: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CyclingTestResult:
    """Summary of one cycling test"""
    force_pct: float
    force_multiplier: float
    total_cycles: int
    total_time_sec: float
    start_temp_c: float
    end_temp_c: float
    temp_rise_c: float
    heating_rate_c_per_sec: float
    relative_power: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ThermalCyclingDDS:
    """Thermal cycling test using DDS interface only"""
    
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
        
        self.logger.info(f"Initializing DDS thermal cycling test for {side} gripper...")
        
        # Initialize DDS
        ChannelFactoryInitialize(0)
        
        # Create publisher for commands
        self.cmd_topic = f"rt/dex1/{side}/cmd"
        self.cmd_publisher = ChannelPublisher(self.cmd_topic, MotorCmds_)
        self.cmd_publisher.Init()
        
        # Create subscriber for states
        self.state_topic = f"rt/dex1/{side}/state"
        self.state_subscriber = ChannelSubscriber(self.state_topic, MotorStates_)
        self.state_subscriber.Init()
        
        # Results
        self.test_results: List[CyclingTestResult] = []
        self.measurements: List[CyclingMeasurement] = []
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Latest state
        self.latest_state = None
        
        self.logger.info(f"✅ DDS initialized")
        self.logger.info(f"   Publishing commands to: {self.cmd_topic}")
        self.logger.info(f"   Subscribing to states from: {self.state_topic}")
        
        # Validate DDS connection
        self._validate_connection()
    
    def send_position_command(self, position_pct: float, effort_pct: float = 50.0):
        """Send position command via DDS"""
        # Convert position % to radians (0% = 0 rad, 100% = 5.4 rad)
        q_radians = (position_pct / 100.0) * 5.4
        
        # Create motor command
        motor_cmd = unitree_go_msg_dds__MotorCmd_()
        motor_cmd.q = q_radians
        motor_cmd.dq = 0.0
        motor_cmd.tau = 0.0
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
            
            # Convert radians to percentage
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
        
        if self.latest_state:
            return self.latest_state
        
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
        """Handle Ctrl+C and kill signals gracefully"""
        if not self._shutdown_requested:
            self._shutdown_requested = True
            signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
            self.logger.warning(f"\n⚠️  Received {signal_name} - initiating graceful shutdown...")
            self._emergency_stop(f"User interrupt ({signal_name})")
            sys.exit(0)
    
    def _emergency_stop(self, reason: str):
        """Emergency stop - send gripper to safe open position"""
        self.logger.error(f"🚨 EMERGENCY STOP: {reason}")
        self.logger.error("Moving gripper to safe open position...")
        for _ in range(30):  # 1 second at 30Hz
            self.send_position_command(30.0, 10.0)
            time.sleep(1.0 / 30.0)
        self.logger.error("Gripper stopped. Test aborted.")
    
    def run_cycling_test(self, force_pct: float, force_multiplier: float,
                        test_duration_sec: float = 120.0) -> CyclingTestResult:
        """
        Run thermal cycling test via DDS
        
        Performs continuous rapid cycles for specified duration:
        - Close to 0% (contact)
        - Open to 30% (release)
        - Monitor temperature rise
        
        Safety aborts:
        - Temperature > 75°C (critical)
        - Communication errors (lost > 0)
        - Starting temperature > 50°C (requires cooldown)
        - Gripper stall (no movement for 5s)
        """
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Cycling Test: {force_pct}% force ({force_multiplier}x)")
        self.logger.info(f"Duration: {test_duration_sec}s")
        self.logger.info(f"{'='*70}")
        
        # Record starting temperature
        start_state = self.read_state()
        start_temp = start_state['temperature']
        
        # SAFETY: Pre-test temperature validation
        if start_temp > 50:
            self.logger.error(f"⚠️  ABORT: Starting temperature {start_temp}°C exceeds 50°C safety limit")
            self.logger.error("Gripper requires additional cooldown before testing.")
            raise RuntimeError(f"Starting temperature too high: {start_temp}°C > 50°C")
        
        # SAFETY: Check for absolute maximum
        if start_temp > 70:
            self._emergency_stop(f"Starting temperature {start_temp}°C exceeds 70°C operating limit")
            raise RuntimeError(f"Temperature exceeds operating limit: {start_temp}°C")
        
        # Cycling state
        test_start = time.time()
        cycle_count = 0
        closing = True
        last_log_time = test_start
        
        self.logger.info(f"\nStart temperature: {start_temp:.1f}°C ✅")
        self.logger.info(f"\nStarting continuous cycling (30% ↔ 0%)...")
        self.logger.info(f"Force: {force_pct}%")
        self.logger.info("")
        
        last_position_change = time.time()
        last_position = start_state['position']
        
        while True:
            state = self.read_state()
            elapsed = time.time() - test_start
            
            # Check if test duration reached
            if elapsed >= test_duration_sec:
                break
            
            # SAFETY: Critical temperature limit
            if state['temperature'] >= 75:
                self._emergency_stop(f"Temperature {state['temperature']}°C exceeds 75°C critical limit")
                raise RuntimeError(f"Temperature safety limit exceeded: {state['temperature']}°C >= 75°C")
            
            # SAFETY: Absolute maximum temperature
            if state['temperature'] >= 80:
                self._emergency_stop(f"Temperature {state['temperature']}°C exceeds 80°C absolute maximum")
                raise RuntimeError(f"Temperature absolute maximum exceeded: {state['temperature']}°C >= 80°C")
            
            # SAFETY: Communication error check
            if state['lost'] > 0:
                self._emergency_stop(f"Communication error detected (lost={state['lost']})")
                raise RuntimeError("DDS communication failure")
            
            # SAFETY: Stall detection
            if abs(state['position'] - last_position) > 1.0:  # Position changed by >1%
                last_position_change = time.time()
                last_position = state['position']
            elif time.time() - last_position_change > 5.0:  # No movement for 5s
                self._emergency_stop(f"Gripper stalled (no movement for 5s at {state['position']:.1f}%)")
                raise RuntimeError("Gripper stall detected")
            
            # SAFETY: Reserve field monitoring (warn only)
            if hasattr(state['reserve'], '__iter__') and any(state['reserve']):
                self.logger.warning(f"⚠️  Non-zero reserve field: {state['reserve']} (may contain error codes)")
            elif not hasattr(state['reserve'], '__iter__') and state['reserve'] != 0:
                self.logger.warning(f"⚠️  Non-zero reserve field: {state['reserve']} (may contain error codes)")
            
            # Continuous cycling
            if closing:
                self.send_position_command(0.0, force_pct)
                if state['position'] < 3.0:
                    closing = False
                    cycle_count += 0.5
            else:
                self.send_position_command(30.0, force_pct)
                if state['position'] > 27.0:
                    closing = True
                    cycle_count += 0.5
            
            current_temp = state['temperature']
            temp_rise = current_temp - start_temp
            
            # SAFETY: Warn if no cycles occurring
            if elapsed > 10.0 and cycle_count == 0:
                self.logger.warning(f"⚠️  No cycles detected after {elapsed:.1f}s - gripper may not be moving")
            
            # Record measurement with ALL DDS state data
            measurement = CyclingMeasurement(
                timestamp=time.time(),
                elapsed_sec=elapsed,
                force_pct=force_pct,
                cycle_number=int(cycle_count),
                position_pct=state['position'],
                target_position_pct=0.0 if closing else 30.0,
                temperature_c=current_temp,
                phase='closing' if closing else 'opening',
                velocity=state['velocity'],
                torque=state['torque'],
                lost=state['lost'],
                reserve=state['reserve']
            )
            self.measurements.append(measurement)
            
            # Log every 5 seconds
            if time.time() - last_log_time >= 5.0:
                direction = "Closing" if closing else "Opening"
                progress_pct = (elapsed / test_duration_sec) * 100
                stall_time = time.time() - last_position_change
                self.logger.info(f"  {elapsed:6.1f}s | Cycles: {cycle_count:5.1f} | {direction:7s} | "
                               f"Pos: {state['position']:5.1f}% | Temp: {current_temp:5.1f}°C | "
                               f"Rise: {temp_rise:+5.2f}°C | Progress: {progress_pct:5.1f}%")
                last_log_time = time.time()
            
            time.sleep(1.0 / 30.0)
        
        # Calculate results
        end_state = self.read_state()
        end_temp = end_state['temperature']
        temp_rise = end_temp - start_temp
        total_time = time.time() - test_start
        heating_rate = temp_rise / total_time if total_time > 0 else 0
        
        result = CyclingTestResult(
            force_pct=force_pct,
            force_multiplier=force_multiplier,
            total_cycles=int(cycle_count),
            total_time_sec=total_time,
            start_temp_c=start_temp,
            end_temp_c=end_temp,
            temp_rise_c=temp_rise,
            heating_rate_c_per_sec=heating_rate,
            relative_power=0.0
        )
        
        self.test_results.append(result)
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Cycling Test Result: {force_pct}% force ({force_multiplier}x)")
        self.logger.info(f"  Total cycles:  {result.total_cycles}")
        self.logger.info(f"  Total time:    {result.total_time_sec:.1f}s")
        self.logger.info(f"  Temp rise:     {result.temp_rise_c:.2f}°C")
        self.logger.info(f"  Heating rate:  {result.heating_rate_c_per_sec:.4f}°C/s")
        self.logger.info(f"{'='*70}\n")
        
        return result
    
    def run_characterization(self, base_force: float = 15.0,
                           test_duration_sec: float = 120.0,
                           cooldown_time: int = 60):
        """
        Run full cycling characterization
        
        Tests 3 force levels (1x, 2x, 3x) with continuous cycling
        """
        force_multipliers = [1.0, 2.0, 3.0]
        forces = [base_force * mult for mult in force_multipliers]
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Cycling Power Characterization (DDS)")
        self.logger.info(f"{'='*70}")
        self.logger.info(f"Base force: {base_force}%")
        self.logger.info(f"Force levels: {forces}")
        self.logger.info(f"Test duration: {test_duration_sec}s per force level")
        self.logger.info(f"Cooldown: {cooldown_time}s between tests")
        self.logger.info(f"{'='*70}\n")
        
        for i, (force, mult) in enumerate(zip(forces, force_multipliers)):
            self.logger.info(f"\n>>> Test {i+1}/3 <<<")
            
            result = self.run_cycling_test(force, mult, test_duration_sec)
            
            # Cooldown between tests
            if i < len(forces) - 1:
                self.logger.info(f"\nCooling down for {cooldown_time}s...")
                self.logger.info("(Gripper at 30%, low force)")
                
                cooldown_start = time.time()
                while time.time() - cooldown_start < cooldown_time:
                    self.send_position_command(30.0, 10.0)
                    time.sleep(1.0 / 30.0)
        
        # Analyze results
        self.analyze_results()
    
    def analyze_results(self):
        """Analyze cycling characterization results"""
        if len(self.test_results) < 2:
            self.logger.warning("Need at least 2 tests for analysis")
            return
        
        # Calculate relative power
        base_rate = self.test_results[0].heating_rate_c_per_sec
        for result in self.test_results:
            if base_rate > 0:
                result.relative_power = result.heating_rate_c_per_sec / base_rate
            else:
                result.relative_power = 0.0
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Cycling Characterization Analysis")
        self.logger.info(f"{'='*70}\n")
        
        self.logger.info("Results Summary:")
        self.logger.info(f"  {'Force':<10} {'Mult':<8} {'Cycles':<10} {'Time':<12} {'Temp Rise':<12} {'Rate':<15} {'Rel Power':<12}")
        self.logger.info(f"  {'-'*10} {'-'*8} {'-'*10} {'-'*12} {'-'*12} {'-'*15} {'-'*12}")
        
        for result in self.test_results:
            self.logger.info(f"  {result.force_pct:6.1f}%    {result.force_multiplier:.1f}x      "
                           f"{result.total_cycles:6d}     {result.total_time_sec:8.1f}s    "
                           f"{result.temp_rise_c:8.2f}°C    {result.heating_rate_c_per_sec:11.4f}°C/s    "
                           f"{result.relative_power:8.2f}x")
        
        self.logger.info("")
        self.logger.info("Key Findings:")
        if len(self.test_results) >= 2:
            actual_2x = self.test_results[1].relative_power
            self.logger.info(f"  Doubling force → {actual_2x:.2f}x power")
        if len(self.test_results) >= 3:
            actual_3x = self.test_results[2].relative_power
            self.logger.info(f"  Tripling force → {actual_3x:.2f}x power")
        
        self.logger.info(f"\n{'='*70}\n")
    
    def save_results(self, base_filename: str = None):
        """Save characterization results"""
        if not base_filename:
            base_filename = f"thermal_cycling_dds_{self.side}_{int(time.time())}"
        
        # Save measurements
        measurements_file = f"{base_filename}_measurements.csv"
        with open(measurements_file, 'w', newline='') as f:
            if self.measurements:
                writer = csv.DictWriter(f, fieldnames=self.measurements[0].to_dict().keys())
                writer.writeheader()
                for measurement in self.measurements:
                    writer.writerow(measurement.to_dict())
        
        self.logger.info(f"💾 Saved {len(self.measurements)} measurements to {measurements_file}")
        
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
            'total_cycles': [r.total_cycles for r in self.test_results],
            'temp_rises': [r.temp_rise_c for r in self.test_results],
            'heating_rates': [r.heating_rate_c_per_sec for r in self.test_results],
            'relative_powers': [r.relative_power for r in self.test_results]
        }
        
        summary_file = f"{base_filename}_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        self.logger.info(f"💾 Saved summary to {summary_file}")


def main():
    parser = argparse.ArgumentParser(description='Thermal Cycling Test via DDS')
    parser.add_argument('--side', required=True, choices=['left', 'right'])
    parser.add_argument('--base-force', type=float, default=15.0,
                       help='Base force level (default: 15%%)')
    parser.add_argument('--duration', type=int, default=120,
                       help='Test duration in seconds (default: 120s)')
    parser.add_argument('--output', default=None)
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("THERMAL CYCLING TEST VIA DDS")
    print("="*70)
    print(f"Side: {args.side}")
    print(f"Base force: {args.base_force}%")
    print(f"Test duration: {args.duration}s per force level")
    print("")
    print("IMPORTANT: ezgripper_dds_driver must be running!")
    print(f"  python3 ezgripper_dds_driver.py --side {args.side}")
    print("="*70 + "\n")
    
    test = ThermalCyclingDDS(side=args.side)
    test.run_characterization(base_force=args.base_force,
                             test_duration_sec=args.duration)
    test.save_results(base_filename=args.output)


if __name__ == '__main__':
    main()
