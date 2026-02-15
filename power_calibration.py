#!/usr/bin/env python3
"""
Power Calibration Test

Measure ACTUAL power consumption vs grasping force by observing rate of change
in current draw across position sweeps.

Approach:
- 3 grasping force points (low, medium, high)
- Each: hold at 0% (full grasp) and measure actual current over 5-degree equivalent time
- Measure rate of change in actual current draw
- Establish real power-to-force correlation

This gives us REAL data, not calculated estimates.

Usage:
    python3 power_calibration.py --side left
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
class PowerCalibrationPoint:
    """Single measurement during calibration"""
    timestamp: float
    grasping_force_pct: float
    position_pct: float
    
    # Actual measurements from servo
    present_current_ma: float  # This is what we care about
    voltage_v: float
    temperature_c: float
    
    # Derived
    actual_power_w: float  # voltage × present_current
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ForceCalibrationResult:
    """Calibration result for one force level"""
    grasping_force_pct: float
    
    # Statistics over measurement period
    avg_current_ma: float
    std_current_ma: float
    avg_power_w: float
    std_power_w: float
    avg_voltage_v: float
    avg_temp_c: float
    
    # Measurement quality
    sample_count: int
    duration_sec: float
    stable: bool  # Low variance = stable measurement
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PowerCalibration:
    """Calibrate actual power consumption vs grasping force"""
    
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
        
        self.gripper = create_gripper(self.connection, f'power_cal_{side}', [1])
        
        # Load calibration
        self._load_calibration()
        
        # Data collection
        self.measurement_points: List[PowerCalibrationPoint] = []
        self.calibration_results: List[ForceCalibrationResult] = []
        
        self.logger.info("✅ Power Calibration Ready")
    
    def _load_calibration(self):
        """Load calibration offset from device config file"""
        config_file = '/tmp/ezgripper_device_config.json'
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                
                # Get serial number from hardware
                import serial.tools.list_ports
                ports = serial.tools.list_ports.comports()
                serial_number = None
                for port in ports:
                    if port.device == self.device:
                        serial_number = port.serial_number
                        break
                
                if serial_number and 'calibration' in config and serial_number in config['calibration']:
                    calibration_offset = config['calibration'][serial_number]
                    self.gripper.zero_positions[0] = calibration_offset
                    self.logger.info(f"✅ Loaded calibration for {serial_number}: offset={calibration_offset}")
                else:
                    self.logger.warning("⚠️  No calibration found - run calibration first")
            else:
                self.logger.warning("⚠️  No device config file found - run calibration first")
        except Exception as e:
            self.logger.error(f"Failed to load calibration: {e}")
    
    def read_sensors(self) -> Dict[str, Any]:
        """Read sensor data"""
        data = self.gripper.bulk_read_sensor_data()
        
        # Read voltage
        try:
            voltage_raw = self.gripper.servos[0].read_address(144, 2)
            voltage = voltage_raw[0] + (voltage_raw[1] << 8)
            data['voltage'] = voltage * 0.1
        except:
            data['voltage'] = 12.0
        
        return data
    
    def calibrate_force_level(self, grasping_force_pct: float, 
                             hold_time_sec: float = 30.0) -> ForceCalibrationResult:
        """
        Calibrate one grasping force level
        
        Method:
        1. Close to 0% (tip-to-tip contact)
        2. Hold with grasping_force for hold_time_sec
        3. Measure actual current draw continuously
        4. Calculate statistics
        
        The actual current draw tells us REAL power consumption at this force level.
        """
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Calibrating Grasping Force: {grasping_force_pct}%")
        self.logger.info(f"Hold time: {hold_time_sec}s")
        self.logger.info(f"{'='*70}")
        
        # Move to 30% starting position
        self.logger.info("Moving to start position (30%)...")
        for i in range(90):  # 3 seconds
            self.gripper.goto_position(30.0, 30.0)
            if i % 30 == 0:
                sensors = self.read_sensors()
                self.logger.info(f"  Position: {sensors['position']:.1f}%")
            time.sleep(1.0 / 30.0)
        
        time.sleep(0.5)
        
        # Close to 0% (contact)
        self.logger.info("Closing to 0% (contact)...")
        contact_start = time.time()
        while time.time() - contact_start < 3.0:
            sensors = self.read_sensors()
            self.gripper.goto_position(0.0, grasping_force_pct)
            
            if sensors['position'] < 3.0:
                self.logger.info(f"  Contact at {sensors['position']:.1f}%")
                break
            
            time.sleep(1.0 / 30.0)
        
        # Hold and measure actual current
        self.logger.info(f"\nHolding at 0% with {grasping_force_pct}% force for {hold_time_sec}s...")
        self.logger.info("Measuring ACTUAL current draw...")
        
        hold_start = time.time()
        current_samples = []
        power_samples = []
        voltage_samples = []
        temp_samples = []
        
        sample_count = 0
        
        while time.time() - hold_start < hold_time_sec:
            sensors = self.read_sensors()
            self.gripper.goto_position(0.0, grasping_force_pct)
            
            # Record ACTUAL current (Present Current)
            present_current = abs(sensors.get('current', 0))
            voltage = sensors.get('voltage', 12.0)
            actual_power = (voltage * present_current) / 1000.0
            
            current_samples.append(present_current)
            power_samples.append(actual_power)
            voltage_samples.append(voltage)
            temp_samples.append(sensors['temperature'])
            
            # Record point
            point = PowerCalibrationPoint(
                timestamp=time.time(),
                grasping_force_pct=grasping_force_pct,
                position_pct=sensors['position'],
                present_current_ma=present_current,
                voltage_v=voltage,
                temperature_c=sensors['temperature'],
                actual_power_w=actual_power
            )
            self.measurement_points.append(point)
            
            # Log every 2 seconds
            elapsed = time.time() - hold_start
            if int(elapsed * 5) % 10 == 0:
                avg_current = np.mean(current_samples[-60:]) if len(current_samples) >= 60 else np.mean(current_samples)
                avg_power = np.mean(power_samples[-60:]) if len(power_samples) >= 60 else np.mean(power_samples)
                self.logger.info(f"  {elapsed:5.1f}s | Current: {present_current:6.1f}mA (avg: {avg_current:6.1f}mA) | "
                               f"Power: {actual_power:5.2f}W (avg: {avg_power:5.2f}W) | "
                               f"Temp: {sensors['temperature']:4.1f}°C")
            
            sample_count += 1
            time.sleep(1.0 / 30.0)
        
        # Calculate statistics
        avg_current = np.mean(current_samples)
        std_current = np.std(current_samples)
        avg_power = np.mean(power_samples)
        std_power = np.std(power_samples)
        avg_voltage = np.mean(voltage_samples)
        avg_temp = np.mean(temp_samples)
        
        # Check stability (coefficient of variation < 10%)
        cv_current = (std_current / avg_current) * 100 if avg_current > 0 else 100
        stable = cv_current < 10.0
        
        result = ForceCalibrationResult(
            grasping_force_pct=grasping_force_pct,
            avg_current_ma=avg_current,
            std_current_ma=std_current,
            avg_power_w=avg_power,
            std_power_w=std_power,
            avg_voltage_v=avg_voltage,
            avg_temp_c=avg_temp,
            sample_count=sample_count,
            duration_sec=hold_time_sec,
            stable=stable
        )
        
        self.calibration_results.append(result)
        
        # Log results
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Calibration Result: {grasping_force_pct}% Force")
        self.logger.info(f"  Actual Current: {avg_current:.1f} ± {std_current:.1f} mA (CV: {cv_current:.1f}%)")
        self.logger.info(f"  Actual Power:   {avg_power:.2f} ± {std_power:.2f} W")
        self.logger.info(f"  Voltage:        {avg_voltage:.2f} V")
        self.logger.info(f"  Temperature:    {avg_temp:.1f} °C")
        self.logger.info(f"  Samples:        {sample_count}")
        self.logger.info(f"  Stable:         {'✅ YES' if stable else '⚠️  NO (high variance)'}")
        self.logger.info(f"{'='*70}\n")
        
        # Return to 30%
        self.logger.info("Returning to 30%...")
        for _ in range(30):
            self.gripper.goto_position(30.0, 30.0)
            time.sleep(1.0 / 30.0)
        
        return result
    
    def run_calibration(self, force_levels: List[float] = None, 
                       hold_time_sec: float = 30.0,
                       rest_time_sec: float = 10.0):
        """
        Run full power calibration
        
        Default: 3 force levels (10%, 25%, 40%)
        Each held for 30 seconds to get stable measurements
        """
        if force_levels is None:
            force_levels = [10, 25, 40]
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Power Calibration Suite")
        self.logger.info(f"{'='*70}")
        self.logger.info(f"Force levels: {force_levels}")
        self.logger.info(f"Hold time per level: {hold_time_sec}s")
        self.logger.info(f"Rest time between: {rest_time_sec}s")
        self.logger.info(f"Total time: ~{len(force_levels) * (hold_time_sec + rest_time_sec + 10) / 60:.1f} minutes")
        self.logger.info(f"{'='*70}\n")
        
        for i, force in enumerate(force_levels):
            self.logger.info(f"\n>>> Calibration {i+1}/{len(force_levels)} <<<")
            
            result = self.calibrate_force_level(force, hold_time_sec)
            
            # Rest between tests
            if i < len(force_levels) - 1:
                self.logger.info(f"Resting {rest_time_sec}s before next test...")
                time.sleep(rest_time_sec)
        
        # Analyze results
        self.analyze_calibration()
    
    def analyze_calibration(self):
        """Analyze calibration results and establish power-to-force correlation"""
        if len(self.calibration_results) < 2:
            self.logger.warning("Need at least 2 calibration points for analysis")
            return
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Calibration Analysis")
        self.logger.info(f"{'='*70}\n")
        
        # Extract data
        forces = [r.grasping_force_pct for r in self.calibration_results]
        currents = [r.avg_current_ma for r in self.calibration_results]
        powers = [r.avg_power_w for r in self.calibration_results]
        
        # Fit linear model: Power = a * Force + b
        force_array = np.array(forces)
        power_array = np.array(powers)
        
        # Linear regression
        coeffs = np.polyfit(force_array, power_array, 1)
        slope = coeffs[0]
        intercept = coeffs[1]
        
        # Calculate R²
        power_pred = slope * force_array + intercept
        ss_res = np.sum((power_array - power_pred) ** 2)
        ss_tot = np.sum((power_array - np.mean(power_array)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        self.logger.info("Power-to-Force Correlation:")
        self.logger.info(f"  Model: Power(W) = {slope:.4f} × Force(%) + {intercept:.4f}")
        self.logger.info(f"  R² = {r_squared:.4f}")
        self.logger.info("")
        
        # Show measured vs predicted
        self.logger.info("Measured vs Predicted:")
        self.logger.info(f"  {'Force':<8} {'Measured':<12} {'Predicted':<12} {'Error':<10}")
        self.logger.info(f"  {'-'*8} {'-'*12} {'-'*12} {'-'*10}")
        for i, force in enumerate(forces):
            measured = powers[i]
            predicted = slope * force + intercept
            error = abs(measured - predicted)
            self.logger.info(f"  {force:6.1f}%  {measured:10.2f}W  {predicted:10.2f}W  {error:8.2f}W")
        
        self.logger.info("")
        self.logger.info("Current Draw:")
        for i, force in enumerate(forces):
            self.logger.info(f"  {force:6.1f}% force → {currents[i]:6.1f}mA avg")
        
        self.logger.info(f"\n{'='*70}\n")
        
        # Save calibration model
        calibration_model = {
            'slope': slope,
            'intercept': intercept,
            'r_squared': r_squared,
            'force_levels': forces,
            'measured_powers': powers,
            'measured_currents': currents
        }
        
        return calibration_model
    
    def save_results(self, base_filename: str = None):
        """Save calibration results"""
        if not base_filename:
            base_filename = f"power_cal_{self.side}_{int(time.time())}"
        
        # Save measurement points
        points_file = f"{base_filename}_points.csv"
        with open(points_file, 'w', newline='') as f:
            if self.measurement_points:
                writer = csv.DictWriter(f, fieldnames=self.measurement_points[0].to_dict().keys())
                writer.writeheader()
                for point in self.measurement_points:
                    writer.writerow(point.to_dict())
        
        self.logger.info(f"💾 Saved {len(self.measurement_points)} measurement points to {points_file}")
        
        # Save calibration results
        results_file = f"{base_filename}_results.csv"
        with open(results_file, 'w', newline='') as f:
            if self.calibration_results:
                writer = csv.DictWriter(f, fieldnames=self.calibration_results[0].to_dict().keys())
                writer.writeheader()
                for result in self.calibration_results:
                    writer.writerow(result.to_dict())
        
        self.logger.info(f"💾 Saved {len(self.calibration_results)} calibration results to {results_file}")
        
        # Save calibration model
        if len(self.calibration_results) >= 2:
            model = self.analyze_calibration()
            model_file = f"{base_filename}_model.json"
            with open(model_file, 'w') as f:
                json.dump(model, f, indent=2)
            self.logger.info(f"💾 Saved calibration model to {model_file}")


def main():
    parser = argparse.ArgumentParser(description='Power Calibration')
    parser.add_argument('--side', required=True, choices=['left', 'right'])
    parser.add_argument('--dev', default='/dev/ttyUSB0')
    parser.add_argument('--forces', nargs='+', type=float, default=[10, 25, 40],
                       help='Force levels to calibrate (default: 10 25 40)')
    parser.add_argument('--hold', type=float, default=30.0,
                       help='Hold time per force level in seconds (default: 30)')
    parser.add_argument('--rest', type=float, default=10.0,
                       help='Rest time between tests (default: 10)')
    parser.add_argument('--output', default=None)
    
    args = parser.parse_args()
    
    cal = PowerCalibration(side=args.side, device=args.dev)
    cal.run_calibration(force_levels=args.forces, 
                       hold_time_sec=args.hold,
                       rest_time_sec=args.rest)
    cal.save_results(base_filename=args.output)


if __name__ == '__main__':
    main()
