#!/usr/bin/env python3
"""
Simple Thermal Power Calibration

Measure power consumption via thermal method:
- Close from 30% → 0% and hold
- Wait until temperature rises 5°C
- Record wall time
- Repeat at 3 force levels: 1x, 2x, 3x base force

Power is proportional to heating rate: faster heating = more power

Usage:
    python3 simple_power_calibration.py --side left --base-force 15
"""

import argparse
import time
import csv
import json
import logging
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

from libezgripper import create_connection, create_gripper


@dataclass
class DetailedMeasurement:
    """Detailed measurement point during test"""
    timestamp: float
    elapsed_sec: float
    force_pct: float
    position_pct: float
    temperature_c: float
    current_ma: float
    voltage_v: float
    power_w: float
    error_code: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ThermalTestResult:
    """Result from one thermal test"""
    force_pct: float
    force_multiplier: float  # 1x, 2x, 3x
    
    start_temp_c: float
    end_temp_c: float
    temp_rise_c: float
    
    wall_time_sec: float
    heating_rate_c_per_sec: float
    
    # Relative power (normalized to 1x force)
    relative_power: float
    
    # Error tracking
    error_count: int
    first_error_time_sec: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SimplePowerCalibration:
    """Simple thermal power calibration"""
    
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
        
        self.gripper = create_gripper(self.connection, f'thermal_cal_{side}', [1])
        
        # Run calibration to ensure accurate position mapping
        self._run_calibration()
        
        # Results
        self.test_results: List[ThermalTestResult] = []
        self.detailed_measurements: List[DetailedMeasurement] = []
        
        self.logger.info("✅ Simple Power Calibration Ready")
    
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
        """Read sensor data including error register"""
        data = self.gripper.bulk_read_sensor_data()
        
        # Read error register (not in bulk read)
        try:
            error = self.gripper.servos[0].read_byte(70)  # Hardware Error Status register
            data['error'] = error
        except:
            data['error'] = 0
        
        return data
    
    def run_thermal_test(self, force_pct: float, force_multiplier: float, 
                        temp_rise_target: float = 5.0) -> ThermalTestResult:
        """
        Run one thermal test
        
        1. Start at 30%
        2. Close to 0% and hold with force_pct
        3. Wait until temperature rises temp_rise_target degrees
        4. Record wall time
        """
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Thermal Test: {force_pct}% force ({force_multiplier}x)")
        self.logger.info(f"Target temp rise: {temp_rise_target}°C")
        self.logger.info(f"{'='*70}")
        
        # Move to 30% starting position
        self.logger.info("Moving to start position (30%)...")
        for i in range(90):  # 3 seconds
            self.gripper.goto_position(30.0, 30.0)
            if i % 15 == 0:  # Every 0.5 seconds
                sensors = self.read_sensors()
                self.logger.info(f"  Position: {sensors['position']:.1f}%, Temp: {sensors['temperature']:.1f}°C")
            time.sleep(1.0 / 30.0)
        
        time.sleep(1.0)
        
        # Record starting temperature
        start_sensors = self.read_sensors()
        start_temp = start_sensors['temperature']
        target_temp = start_temp + temp_rise_target
        
        self.logger.info(f"\nStart temperature: {start_temp:.1f}°C")
        self.logger.info(f"Target temperature: {target_temp:.1f}°C")
        
        # Close to 0% (contact)
        self.logger.info("\nClosing to 0% (contact)...")
        contact_start = time.time()
        last_contact_log = contact_start
        while time.time() - contact_start < 3.0:
            sensors = self.read_sensors()
            self.gripper.goto_position(0.0, force_pct)
            
            # Log every 0.5 seconds during closing
            if time.time() - last_contact_log >= 0.5:
                self.logger.info(f"  Position: {sensors['position']:.1f}%, Temp: {sensors['temperature']:.1f}°C")
                last_contact_log = time.time()
            
            if sensors['position'] < 3.0:
                self.logger.info(f"  ✅ Contact at {sensors['position']:.1f}%, Temp: {sensors['temperature']:.1f}°C")
                break
            
            time.sleep(1.0 / 30.0)
        
        # Hold and wait for temperature rise
        self.logger.info(f"\nHolding at 0% with {force_pct}% force...")
        self.logger.info(f"Waiting for temperature to rise {temp_rise_target}°C...")
        self.logger.info(f"Start: {start_temp:.1f}°C → Target: {target_temp:.1f}°C")
        self.logger.info("")
        
        test_start = time.time()
        last_log_time = test_start
        error_count = 0
        first_error_time = None
        
        while True:
            sensors = self.read_sensors()
            self.gripper.goto_position(0.0, force_pct)
            
            current_temp = sensors['temperature']
            temp_rise = current_temp - start_temp
            elapsed = time.time() - test_start
            remaining = temp_rise_target - temp_rise
            error_code = sensors.get('error', 0)
            
            # Track errors
            if error_code != 0:
                error_count += 1
                if first_error_time is None:
                    first_error_time = elapsed
                    self.logger.warning(f"  ⚠️  ERROR {error_code} detected at {elapsed:.1f}s!")
            
            # Record detailed measurement every cycle (30Hz)
            current_ma = abs(sensors.get('current', 0))
            voltage = sensors.get('voltage', 12.0)
            power = (voltage * current_ma) / 1000.0
            
            measurement = DetailedMeasurement(
                timestamp=time.time(),
                elapsed_sec=elapsed,
                force_pct=force_pct,
                position_pct=sensors['position'],
                temperature_c=current_temp,
                current_ma=current_ma,
                voltage_v=voltage,
                power_w=power,
                error_code=error_code
            )
            self.detailed_measurements.append(measurement)
            
            # Log every 2 seconds for better monitoring
            if time.time() - last_log_time >= 2.0:
                progress_pct = (temp_rise / temp_rise_target) * 100
                error_str = f" | ERROR: {error_code}" if error_code != 0 else ""
                self.logger.info(f"  {elapsed:6.1f}s | Pos: {sensors['position']:5.1f}% | Temp: {current_temp:5.1f}°C | "
                               f"Rise: {temp_rise:+5.2f}°C | Progress: {progress_pct:5.1f}%{error_str}")
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
        end_temp = sensors['temperature']
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
            relative_power=0.0,  # Will be calculated after all tests
            error_count=error_count,
            first_error_time_sec=first_error_time if first_error_time else 0.0
        )
        
        self.test_results.append(result)
        
        self.logger.info(f"{'='*70}")
        self.logger.info(f"Test Result: {force_pct}% force ({force_multiplier}x)")
        self.logger.info(f"  Wall time:     {wall_time:.1f}s")
        self.logger.info(f"  Temp rise:     {actual_temp_rise:.1f}°C")
        self.logger.info(f"  Heating rate:  {heating_rate:.4f}°C/s")
        if error_count > 0:
            self.logger.info(f"  ⚠️  Errors:      {error_count} errors detected")
            self.logger.info(f"  ⚠️  First error: {first_error_time:.1f}s into test")
        self.logger.info(f"{'='*70}\n")
        
        # Return to 30%
        self.logger.info("Returning to 30%...")
        for _ in range(30):
            self.gripper.goto_position(30.0, 30.0)
            time.sleep(1.0 / 30.0)
        
        return result
    
    def run_calibration(self, base_force: float = 15.0, 
                       temp_rise: float = 5.0,
                       cooldown_time: float = 60.0):
        """
        Run full thermal calibration
        
        3 tests at 1x, 2x, 3x base force
        Each waits for same temperature rise
        """
        force_multipliers = [1.0, 2.0, 3.0]
        forces = [base_force * mult for mult in force_multipliers]
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Simple Thermal Power Calibration")
        self.logger.info(f"{'='*70}")
        self.logger.info(f"Base force: {base_force}%")
        self.logger.info(f"Force levels: {forces}")
        self.logger.info(f"Temperature rise target: {temp_rise}°C")
        self.logger.info(f"Cooldown between tests: {cooldown_time}s")
        self.logger.info(f"{'='*70}\n")
        
        for i, (force, mult) in enumerate(zip(forces, force_multipliers)):
            self.logger.info(f"\n>>> Test {i+1}/3 <<<")
            
            result = self.run_thermal_test(force, mult, temp_rise)
            
            # Cooldown between tests (except after last test)
            if i < len(forces) - 1:
                self.logger.info(f"\nCooling down for {cooldown_time}s...")
                self.logger.info("(Gripper at 30%, low force)")
                self.logger.info("")
                
                cooldown_start = time.time()
                last_cooldown_log = cooldown_start
                while time.time() - cooldown_start < cooldown_time:
                    self.gripper.goto_position(30.0, 10.0)
                    
                    # Log every 3 seconds for better monitoring
                    elapsed = time.time() - cooldown_start
                    if time.time() - last_cooldown_log >= 3.0:
                        sensors = self.read_sensors()
                        remaining = cooldown_time - elapsed
                        progress_pct = (elapsed / cooldown_time) * 100
                        self.logger.info(f"  {elapsed:5.1f}s | Temp: {sensors['temperature']:.1f}°C | "
                                       f"Position: {sensors['position']:.1f}% | "
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
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Thermal Calibration Analysis")
        self.logger.info(f"{'='*70}\n")
        
        # Calculate relative power (heating rate is proportional to power)
        # Normalize to 1x force
        base_heating_rate = self.test_results[0].heating_rate_c_per_sec
        
        for result in self.test_results:
            result.relative_power = result.heating_rate_c_per_sec / base_heating_rate
        
        # Display results
        self.logger.info("Results Summary:")
        self.logger.info(f"  {'Force':<10} {'Mult':<8} {'Time':<12} {'Rate':<15} {'Rel Power':<12}")
        self.logger.info(f"  {'-'*10} {'-'*8} {'-'*12} {'-'*15} {'-'*12}")
        
        for result in self.test_results:
            self.logger.info(f"  {result.force_pct:6.1f}%   {result.force_multiplier:4.1f}x   "
                           f"{result.wall_time_sec:8.1f}s   {result.heating_rate_c_per_sec:10.4f}°C/s   "
                           f"{result.relative_power:8.2f}x")
        
        self.logger.info("")
        self.logger.info("Key Findings:")
        self.logger.info(f"  Doubling force → {self.test_results[1].relative_power:.2f}x power")
        self.logger.info(f"  Tripling force → {self.test_results[2].relative_power:.2f}x power")
        
        # Check linearity
        expected_2x = 2.0
        expected_3x = 3.0
        actual_2x = self.test_results[1].relative_power
        actual_3x = self.test_results[2].relative_power
        
        error_2x = abs(actual_2x - expected_2x) / expected_2x * 100
        error_3x = abs(actual_3x - expected_3x) / expected_3x * 100
        
        self.logger.info("")
        self.logger.info("Linearity Check:")
        self.logger.info(f"  2x force: expected {expected_2x:.2f}x, actual {actual_2x:.2f}x (error: {error_2x:.1f}%)")
        self.logger.info(f"  3x force: expected {expected_3x:.2f}x, actual {actual_3x:.2f}x (error: {error_3x:.1f}%)")
        
        if error_2x < 10 and error_3x < 10:
            self.logger.info("  ✅ Power scales linearly with force")
        else:
            self.logger.info("  ⚠️  Non-linear relationship detected")
        
        self.logger.info(f"\n{'='*70}\n")
    
    def save_results(self, base_filename: str = None):
        """Save calibration results"""
        if not base_filename:
            base_filename = f"thermal_cal_{self.side}_{int(time.time())}"
        
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
            'base_force': self.test_results[0].force_pct,
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
    parser = argparse.ArgumentParser(description='Simple Thermal Power Calibration')
    parser.add_argument('--side', required=True, choices=['left', 'right'])
    parser.add_argument('--dev', default='/dev/ttyUSB0')
    parser.add_argument('--base-force', type=float, default=15.0,
                       help='Base force level (default: 15%%)')
    parser.add_argument('--temp-rise', type=float, default=5.0,
                       help='Temperature rise target in °C (default: 5)')
    parser.add_argument('--cooldown', type=float, default=60.0,
                       help='Cooldown time between tests in seconds (default: 60)')
    parser.add_argument('--output', default=None)
    
    args = parser.parse_args()
    
    cal = SimplePowerCalibration(side=args.side, device=args.dev)
    cal.run_calibration(base_force=args.base_force, 
                       temp_rise=args.temp_rise,
                       cooldown_time=args.cooldown)
    cal.save_results(base_filename=args.output)


if __name__ == '__main__':
    main()
