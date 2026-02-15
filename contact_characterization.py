#!/usr/bin/env python3
"""
Contact Power Characterization

Characterize power consumption during the CONTACT phase:
- Rapid closing from 30% → 0% (contact)
- Measure current draw during movement
- Detect contact point
- Measure contact impact current spike
- Characterize transition to static grasp

This completes the power profile for the full grasp cycle:
1. Moving: 30% → contact position
2. Contact: Impact and detection
3. Grasping: Static hold (already characterized)

Usage:
    python3 contact_characterization.py --side left --base-force 15
"""

import argparse
import time
import csv
import json
import logging
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import numpy as np

from libezgripper import create_connection, create_gripper


@dataclass
class CyclingMeasurement:
    """Single measurement during cycling test"""
    timestamp: float
    elapsed_sec: float
    
    # Test parameters
    force_pct: float
    cycle_number: int
    
    # Position tracking
    position_pct: float
    target_position_pct: float
    
    # Temperature (only reliable metric)
    temperature_c: float
    
    # Phase detection
    phase: str  # 'opening', 'closing'
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CyclingTestResult:
    """Summary of one cycling test"""
    force_pct: float
    force_multiplier: float
    
    # Test duration
    total_cycles: int
    total_time_sec: float
    
    # Temperature (only reliable metric)
    start_temp_c: float
    end_temp_c: float
    temp_rise_c: float
    
    # Derived power metric
    heating_rate_c_per_sec: float
    relative_power: float  # Normalized to 1x force
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContactCharacterization:
    """Characterize power consumption during rapid cycling operations"""
    
    def __init__(self, side: str, device: str = "/dev/ttyUSB0"):
        self.side = side
        self.device = device
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            force=True
        )
        self.logger = logging.getLogger(__name__)
        
        print(f"Connecting to {side} gripper on {device}...", flush=True)
        
        # Initialize hardware
        self.connection = create_connection(dev_name=device, baudrate=1000000)
        time.sleep(2.0)
        
        self.gripper = create_gripper(self.connection, f'contact_char_{side}', [1])
        
        # Run calibration to ensure accurate position mapping
        self._run_calibration()
        
        # Results
        self.measurements: List[CyclingMeasurement] = []
        self.test_results: List[CyclingTestResult] = []
        
        self.logger.info("✅ Contact Characterization Ready")
    
    def _run_calibration(self):
        """Run calibration and save to config file"""
        config_file = '/tmp/ezgripper_device_config.json'
        
        self.logger.info("Running calibration...")
        self.logger.info("Please ensure gripper is unobstructed and can open fully")
        
        try:
            # Run calibration
            self.gripper.calibrate()
            zero_position = self.gripper.zero_positions[0]
            calibration_offset = abs(zero_position)
            
            self.logger.info(f"✅ Calibration complete: zero_position={zero_position}, offset={calibration_offset}")
            
            # Get serial number
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            serial_number = 'unknown'
            for port in ports:
                if port.device == self.device:
                    serial_number = port.serial_number if port.serial_number else 'unknown'
                    break
            
            # Save to config file
            config = {}
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
            
            if 'calibration' not in config:
                config['calibration'] = {}
            
            config['calibration'][serial_number] = calibration_offset
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            self.logger.info(f"✅ Saved calibration for serial {serial_number} to {config_file}")
            
        except Exception as e:
            self.logger.error(f"Calibration failed: {e}")
            raise
    
    def read_sensors(self) -> Dict[str, Any]:
        """Read sensor data"""
        return self.gripper.bulk_read_sensor_data()
    
    def run_cycling_test(self, force_pct: float, force_multiplier: float,
                        test_duration_sec: float = 120.0) -> CyclingTestResult:
        """
        Run thermal cycling test
        
        Performs continuous rapid cycles for specified duration:
        - 30% → 0% → 30% → 0% ... (continuous)
        - Measures temperature rise over time
        - Only temperature is reliable in Mode 5
        
        Goal: Measure power during active cycling operations
        
        Args:
            force_pct: Grasping force percentage
            force_multiplier: 1x, 2x, 3x for comparison
            test_duration_sec: How long to cycle (default: 120s = 2 minutes)
        """
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Cycling Test: {force_pct}% force ({force_multiplier}x)")
        self.logger.info(f"Duration: {test_duration_sec}s")
        self.logger.info(f"{'='*70}")
        
        # Record starting temperature
        start_sensors = self.read_sensors()
        start_temp = start_sensors['temperature']
        self.logger.info(f"\nStart temperature: {start_temp:.1f}°C")
        
        # Cycling state
        test_start = time.time()
        cycle_count = 0
        closing = True  # Start by closing
        last_log_time = test_start
        
        # Continuous cycling until duration reached
        self.logger.info(f"\nStarting continuous cycling (30% ↔ 0%)...")
        self.logger.info(f"Force: {force_pct}%")
        self.logger.info("")
        
        while True:
            sensors = self.read_sensors()
            elapsed = time.time() - test_start
            
            # Check if test duration reached
            if elapsed >= test_duration_sec:
                break
            
            # Continuous cycling: 30% → 0% → 30% → 0%...
            if closing:
                self.gripper.goto_position(0.0, force_pct)
                # Check if reached 0%
                if sensors['position'] < 3.0:
                    closing = False
                    cycle_count += 0.5  # Half cycle (close)
            else:
                self.gripper.goto_position(30.0, force_pct)
                # Check if reached 30%
                if sensors['position'] > 27.0:
                    closing = True
                    cycle_count += 0.5  # Half cycle (open)
            
            current_temp = sensors['temperature']
            temp_rise = current_temp - start_temp
            
            # Record measurement every cycle
            measurement = CyclingMeasurement(
                timestamp=time.time(),
                elapsed_sec=elapsed,
                force_pct=force_pct,
                cycle_number=int(cycle_count),
                position_pct=sensors['position'],
                target_position_pct=0.0 if closing else 30.0,
                temperature_c=current_temp,
                phase='closing' if closing else 'opening'
            )
            self.measurements.append(measurement)
            
            # Log every 5 seconds
            if time.time() - last_log_time >= 5.0:
                direction = "Closing" if closing else "Opening"
                progress_pct = (elapsed / test_duration_sec) * 100
                self.logger.info(f"  {elapsed:6.1f}s | Cycles: {cycle_count:5.1f} | {direction:7s} | "
                               f"Pos: {sensors['position']:5.1f}% | Temp: {current_temp:5.1f}°C | "
                               f"Rise: {temp_rise:+5.2f}°C | Progress: {progress_pct:5.1f}%")
                last_log_time = time.time()
            
            time.sleep(1.0 / 30.0)
        
        # Calculate results
        end_sensors = self.read_sensors()
        end_temp = end_sensors['temperature']
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
            relative_power=0.0  # Will be calculated after all tests
        )
        
        self.test_results.append(result)
        
        # Log results
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
        Measures temperature rise during active cycling operations
        """
        force_multipliers = [1.0, 2.0, 3.0]
        forces = [base_force * mult for mult in force_multipliers]
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Cycling Power Characterization")
        self.logger.info(f"{'='*70}")
        self.logger.info(f"Base force: {base_force}%")
        self.logger.info(f"Force levels: {forces}")
        self.logger.info(f"Test duration: {test_duration_sec}s per force level")
        self.logger.info(f"Cooldown: {cooldown_time}s between tests")
        self.logger.info(f"{'='*70}\n")
        
        for i, (force, mult) in enumerate(zip(forces, force_multipliers)):
            self.logger.info(f"\n>>> Test {i+1}/3 <<<")
            
            result = self.run_cycling_test(force, mult, test_duration_sec)
            
            # Cooldown between tests (except after last test)
            if i < len(forces) - 1:
                self.logger.info(f"\nCooling down for {cooldown_time}s...")
                self.logger.info("(Gripper at 30%, low force)")
                
                cooldown_start = time.time()
                while time.time() - cooldown_start < cooldown_time:
                    self.gripper.goto_position(30.0, 10.0)
                    time.sleep(1.0 / 30.0)
        
        # Analyze results
        self.analyze_results()
    
    def analyze_results(self):
        """Analyze cycling characterization results"""
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
        self.logger.info(f"Cycling Characterization Analysis")
        self.logger.info(f"{'='*70}\n")
        
        # Display results table
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
            base_filename = f"contact_char_{self.side}_{int(time.time())}"
        
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
    parser = argparse.ArgumentParser(description='Contact Power Characterization')
    parser.add_argument('--side', required=True, choices=['left', 'right'])
    parser.add_argument('--dev', default='/dev/ttyUSB0')
    parser.add_argument('--base-force', type=float, default=15.0,
                       help='Base force level (default: 15%%)')
    parser.add_argument('--duration', type=int, default=120,
                       help='Test duration in seconds (default: 120s = 2 minutes)')
    parser.add_argument('--output', default=None)
    
    args = parser.parse_args()
    
    char = ContactCharacterization(side=args.side, device=args.dev)
    char.run_characterization(base_force=args.base_force,
                             test_duration_sec=args.duration)
    char.save_results(base_filename=args.output)


if __name__ == '__main__':
    main()
