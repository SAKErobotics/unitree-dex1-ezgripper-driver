#!/usr/bin/env python3
"""
Isolated Force Characterization Tests

Three separate tests to isolate each phase:
1. MOVING: Full open (100%) ↔ 10% cycles - pure moving power
2. CONTACT: 30% → 0% → 30% rapid cycles - contact/closure power (tip-to-tip)
3. GRASPING: 30% → grasp → hold - pure grasping/holding power

Each test isolates one phase so power consumption can be accurately measured.

Usage:
    python3 isolated_force_characterization.py --side left
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
class MeasurementPoint:
    """Single measurement point"""
    timestamp: float
    test_type: str  # 'moving', 'contact', 'grasping'
    test_id: int
    cycle: int
    
    # Force settings
    moving_force_pct: float
    grasping_force_pct: float
    
    # Position
    position_pct: float
    target_position_pct: float
    
    # Control signal (Mode 5)
    goal_current_units: int
    goal_current_ma: float
    commanded_force_pct: float
    
    # Sensors
    present_current_ma: float  # May be unreliable
    voltage_v: float
    temperature_c: float
    
    # Derived
    power_w: float  # voltage × goal_current
    temp_delta_c: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TestSummary:
    """Summary of one test"""
    test_type: str
    test_id: int
    moving_force_pct: float
    grasping_force_pct: float
    
    # Cycles
    cycles_completed: int
    total_duration_sec: float
    
    # Power
    avg_power_w: float
    peak_power_w: float
    min_power_w: float
    
    # Thermal
    start_temp_c: float
    end_temp_c: float
    temp_rise_c: float
    peak_temp_c: float
    
    # Success
    completed: bool
    thermal_warning: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IsolatedForceCharacterization:
    """Isolated phase testing for accurate power measurement"""
    
    def __init__(self, side: str, device: str = "/dev/ttyUSB0"):
        self.side = side
        self.device = device
        
        # Setup logging with unbuffered output
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            force=True
        )
        self.logger = logging.getLogger(__name__)
        
        # Print to stdout immediately (unbuffered)
        print(f"Connecting to {side} gripper on {device}...", flush=True)
        
        # Initialize hardware
        self.logger.info(f"Connecting to {side} gripper on {device}...")
        self.connection = create_connection(dev_name=device, baudrate=1000000)
        time.sleep(2.0)
        
        self.gripper = create_gripper(self.connection, f'isolated_test_{side}', [1])
        
        # Load calibration from device config
        self._load_calibration()
        
        # Hardware parameters
        self.hardware_current_limit = self.gripper.config._config.get('servo', {}).get(
            'dynamixel_settings', {}).get('current_limit', 1120)
        self.current_unit_to_ma = 3.36
        
        # Data collection
        self.measurement_points: List[MeasurementPoint] = []
        self.test_summaries: List[TestSummary] = []
        
        # Read initial position
        initial_data = self.gripper.bulk_read_sensor_data()
        self.logger.info(f"Current position: {initial_data['position']:.1f}%")
        self.logger.info(f"Current temperature: {initial_data['temperature']:.1f}°C")
        self.logger.info("✅ Isolated Characterization Ready")
    
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
                    self.logger.warning("⚠️  No calibration found - positions may be incorrect")
            else:
                self.logger.warning("⚠️  No device config file found - run calibration first")
        except Exception as e:
            self.logger.error(f"Failed to load calibration: {e}")
    
    def calculate_goal_current(self, force_pct: float) -> tuple:
        """Calculate Goal Current from force percentage"""
        goal_current_units = int((force_pct / 100.0) * self.hardware_current_limit)
        goal_current_ma = goal_current_units * self.current_unit_to_ma
        return goal_current_units, goal_current_ma
    
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
    
    def thermal_backoff(self, current_temp: float):
        """
        Thermal management: pause if temp >= 70°C, wait until < 60°C
        
        This creates a thermal oscillation which is acceptable for testing.
        Independent of test timing - purely temperature-driven.
        """
        if current_temp >= 70.0:
            self.logger.warning(f"\n⚠️  THERMAL BACKOFF: {current_temp:.1f}°C >= 70°C")
            self.logger.warning(f"   Pausing until temperature drops below 60°C...")
            
            # Move to safe position (30%) to reduce load
            for _ in range(30):
                self.gripper.goto_position(30.0, 10.0)  # Low force
                time.sleep(1.0 / 30.0)
            
            # Wait for cooldown
            backoff_start = time.time()
            while True:
                sensors = self.read_sensors()
                temp = sensors['temperature']
                
                # Log every 5 seconds
                elapsed = time.time() - backoff_start
                if int(elapsed) % 5 == 0:
                    self.logger.info(f"   Cooling: {temp:.1f}°C (target: <60°C, elapsed: {elapsed:.0f}s)")
                
                if temp < 60.0:
                    self.logger.info(f"✅ Temperature dropped to {temp:.1f}°C - resuming tests")
                    break
                
                time.sleep(1.0)
            
            return True
        
        return False
    
    def record_point(self, test_type: str, test_id: int, cycle: int,
                    moving_force: float, grasping_force: float,
                    position: float, target: float, commanded_force: float,
                    sensors: Dict, start_temp: float) -> MeasurementPoint:
        """Record a measurement point"""
        goal_units, goal_ma = self.calculate_goal_current(commanded_force)
        
        # Diagnostic: Log first few points to verify recording
        if len(self.measurement_points) < 3:
            self.logger.info(f"📊 Recording point #{len(self.measurement_points)}: "
                           f"type={test_type}, pos={position:.1f}%, force={commanded_force:.0f}%")
        
        point = MeasurementPoint(
            timestamp=time.time(),
            test_type=test_type,
            test_id=test_id,
            cycle=cycle,
            moving_force_pct=moving_force,
            grasping_force_pct=grasping_force,
            position_pct=position,
            target_position_pct=target,
            goal_current_units=goal_units,
            goal_current_ma=goal_ma,
            commanded_force_pct=commanded_force,
            present_current_ma=abs(sensors.get('current', 0)),
            voltage_v=sensors.get('voltage', 12.0),
            temperature_c=sensors['temperature'],
            power_w=(sensors.get('voltage', 12.0) * goal_ma) / 1000.0,
            temp_delta_c=sensors['temperature'] - start_temp
        )
        
        self.measurement_points.append(point)
        return point
    
    def test_moving_power(self, test_id: int, moving_force_pct: float, 
                         cycles: int = 10) -> TestSummary:
        """
        Test 1: MOVING power isolation
        
        80% ↔ 60% cycles
        Pure moving power, no contact/grasping
        """
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Test {test_id}: MOVING Power (force={moving_force_pct}%)")
        self.logger.info(f"  Cycles: {cycles} × (80% → 60% → 80%)")
        self.logger.info(f"{'='*70}")
        
        # Start at 80%
        self.logger.info("Moving to start position (80%)...")
        start_move_time = time.time()
        position_reached = False
        
        for i in range(180):  # Max 6 seconds at 30Hz
            self.gripper.goto_position(80.0, 30.0)
            
            # Check position every 30 iterations (1 second)
            if i % 30 == 0:
                sensors = self.read_sensors()
                self.logger.info(f"  Moving: {sensors['position']:.1f}% (target: 80.0%)")
                if abs(sensors['position'] - 80.0) < 2.0:
                    position_reached = True
                    break
            
            time.sleep(1.0 / 30.0)
        
        if not position_reached:
            self.logger.warning("⚠️  Did not reach 80% start position")
        else:
            self.logger.info(f"✅ Reached 80% in {time.time() - start_move_time:.1f}s")
        
        time.sleep(0.5)
        
        # Record start temp
        start_data = self.read_sensors()
        start_temp = start_data['temperature']
        start_time = time.time()
        
        self.logger.info(f"Start: Temp={start_temp:.1f}°C")
        
        power_samples = []
        temp_samples = [start_temp]
        
        # Run cycles
        for cycle in range(cycles):
            self.logger.info(f"\nCycle {cycle + 1}/{cycles}")
            
            # Close to 60%
            self.logger.info("  Closing to 60%...")
            target = 60.0
            while True:
                sensors = self.read_sensors()
                self.gripper.goto_position(target, moving_force_pct)
                
                point = self.record_point('moving', test_id, cycle, 
                                        moving_force_pct, 0.0,
                                        sensors['position'], target, moving_force_pct,
                                        sensors, start_temp)
                power_samples.append(point.power_w)
                temp_samples.append(point.temperature_c)
                
                if abs(sensors['position'] - target) < 2.0:
                    break
                
                time.sleep(1.0 / 30.0)
            
            # Open to 80%
            self.logger.info("  Opening to 80%...")
            target = 80.0
            while True:
                sensors = self.read_sensors()
                self.gripper.goto_position(target, moving_force_pct)
                
                point = self.record_point('moving', test_id, cycle,
                                        moving_force_pct, 0.0,
                                        sensors['position'], target, moving_force_pct,
                                        sensors, start_temp)
                power_samples.append(point.power_w)
                temp_samples.append(point.temperature_c)
                
                if abs(sensors['position'] - target) < 2.0:
                    break
                
                time.sleep(1.0 / 30.0)
            
            # Log cycle stats
            cycle_power = sum(power_samples[-60:]) / min(60, len(power_samples))
            self.logger.info(f"  Cycle power: {cycle_power:.2f}W avg, Temp: {temp_samples[-1]:.1f}°C")
            
            # Check for thermal backoff
            self.thermal_backoff(temp_samples[-1])
        
        # Compile summary
        end_time = time.time()
        final_data = self.read_sensors()
        
        summary = TestSummary(
            test_type='moving',
            test_id=test_id,
            moving_force_pct=moving_force_pct,
            grasping_force_pct=0.0,
            cycles_completed=cycles,
            total_duration_sec=end_time - start_time,
            avg_power_w=sum(power_samples) / len(power_samples) if power_samples else 0.0,
            peak_power_w=max(power_samples) if power_samples else 0.0,
            min_power_w=min(power_samples) if power_samples else 0.0,
            start_temp_c=start_temp,
            end_temp_c=final_data['temperature'],
            temp_rise_c=final_data['temperature'] - start_temp,
            peak_temp_c=max(temp_samples),
            completed=True,
            thermal_warning=max(temp_samples) > 60.0
        )
        
        self.test_summaries.append(summary)
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"MOVING Test Summary:")
        self.logger.info(f"  Power: {summary.avg_power_w:.2f}W avg, {summary.peak_power_w:.2f}W peak")
        self.logger.info(f"  Temp Rise: +{summary.temp_rise_c:.1f}°C")
        self.logger.info(f"{'='*70}\n")
        
        return summary
    
    def test_contact_power(self, test_id: int, moving_force_pct: float,
                          cycles: int = 10) -> TestSummary:
        """
        Test 2: CONTACT power isolation
        
        30% → 0% → 30% rapid cycles (no hold)
        Tip-to-tip contact, immediate return
        Isolates contact/closure power (high current event)
        """
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Test {test_id}: CONTACT Power (force={moving_force_pct}%)")
        self.logger.info(f"  Cycles: {cycles} × (30% → 0% → 30%)")
        self.logger.info(f"  No hold time - immediate return")
        self.logger.info(f"{'='*70}")
        
        # Start at 30%
        self.logger.info("Moving to start position (30%)...")
        start_move_time = time.time()
        position_reached = False
        
        for i in range(180):  # Max 6 seconds at 30Hz
            self.gripper.goto_position(30.0, 30.0)
            
            # Check position every 30 iterations (1 second)
            if i % 30 == 0:
                sensors = self.read_sensors()
                self.logger.info(f"  Moving: {sensors['position']:.1f}% (target: 30.0%)")
                if abs(sensors['position'] - 30.0) < 2.0:
                    position_reached = True
                    break
            
            time.sleep(1.0 / 30.0)
        
        if not position_reached:
            self.logger.warning("⚠️  Did not reach 30% start position")
        else:
            self.logger.info(f"✅ Reached 30% in {time.time() - start_move_time:.1f}s")
        
        time.sleep(0.5)
        
        # Record start temp
        start_data = self.read_sensors()
        start_temp = start_data['temperature']
        start_time = time.time()
        
        self.logger.info(f"Start: Temp={start_temp:.1f}°C")
        
        power_samples = []
        temp_samples = [start_temp]
        
        # Run cycles
        for cycle in range(cycles):
            self.logger.info(f"\nCycle {cycle + 1}/{cycles}")
            
            # Close to 0% (tip-to-tip contact)
            self.logger.info("  Closing to 0%...")
            target = 0.0
            contact_start = time.time()
            while time.time() - contact_start < 3.0:  # Max 3 seconds
                sensors = self.read_sensors()
                self.gripper.goto_position(target, moving_force_pct)
                
                point = self.record_point('contact', test_id, cycle,
                                        moving_force_pct, 0.0,
                                        sensors['position'], target, moving_force_pct,
                                        sensors, start_temp)
                power_samples.append(point.power_w)
                temp_samples.append(point.temperature_c)
                
                # Break when position stable at ~0-3%
                if sensors['position'] < 3.0:
                    break
                
                time.sleep(1.0 / 30.0)
            
            # Immediate return to 30% (no hold)
            self.logger.info("  Returning to 30%...")
            target = 30.0
            while True:
                sensors = self.read_sensors()
                self.gripper.goto_position(target, moving_force_pct)
                
                point = self.record_point('contact', test_id, cycle,
                                        moving_force_pct, 0.0,
                                        sensors['position'], target, moving_force_pct,
                                        sensors, start_temp)
                power_samples.append(point.power_w)
                temp_samples.append(point.temperature_c)
                
                if abs(sensors['position'] - target) < 2.0:
                    break
                
                time.sleep(1.0 / 30.0)
            
            # Log cycle stats
            cycle_power = sum(power_samples[-60:]) / min(60, len(power_samples))
            self.logger.info(f"  Cycle power: {cycle_power:.2f}W avg, Temp: {temp_samples[-1]:.1f}°C")
            
            # Check for thermal backoff
            self.thermal_backoff(temp_samples[-1])
        
        # Compile summary
        end_time = time.time()
        final_data = self.read_sensors()
        
        summary = TestSummary(
            test_type='contact',
            test_id=test_id,
            moving_force_pct=moving_force_pct,
            grasping_force_pct=0.0,
            cycles_completed=cycles,
            total_duration_sec=end_time - start_time,
            avg_power_w=sum(power_samples) / len(power_samples) if power_samples else 0.0,
            peak_power_w=max(power_samples) if power_samples else 0.0,
            min_power_w=min(power_samples) if power_samples else 0.0,
            start_temp_c=start_temp,
            end_temp_c=final_data['temperature'],
            temp_rise_c=final_data['temperature'] - start_temp,
            peak_temp_c=max(temp_samples),
            completed=True,
            thermal_warning=max(temp_samples) > 60.0
        )
        
        self.test_summaries.append(summary)
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"CONTACT Test Summary:")
        self.logger.info(f"  Power: {summary.avg_power_w:.2f}W avg, {summary.peak_power_w:.2f}W peak")
        self.logger.info(f"  Temp Rise: +{summary.temp_rise_c:.1f}°C")
        self.logger.info(f"{'='*70}\n")
        
        return summary
    
    def test_grasping_power(self, test_id: int, moving_force_pct: float,
                           grasping_force_pct: float, hold_time_sec: float = 10.0) -> TestSummary:
        """
        Test 3: GRASPING power isolation
        
        30% → 0% (contact) → hold with grasping force
        MUST close to 0% to trigger contact and enter grasping state
        Pure grasping/holding power during hold phase
        Moving power can be subtracted from Test 1 data
        """
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Test {test_id}: GRASPING Power")
        self.logger.info(f"  Moving: {moving_force_pct}%, Grasping: {grasping_force_pct}%")
        self.logger.info(f"  Hold time: {hold_time_sec}s")
        self.logger.info(f"{'='*70}")
        
        # Start at 30%
        self.logger.info("Moving to start position (30%)...")
        start_move_time = time.time()
        position_reached = False
        
        for i in range(180):  # Max 6 seconds at 30Hz
            self.gripper.goto_position(30.0, 30.0)
            
            # Check position every 30 iterations (1 second)
            if i % 30 == 0:
                sensors = self.read_sensors()
                self.logger.info(f"  Moving: {sensors['position']:.1f}% (target: 30.0%)")
                if abs(sensors['position'] - 30.0) < 2.0:
                    position_reached = True
                    break
            
            time.sleep(1.0 / 30.0)
        
        if not position_reached:
            self.logger.warning("⚠️  Did not reach 30% start position")
        else:
            self.logger.info(f"✅ Reached 30% in {time.time() - start_move_time:.1f}s")
        
        time.sleep(0.5)
        
        # Record start temp
        start_data = self.read_sensors()
        start_temp = start_data['temperature']
        start_time = time.time()
        
        self.logger.info(f"Start: Temp={start_temp:.1f}°C")
        
        power_samples = []
        temp_samples = [start_temp]
        
        # Phase 1: Close to 0% to trigger contact/grasping
        # Use moving force to get there
        self.logger.info("\nPhase 1: Closing to 0% to trigger contact...")
        target = 0.0
        contact_start = time.time()
        while time.time() - contact_start < 3.0:  # Max 3 seconds
            sensors = self.read_sensors()
            self.gripper.goto_position(target, moving_force_pct)
            
            point = self.record_point('grasping', test_id, 0,
                                    moving_force_pct, grasping_force_pct,
                                    sensors['position'], target, moving_force_pct,
                                    sensors, start_temp)
            power_samples.append(point.power_w)
            temp_samples.append(point.temperature_c)
            
            # Break when position stable at ~0-3%
            if sensors['position'] < 3.0:
                self.logger.info(f"  Contact at {sensors['position']:.1f}%")
                break
            
            time.sleep(1.0 / 30.0)
        
        # Phase 2: Hold at 0% with grasping force
        self.logger.info(f"\nPhase 2: Holding with grasping force ({grasping_force_pct}%) for {hold_time_sec}s...")
        
        hold_start = time.time()
        grasp_power_samples = []  # Separate samples for pure grasping
        
        while time.time() - hold_start < hold_time_sec:
            sensors = self.read_sensors()
            self.gripper.goto_position(target, grasping_force_pct)
            
            point = self.record_point('grasping', test_id, 0,
                                    moving_force_pct, grasping_force_pct,
                                    sensors['position'], target, grasping_force_pct,
                                    sensors, start_temp)
            power_samples.append(point.power_w)
            grasp_power_samples.append(point.power_w)
            temp_samples.append(point.temperature_c)
            
            # Log every second
            elapsed = time.time() - hold_start
            if int(elapsed * 10) % 10 == 0:
                self.logger.info(f"  Hold: {elapsed:.1f}s | Power: {point.power_w:.2f}W | Temp: {point.temperature_c:.1f}°C")
            
            # Check for thermal backoff (will pause hold if needed)
            if self.thermal_backoff(point.temperature_c):
                # Reset hold timer after thermal backoff
                hold_start = time.time()
            
            time.sleep(1.0 / 30.0)
        
        # Return to 30%
        self.logger.info("\nReturning to 30%...")
        for _ in range(30):
            self.gripper.goto_position(30.0, 30.0)
            time.sleep(1.0 / 30.0)
        
        # Compile summary
        end_time = time.time()
        final_data = self.read_sensors()
        
        summary = TestSummary(
            test_type='grasping',
            test_id=test_id,
            moving_force_pct=moving_force_pct,
            grasping_force_pct=grasping_force_pct,
            cycles_completed=1,
            total_duration_sec=end_time - start_time,
            avg_power_w=sum(grasp_power_samples) / len(grasp_power_samples) if grasp_power_samples else 0.0,
            peak_power_w=max(grasp_power_samples) if grasp_power_samples else 0.0,
            min_power_w=min(grasp_power_samples) if grasp_power_samples else 0.0,
            start_temp_c=start_temp,
            end_temp_c=final_data['temperature'],
            temp_rise_c=final_data['temperature'] - start_temp,
            peak_temp_c=max(temp_samples),
            completed=True,
            thermal_warning=max(temp_samples) > 60.0
        )
        
        self.test_summaries.append(summary)
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"GRASPING Test Summary:")
        self.logger.info(f"  Pure Grasp Power: {summary.avg_power_w:.2f}W avg, {summary.peak_power_w:.2f}W peak")
        self.logger.info(f"  Temp Rise: +{summary.temp_rise_c:.1f}°C")
        self.logger.info(f"{'='*70}\n")
        
        return summary
    
    def run_full_suite(self, rest_time_sec: float = 5.0):
        """
        Run complete isolated test suite
        
        For each force combination:
        1. Test moving power
        2. Test contact power
        3. Test grasping power
        """
        # Test matrix
        moving_forces = [15, 25, 35, 50, 70]
        grasping_forces = [10, 20, 30, 40]
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"Isolated Force Characterization Suite")
        self.logger.info(f"{'='*70}")
        self.logger.info(f"Moving Forces: {moving_forces}")
        self.logger.info(f"Grasping Forces: {grasping_forces}")
        self.logger.info(f"Tests per combination: 3 (moving, contact, grasping)")
        self.logger.info(f"Total tests: {len(moving_forces) + len(moving_forces) + len(moving_forces) * len(grasping_forces)}")
        self.logger.info(f"{'='*70}\n")
        
        test_id = 1
        
        # Test 1: Moving power for each moving force
        self.logger.info("\n" + "="*70)
        self.logger.info("PHASE 1: MOVING POWER TESTS")
        self.logger.info("="*70)
        
        for moving_force in moving_forces:
            self.test_moving_power(test_id, moving_force, cycles=10)
            test_id += 1
            time.sleep(rest_time_sec)
        
        # Test 2: Contact power for each moving force
        self.logger.info("\n" + "="*70)
        self.logger.info("PHASE 2: CONTACT POWER TESTS")
        self.logger.info("="*70)
        
        for moving_force in moving_forces:
            self.test_contact_power(test_id, moving_force, cycles=10)
            test_id += 1
            time.sleep(rest_time_sec)
        
        # Test 3: Grasping power for each combination
        self.logger.info("\n" + "="*70)
        self.logger.info("PHASE 3: GRASPING POWER TESTS")
        self.logger.info("="*70)
        
        for moving_force in moving_forces:
            for grasping_force in grasping_forces:
                self.test_grasping_power(test_id, moving_force, grasping_force, hold_time_sec=10.0)
                test_id += 1
                time.sleep(rest_time_sec)
        
        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"✅ Full Suite Complete")
        self.logger.info(f"{'='*70}\n")
    
    def save_results(self, base_filename: str = None):
        """Save results to CSV"""
        if not base_filename:
            base_filename = f"isolated_char_{self.side}_{int(time.time())}"
        
        # Save measurement points
        points_file = f"{base_filename}_points.csv"
        with open(points_file, 'w', newline='') as f:
            if self.measurement_points:
                writer = csv.DictWriter(f, fieldnames=self.measurement_points[0].to_dict().keys())
                writer.writeheader()
                for point in self.measurement_points:
                    writer.writerow(point.to_dict())
        
        self.logger.info(f"💾 Saved {len(self.measurement_points)} points to {points_file}")
        
        # Save summaries
        summary_file = f"{base_filename}_summary.csv"
        with open(summary_file, 'w', newline='') as f:
            if self.test_summaries:
                writer = csv.DictWriter(f, fieldnames=self.test_summaries[0].to_dict().keys())
                writer.writeheader()
                for summary in self.test_summaries:
                    writer.writerow(summary.to_dict())
        
        self.logger.info(f"💾 Saved {len(self.test_summaries)} summaries to {summary_file}")
        
        # Save metadata
        metadata_file = f"{base_filename}_metadata.json"
        metadata = {
            'side': self.side,
            'device': self.device,
            'timestamp': time.time(),
            'hardware_current_limit': self.hardware_current_limit,
            'test_count': len(self.test_summaries),
            'measurement_count': len(self.measurement_points)
        }
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.logger.info(f"💾 Saved metadata to {metadata_file}")


def main():
    parser = argparse.ArgumentParser(description='Isolated Force Characterization')
    parser.add_argument('--side', required=True, choices=['left', 'right'])
    parser.add_argument('--dev', default='/dev/ttyUSB0')
    parser.add_argument('--rest', type=float, default=5.0)
    parser.add_argument('--output', default=None)
    
    args = parser.parse_args()
    
    suite = IsolatedForceCharacterization(side=args.side, device=args.dev)
    suite.run_full_suite(rest_time_sec=args.rest)
    suite.save_results(base_filename=args.output)


if __name__ == '__main__':
    main()
