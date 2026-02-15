#!/usr/bin/env python3
"""
Force Characterization Test Suite

Systematic mapping of moving_force vs grasping_force vs power consumption.
Uses 20° position sweeps without objects to characterize force-power relationship.

Key Design:
- Mode 5: Goal Current is the control signal (Present Current unreliable)
- 20° sweep (100% → 80%) provides consistent load profile
- Temperature delta measurement (not absolute)
- No object needed - characterizes gripper itself

Test Matrix: 5 moving forces × 4 grasping forces = 20 tests
- Moving: 15%, 25%, 35%, 50%, 70%
- Grasping: 10%, 20%, 30%, 40%

Usage:
    python3 characterization_suite.py --side left
    python3 characterization_suite.py --side right --dev /dev/ttyUSB1
"""

import argparse
import time
import json
import csv
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import sys

from libezgripper import create_connection, create_gripper
from libezgripper.grasp_manager import GraspManager


@dataclass
class CharacterizationPoint:
    """Single measurement point during test"""
    timestamp: float
    test_id: int
    moving_force_pct: float
    grasping_force_pct: float
    phase: str  # 'moving', 'grasping', 'idle'
    
    # Position
    position_pct: float
    position_units: int
    
    # Control signals (what we command)
    goal_current_units: int  # The actual control signal in Mode 5
    goal_current_ma: float   # Converted to mA
    
    # Sensor readings
    present_current_ma: float  # May be unreliable in Mode 5
    voltage_v: float
    temperature_c: float
    
    # Derived
    power_estimate_w: float  # voltage × goal_current
    temp_delta_c: float      # Change from test start
    
    # State
    grasp_state: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TestResult:
    """Summary of one complete test"""
    test_id: int
    moving_force_pct: float
    grasping_force_pct: float
    
    # Timing
    time_to_position_sec: float
    hold_duration_sec: float
    
    # Power consumption by phase
    moving_avg_power_w: float
    moving_peak_power_w: float
    grasping_avg_power_w: float
    grasping_peak_power_w: float
    
    # Thermal
    start_temp_c: float
    peak_temp_c: float
    temp_rise_c: float
    
    # Stability
    position_stable: bool
    position_drift_pct: float
    
    # Success
    completed: bool
    thermal_warning: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ForceCharacterizationSuite:
    """Systematic force characterization testing"""
    
    def __init__(self, side: str, device: str = "/dev/ttyUSB0"):
        self.side = side
        self.device = device
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize hardware
        self.logger.info(f"Connecting to {side} gripper on {device}...")
        self.connection = create_connection(dev_name=device, baudrate=1000000)
        time.sleep(2.0)
        
        self.gripper = create_gripper(self.connection, f'char_test_{side}', [1])
        
        # Get hardware parameters
        self.hardware_current_limit = self.gripper.config._config.get('servo', {}).get(
            'dynamixel_settings', {}).get('current_limit', 1120)
        self.current_unit_to_ma = 3.36  # MX-64 conversion factor
        
        # Data collection
        self.measurement_points: List[CharacterizationPoint] = []
        self.test_results: List[TestResult] = []
        
        self.logger.info("✅ Characterization Suite Ready")
        self.logger.info(f"   Hardware Current Limit: {self.hardware_current_limit} units "
                        f"({self.hardware_current_limit * self.current_unit_to_ma:.0f}mA)")
    
    def update_force_config(self, moving_force_pct: float, grasping_force_pct: float):
        """Update force configuration"""
        config = self.gripper.config._config
        config['servo']['force_management']['moving_force_pct'] = moving_force_pct
        config['servo']['force_management']['grasping_force_pct'] = grasping_force_pct
        
        # Reinitialize grasp manager
        self.grasp_manager = GraspManager(self.gripper.config)
    
    def read_sensor_data(self) -> Dict[str, Any]:
        """Read all sensor data"""
        data = self.gripper.bulk_read_sensor_data()
        
        # Add voltage reading (register 144)
        try:
            voltage_raw = self.gripper.servos[0].read_address(144, 2)
            voltage = voltage_raw[0] + (voltage_raw[1] << 8)
            data['voltage'] = voltage * 0.1  # Convert to volts
        except:
            data['voltage'] = 12.0  # Default
        
        return data
    
    def calculate_goal_current(self, force_pct: float) -> tuple:
        """Calculate Goal Current from force percentage"""
        goal_current_units = int((force_pct / 100.0) * self.hardware_current_limit)
        goal_current_ma = goal_current_units * self.current_unit_to_ma
        return goal_current_units, goal_current_ma
    
    def run_single_test(self, test_id: int, moving_force_pct: float, 
                       grasping_force_pct: float) -> TestResult:
        """
        Run single characterization test
        
        Sequence:
        1. Open to 100% (starting position)
        2. Close to 80% with moving_force (20° sweep)
        3. Hold at 80% with grasping_force for 10s
        4. Return to 100%
        """
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Test {test_id}: Moving={moving_force_pct}%, Grasping={grasping_force_pct}%")
        self.logger.info(f"{'='*70}")
        
        # Update configuration
        self.update_force_config(moving_force_pct, grasping_force_pct)
        
        # Calculate Goal Current values
        moving_goal_units, moving_goal_ma = self.calculate_goal_current(moving_force_pct)
        grasping_goal_units, grasping_goal_ma = self.calculate_goal_current(grasping_force_pct)
        
        self.logger.info(f"Moving Goal Current: {moving_goal_units} units ({moving_goal_ma:.0f}mA)")
        self.logger.info(f"Grasping Goal Current: {grasping_goal_units} units ({grasping_goal_ma:.0f}mA)")
        
        # Phase 0: Move to starting position (100%)
        self.logger.info("\nPhase 0: Moving to start position (100%)...")
        for _ in range(60):  # 2 seconds at 30Hz
            self.gripper.goto_position(100.0, 30.0)
            time.sleep(1.0 / 30.0)
        
        # Wait for position to stabilize
        time.sleep(1.0)
        
        # Record initial state
        initial_data = self.read_sensor_data()
        start_temp = initial_data['temperature']
        start_time = time.time()
        
        self.logger.info(f"Start: Pos={initial_data['position']:.1f}%, Temp={start_temp:.1f}°C")
        
        # Phase 1: Close to 80% (20° sweep) with moving_force
        self.logger.info(f"\nPhase 1: Closing to 80% (moving_force={moving_force_pct}%)...")
        
        phase1_start = time.time()
        phase1_power_samples = []
        target_reached = False
        
        while time.time() - phase1_start < 5.0:  # Max 5 seconds
            data = self.read_sensor_data()
            data['commanded_position'] = 80.0
            
            # Process through grasp manager
            goal_position, goal_effort = self.grasp_manager.process_cycle(
                sensor_data=data,
                hardware_current_limit_ma=self.hardware_current_limit * self.current_unit_to_ma
            )
            
            # Execute command
            self.gripper.goto_position(goal_position, goal_effort)
            
            # Calculate actual goal current being sent
            actual_goal_units, actual_goal_ma = self.calculate_goal_current(goal_effort)
            
            # Record measurement point
            point = CharacterizationPoint(
                timestamp=time.time(),
                test_id=test_id,
                moving_force_pct=moving_force_pct,
                grasping_force_pct=grasping_force_pct,
                phase='moving',
                position_pct=data['position'],
                position_units=int(data['position'] * 25),  # Approximate
                goal_current_units=actual_goal_units,
                goal_current_ma=actual_goal_ma,
                present_current_ma=abs(data.get('current', 0)),
                voltage_v=data.get('voltage', 12.0),
                temperature_c=data['temperature'],
                power_estimate_w=(data.get('voltage', 12.0) * actual_goal_ma) / 1000.0,
                temp_delta_c=data['temperature'] - start_temp,
                grasp_state=self.grasp_manager.state.value
            )
            self.measurement_points.append(point)
            phase1_power_samples.append(point.power_estimate_w)
            
            # Check if reached target
            if abs(data['position'] - 80.0) < 2.0:
                target_reached = True
                break
            
            time.sleep(1.0 / 30.0)
        
        phase1_duration = time.time() - phase1_start
        
        if not target_reached:
            self.logger.warning("⚠️  Did not reach 80% position")
        
        # Phase 2: Hold at 80% with grasping_force for 10s
        self.logger.info(f"\nPhase 2: Holding at 80% (grasping_force={grasping_force_pct}%) for 10s...")
        
        phase2_start = time.time()
        phase2_power_samples = []
        hold_duration = 10.0
        initial_hold_position = self.read_sensor_data()['position']
        max_drift = 0.0
        
        while time.time() - phase2_start < hold_duration:
            data = self.read_sensor_data()
            data['commanded_position'] = 80.0
            
            # Process through grasp manager
            goal_position, goal_effort = self.grasp_manager.process_cycle(
                sensor_data=data,
                hardware_current_limit_ma=self.hardware_current_limit * self.current_unit_to_ma
            )
            
            # Execute command
            self.gripper.goto_position(goal_position, goal_effort)
            
            # Calculate actual goal current
            actual_goal_units, actual_goal_ma = self.calculate_goal_current(goal_effort)
            
            # Record measurement point
            point = CharacterizationPoint(
                timestamp=time.time(),
                test_id=test_id,
                moving_force_pct=moving_force_pct,
                grasping_force_pct=grasping_force_pct,
                phase='grasping',
                position_pct=data['position'],
                position_units=int(data['position'] * 25),
                goal_current_units=actual_goal_units,
                goal_current_ma=actual_goal_ma,
                present_current_ma=abs(data.get('current', 0)),
                voltage_v=data.get('voltage', 12.0),
                temperature_c=data['temperature'],
                power_estimate_w=(data.get('voltage', 12.0) * actual_goal_ma) / 1000.0,
                temp_delta_c=data['temperature'] - start_temp,
                grasp_state=self.grasp_manager.state.value
            )
            self.measurement_points.append(point)
            phase2_power_samples.append(point.power_estimate_w)
            
            # Track drift
            drift = abs(data['position'] - initial_hold_position)
            max_drift = max(max_drift, drift)
            
            # Log every second
            elapsed = time.time() - phase2_start
            if int(elapsed * 10) % 10 == 0:
                self.logger.info(f"   Hold: {elapsed:.1f}s | Pos: {data['position']:5.1f}% | "
                               f"Temp: {data['temperature']:4.1f}°C | "
                               f"Power: {point.power_estimate_w:.2f}W")
            
            time.sleep(1.0 / 30.0)
        
        # Phase 3: Return to 100%
        self.logger.info("\nPhase 3: Returning to 100%...")
        for _ in range(60):
            self.gripper.goto_position(100.0, 30.0)
            time.sleep(1.0 / 30.0)
        
        # Compile results
        final_data = self.read_sensor_data()
        peak_temp = max(p.temperature_c for p in self.measurement_points 
                       if p.test_id == test_id)
        
        result = TestResult(
            test_id=test_id,
            moving_force_pct=moving_force_pct,
            grasping_force_pct=grasping_force_pct,
            time_to_position_sec=phase1_duration,
            hold_duration_sec=hold_duration,
            moving_avg_power_w=sum(phase1_power_samples) / len(phase1_power_samples) if phase1_power_samples else 0.0,
            moving_peak_power_w=max(phase1_power_samples) if phase1_power_samples else 0.0,
            grasping_avg_power_w=sum(phase2_power_samples) / len(phase2_power_samples) if phase2_power_samples else 0.0,
            grasping_peak_power_w=max(phase2_power_samples) if phase2_power_samples else 0.0,
            start_temp_c=start_temp,
            peak_temp_c=peak_temp,
            temp_rise_c=peak_temp - start_temp,
            position_stable=max_drift < 2.0,
            position_drift_pct=max_drift,
            completed=target_reached,
            thermal_warning=peak_temp > 60.0
        )
        
        self.test_results.append(result)
        
        # Log summary
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Test {test_id} Summary:")
        self.logger.info(f"  Moving Power: {result.moving_avg_power_w:.2f}W avg, {result.moving_peak_power_w:.2f}W peak")
        self.logger.info(f"  Grasping Power: {result.grasping_avg_power_w:.2f}W avg, {result.grasping_peak_power_w:.2f}W peak")
        self.logger.info(f"  Temperature Rise: {result.temp_rise_c:.1f}°C (start: {result.start_temp_c:.1f}°C, peak: {result.peak_temp_c:.1f}°C)")
        self.logger.info(f"  Position Drift: {result.position_drift_pct:.2f}%")
        self.logger.info(f"  Thermal Warning: {'⚠️  YES' if result.thermal_warning else '✅ NO'}")
        self.logger.info(f"{'='*70}\n")
        
        return result
    
    def run_full_suite(self, rest_time_sec: float = 5.0):
        """
        Run complete test matrix
        
        5 moving forces × 4 grasping forces = 20 tests
        """
        # Define test matrix
        moving_forces = [15, 25, 35, 50, 70]
        grasping_forces = [10, 20, 30, 40]
        
        total_tests = len(moving_forces) * len(grasping_forces)
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Starting Full Characterization Suite")
        self.logger.info(f"{'='*70}")
        self.logger.info(f"Moving Forces: {moving_forces}")
        self.logger.info(f"Grasping Forces: {grasping_forces}")
        self.logger.info(f"Total Tests: {total_tests}")
        self.logger.info(f"Rest Time: {rest_time_sec}s between tests")
        self.logger.info(f"Estimated Duration: {(total_tests * 20 + (total_tests - 1) * rest_time_sec) / 60:.1f} minutes")
        self.logger.info(f"{'='*70}\n")
        
        test_id = 1
        
        for moving_force in moving_forces:
            for grasping_force in grasping_forces:
                self.logger.info(f"\n>>> Test {test_id}/{total_tests} <<<")
                
                result = self.run_single_test(test_id, moving_force, grasping_force)
                
                # Check for thermal issues
                if result.thermal_warning:
                    extended_rest = rest_time_sec * 2
                    self.logger.warning(f"⚠️  Thermal warning - extending rest to {extended_rest}s")
                    time.sleep(extended_rest)
                else:
                    time.sleep(rest_time_sec)
                
                test_id += 1
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"✅ Full Suite Complete - {total_tests} tests")
        self.logger.info(f"{'='*70}\n")
    
    def save_results(self, base_filename: str = None):
        """Save results to CSV files"""
        if not base_filename:
            base_filename = f"force_char_{self.side}_{int(time.time())}"
        
        # Save detailed measurement points
        points_file = f"{base_filename}_points.csv"
        with open(points_file, 'w', newline='') as f:
            if self.measurement_points:
                writer = csv.DictWriter(f, fieldnames=self.measurement_points[0].to_dict().keys())
                writer.writeheader()
                for point in self.measurement_points:
                    writer.writerow(point.to_dict())
        
        self.logger.info(f"💾 Saved {len(self.measurement_points)} measurement points to {points_file}")
        
        # Save test summaries
        summary_file = f"{base_filename}_summary.csv"
        with open(summary_file, 'w', newline='') as f:
            if self.test_results:
                writer = csv.DictWriter(f, fieldnames=self.test_results[0].to_dict().keys())
                writer.writeheader()
                for result in self.test_results:
                    writer.writerow(result.to_dict())
        
        self.logger.info(f"💾 Saved {len(self.test_results)} test summaries to {summary_file}")
        
        # Save metadata
        metadata_file = f"{base_filename}_metadata.json"
        metadata = {
            'side': self.side,
            'device': self.device,
            'timestamp': time.time(),
            'hardware_current_limit': self.hardware_current_limit,
            'current_unit_to_ma': self.current_unit_to_ma,
            'test_count': len(self.test_results),
            'measurement_count': len(self.measurement_points)
        }
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.logger.info(f"💾 Saved metadata to {metadata_file}")
    
    def print_summary(self):
        """Print summary analysis"""
        if not self.test_results:
            self.logger.info("No test results available")
            return
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Characterization Summary")
        self.logger.info(f"{'='*70}")
        
        # Find optimal configurations
        results_sorted_by_power = sorted(self.test_results, 
                                        key=lambda r: r.grasping_avg_power_w)
        results_sorted_by_temp = sorted(self.test_results, 
                                       key=lambda r: r.temp_rise_c)
        
        self.logger.info("\nLowest Power Consumption (Grasping):")
        for i, r in enumerate(results_sorted_by_power[:3]):
            self.logger.info(f"  {i+1}. Moving={r.moving_force_pct}%, Grasping={r.grasping_force_pct}% "
                           f"→ {r.grasping_avg_power_w:.2f}W avg")
        
        self.logger.info("\nLowest Temperature Rise:")
        for i, r in enumerate(results_sorted_by_temp[:3]):
            self.logger.info(f"  {i+1}. Moving={r.moving_force_pct}%, Grasping={r.grasping_force_pct}% "
                           f"→ +{r.temp_rise_c:.1f}°C")
        
        self.logger.info("\nHighest Power (for maximum force):")
        for i, r in enumerate(reversed(results_sorted_by_power[-3:])):
            self.logger.info(f"  {i+1}. Moving={r.moving_force_pct}%, Grasping={r.grasping_force_pct}% "
                           f"→ {r.grasping_avg_power_w:.2f}W avg")
        
        # Stability analysis
        stable_count = sum(1 for r in self.test_results if r.position_stable)
        self.logger.info(f"\nPosition Stability: {stable_count}/{len(self.test_results)} tests stable")
        
        # Thermal analysis
        thermal_warnings = sum(1 for r in self.test_results if r.thermal_warning)
        self.logger.info(f"Thermal Warnings: {thermal_warnings}/{len(self.test_results)} tests")
        
        self.logger.info(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description='Force Characterization Test Suite')
    parser.add_argument('--side', required=True, choices=['left', 'right'],
                       help='Gripper side')
    parser.add_argument('--dev', default='/dev/ttyUSB0',
                       help='Serial device (default: /dev/ttyUSB0)')
    parser.add_argument('--rest', type=float, default=5.0,
                       help='Rest time between tests in seconds (default: 5.0)')
    parser.add_argument('--output', default=None,
                       help='Base filename for output (default: auto-generated)')
    
    args = parser.parse_args()
    
    # Create suite
    suite = ForceCharacterizationSuite(side=args.side, device=args.dev)
    
    # Run full test matrix
    suite.run_full_suite(rest_time_sec=args.rest)
    
    # Print summary
    suite.print_summary()
    
    # Save results
    suite.save_results(base_filename=args.output)


if __name__ == '__main__':
    main()
