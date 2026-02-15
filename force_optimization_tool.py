#!/usr/bin/env python3
"""
Force Optimization Tool for EZGripper

Interactive testing tool for optimizing gripper forces with real-time monitoring.
Allows adjustment of force settings and timing parameters to achieve strong grasps
without overloading the servo.

Usage:
    python3 force_optimization_tool.py --side left
    python3 force_optimization_tool.py --side right --dev /dev/ttyUSB1
"""

import argparse
import time
import json
import logging
import sys
from dataclasses import dataclass
from typing import Optional, Dict, Any
import threading

from libezgripper import create_connection, create_gripper
from libezgripper.grasp_manager import GraspManager


@dataclass
class ForceProfile:
    """Force settings for testing"""
    moving_force_pct: float = 17.0
    grasping_force_pct: float = 10.0
    idle_force_pct: float = 10.0
    
    # Timing parameters
    contact_settle_time_ms: int = 0  # Time to wait in CONTACT state before GRASPING
    grasp_hold_time_sec: float = 5.0  # How long to hold grasp during test
    
    # Detection thresholds
    consecutive_samples: int = 3
    stall_tolerance_pct: float = 2.0


@dataclass
class TestResult:
    """Results from a single grasp test"""
    timestamp: float
    profile: ForceProfile
    
    # Performance metrics
    time_to_contact_sec: float
    max_current_ma: float
    avg_current_ma: float
    peak_temperature_c: float
    final_position_pct: float
    
    # Success indicators
    contact_detected: bool
    grasp_stable: bool
    thermal_warning: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export"""
        return {
            'timestamp': self.timestamp,
            'profile': {
                'moving_force': self.profile.moving_force_pct,
                'grasping_force': self.profile.grasping_force_pct,
                'idle_force': self.profile.idle_force_pct,
                'contact_settle_ms': self.profile.contact_settle_time_ms,
                'grasp_hold_sec': self.profile.grasp_hold_time_sec,
                'consecutive_samples': self.profile.consecutive_samples,
                'stall_tolerance': self.profile.stall_tolerance_pct
            },
            'metrics': {
                'time_to_contact': self.time_to_contact_sec,
                'max_current_ma': self.max_current_ma,
                'avg_current_ma': self.avg_current_ma,
                'peak_temperature': self.peak_temperature_c,
                'final_position': self.final_position_pct
            },
            'success': {
                'contact_detected': self.contact_detected,
                'grasp_stable': self.grasp_stable,
                'thermal_warning': self.thermal_warning
            }
        }


class ForceOptimizationTool:
    """Interactive tool for optimizing gripper force settings"""
    
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
        time.sleep(2.0)  # Wait for servo to settle
        
        self.gripper = create_gripper(self.connection, f'force_test_{side}', [1])
        
        # Current force profile
        self.current_profile = ForceProfile()
        
        # Test results history
        self.test_results = []
        
        # Monitoring state
        self.monitoring = False
        self.monitor_thread = None
        self.current_data = {}
        self.data_lock = threading.Lock()
        
        self.logger.info("✅ Force Optimization Tool Ready")
        self.logger.info(f"   Hardware: {self.gripper.servos[0].model_name if self.gripper.servos else 'Unknown'}")
        
    def update_force_profile(self, profile: ForceProfile):
        """Update the force profile in the gripper config"""
        self.current_profile = profile
        
        # Update config
        config = self.gripper.config._config
        config['servo']['force_management']['moving_force_pct'] = profile.moving_force_pct
        config['servo']['force_management']['grasping_force_pct'] = profile.grasping_force_pct
        config['servo']['force_management']['idle_force_pct'] = profile.idle_force_pct
        
        config['servo']['collision_detection']['consecutive_samples_required'] = profile.consecutive_samples
        config['servo']['collision_detection']['stall_tolerance_pct'] = profile.stall_tolerance_pct
        
        # Reinitialize grasp manager with new settings
        self.grasp_manager = GraspManager(self.gripper.config)
        
        self.logger.info(f"📝 Updated Force Profile:")
        self.logger.info(f"   Moving: {profile.moving_force_pct}%")
        self.logger.info(f"   Grasping: {profile.grasping_force_pct}%")
        self.logger.info(f"   Idle: {profile.idle_force_pct}%")
        self.logger.info(f"   Contact Settle: {profile.contact_settle_time_ms}ms")
        self.logger.info(f"   Grasp Hold: {profile.grasp_hold_time_sec}s")
        
    def start_monitoring(self):
        """Start background monitoring thread"""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("📊 Monitoring started")
        
    def stop_monitoring(self):
        """Stop background monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
        self.logger.info("📊 Monitoring stopped")
        
    def _monitor_loop(self):
        """Background monitoring loop at 10Hz"""
        while self.monitoring:
            try:
                sensor_data = self.gripper.bulk_read_sensor_data()
                
                with self.data_lock:
                    self.current_data = {
                        'position': sensor_data.get('position', 0.0),
                        'current': abs(sensor_data.get('current', 0)),
                        'temperature': sensor_data.get('temperature', 0),
                        'voltage': sensor_data.get('voltage', 0.0),
                        'error': sensor_data.get('error', 0),
                        'timestamp': time.time()
                    }
                
                time.sleep(0.1)  # 10Hz
                
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                time.sleep(0.5)
                
    def get_current_data(self) -> Dict[str, Any]:
        """Get latest sensor data (thread-safe)"""
        with self.data_lock:
            return self.current_data.copy()
            
    def run_grasp_test(self, target_position: float = 0.0) -> TestResult:
        """
        Run a single grasp test with current force profile
        
        Args:
            target_position: Target position to close to (0-100%)
            
        Returns:
            TestResult with performance metrics
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"🧪 Starting Grasp Test")
        self.logger.info(f"   Target Position: {target_position:.1f}%")
        self.logger.info(f"   Moving Force: {self.current_profile.moving_force_pct}%")
        self.logger.info(f"   Grasping Force: {self.current_profile.grasping_force_pct}%")
        self.logger.info(f"{'='*60}\n")
        
        # Start monitoring
        self.start_monitoring()
        
        # Initialize grasp manager
        self.grasp_manager = GraspManager(self.gripper.config)
        
        # Metrics tracking
        start_time = time.time()
        contact_time = None
        current_samples = []
        temp_samples = []
        
        # Get hardware current limit for percentage conversion
        hardware_current_limit = self.gripper.config._config.get('servo', {}).get('dynamixel_settings', {}).get('current_limit', 1120)
        max_current_ma = hardware_current_limit * 3.36  # Convert to mA
        
        try:
            # Phase 1: Close to target
            self.logger.info(f"Phase 1: Closing to {target_position:.1f}%...")
            
            cycle_count = 0
            contact_detected = False
            
            while True:
                # Get sensor data
                data = self.get_current_data()
                
                # Add commanded position
                data['commanded_position'] = target_position
                
                # Process through grasp manager
                goal_position, goal_effort = self.grasp_manager.process_cycle(
                    sensor_data=data,
                    hardware_current_limit_ma=max_current_ma
                )
                
                # Execute command
                self.gripper.goto_position(goal_position, goal_effort)
                
                # Track metrics
                current_samples.append(data['current'])
                temp_samples.append(data['temperature'])
                
                # Check state
                state_info = self.grasp_manager.get_state_info()
                current_state = self.grasp_manager.state.value
                
                # Log progress every 10 cycles (0.33 sec at 30Hz)
                if cycle_count % 10 == 0:
                    self.logger.info(f"   State: {current_state:8s} | Pos: {data['position']:5.1f}% | "
                                   f"Current: {data['current']:4.0f}mA | Temp: {data['temperature']:4.1f}°C")
                
                # Detect contact
                if current_state == 'grasping' and not contact_detected:
                    contact_detected = True
                    contact_time = time.time()
                    self.logger.info(f"\n✅ CONTACT DETECTED at {data['position']:.1f}% "
                                   f"(time: {contact_time - start_time:.2f}s)\n")
                    
                    # Apply contact settle time if configured
                    if self.current_profile.contact_settle_time_ms > 0:
                        settle_sec = self.current_profile.contact_settle_time_ms / 1000.0
                        self.logger.info(f"   Settling for {settle_sec:.3f}s...")
                        time.sleep(settle_sec)
                    
                    break
                
                # Timeout after 5 seconds
                if time.time() - start_time > 5.0:
                    self.logger.warning("⚠️  Timeout - no contact detected")
                    break
                
                cycle_count += 1
                time.sleep(1.0 / 30.0)  # 30Hz
            
            # Phase 2: Hold grasp
            if contact_detected:
                self.logger.info(f"Phase 2: Holding grasp for {self.current_profile.grasp_hold_time_sec}s...")
                
                hold_start = time.time()
                position_stable = True
                initial_position = self.get_current_data()['position']
                
                while time.time() - hold_start < self.current_profile.grasp_hold_time_sec:
                    # Get sensor data
                    data = self.get_current_data()
                    data['commanded_position'] = target_position
                    
                    # Process through grasp manager
                    goal_position, goal_effort = self.grasp_manager.process_cycle(
                        sensor_data=data,
                        hardware_current_limit_ma=max_current_ma
                    )
                    
                    # Execute command
                    self.gripper.goto_position(goal_position, goal_effort)
                    
                    # Track metrics
                    current_samples.append(data['current'])
                    temp_samples.append(data['temperature'])
                    
                    # Check for slip (position change > 3%)
                    if abs(data['position'] - initial_position) > 3.0:
                        position_stable = False
                        self.logger.warning(f"⚠️  Slip detected: {initial_position:.1f}% → {data['position']:.1f}%")
                    
                    # Log every second
                    elapsed = time.time() - hold_start
                    if int(elapsed * 10) % 10 == 0:  # Every second
                        self.logger.info(f"   Hold: {elapsed:.1f}s | Pos: {data['position']:5.1f}% | "
                                       f"Current: {data['current']:4.0f}mA | Temp: {data['temperature']:4.1f}°C")
                    
                    time.sleep(1.0 / 30.0)  # 30Hz
                
                self.logger.info("✅ Grasp hold complete")
            
            # Phase 3: Release
            self.logger.info("Phase 3: Releasing...")
            
            # Open to 50%
            for _ in range(30):  # 1 second at 30Hz
                data = self.get_current_data()
                data['commanded_position'] = 50.0
                
                goal_position, goal_effort = self.grasp_manager.process_cycle(
                    sensor_data=data,
                    hardware_current_limit_ma=max_current_ma
                )
                
                self.gripper.goto_position(goal_position, goal_effort)
                time.sleep(1.0 / 30.0)
            
            # Compile results
            final_data = self.get_current_data()
            
            result = TestResult(
                timestamp=time.time(),
                profile=self.current_profile,
                time_to_contact_sec=contact_time - start_time if contact_time else -1.0,
                max_current_ma=max(current_samples) if current_samples else 0.0,
                avg_current_ma=sum(current_samples) / len(current_samples) if current_samples else 0.0,
                peak_temperature_c=max(temp_samples) if temp_samples else 0.0,
                final_position_pct=final_data['position'],
                contact_detected=contact_detected,
                grasp_stable=position_stable if contact_detected else False,
                thermal_warning=max(temp_samples) > 60.0 if temp_samples else False
            )
            
            # Log summary
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"📊 Test Results Summary")
            self.logger.info(f"{'='*60}")
            self.logger.info(f"Contact Detected:    {'✅ YES' if result.contact_detected else '❌ NO'}")
            self.logger.info(f"Grasp Stable:        {'✅ YES' if result.grasp_stable else '❌ NO'}")
            self.logger.info(f"Time to Contact:     {result.time_to_contact_sec:.2f}s")
            self.logger.info(f"Max Current:         {result.max_current_ma:.0f}mA")
            self.logger.info(f"Avg Current:         {result.avg_current_ma:.0f}mA")
            self.logger.info(f"Peak Temperature:    {result.peak_temperature_c:.1f}°C")
            self.logger.info(f"Final Position:      {result.final_position_pct:.1f}%")
            self.logger.info(f"Thermal Warning:     {'⚠️  YES' if result.thermal_warning else '✅ NO'}")
            self.logger.info(f"{'='*60}\n")
            
            # Store result
            self.test_results.append(result)
            
            return result
            
        finally:
            self.stop_monitoring()
    
    def run_continuous_test(self, cycles: int = 10, rest_time_sec: float = 3.0):
        """
        Run continuous grasp/release cycles for endurance testing
        
        Args:
            cycles: Number of grasp/release cycles
            rest_time_sec: Rest time between cycles
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"🔄 Starting Continuous Test")
        self.logger.info(f"   Cycles: {cycles}")
        self.logger.info(f"   Rest Time: {rest_time_sec}s")
        self.logger.info(f"{'='*60}\n")
        
        for cycle in range(cycles):
            self.logger.info(f"\n--- Cycle {cycle + 1}/{cycles} ---")
            
            # Run grasp test
            result = self.run_grasp_test(target_position=0.0)
            
            # Check for thermal issues
            if result.thermal_warning:
                self.logger.warning(f"⚠️  Thermal warning detected - extending rest time")
                time.sleep(rest_time_sec * 2)
            else:
                time.sleep(rest_time_sec)
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"✅ Continuous Test Complete")
        self.logger.info(f"{'='*60}\n")
        
        # Summary statistics
        self._print_test_summary()
    
    def _print_test_summary(self):
        """Print summary of all test results"""
        if not self.test_results:
            self.logger.info("No test results available")
            return
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"📈 Test Summary ({len(self.test_results)} tests)")
        self.logger.info(f"{'='*60}")
        
        success_rate = sum(1 for r in self.test_results if r.contact_detected) / len(self.test_results) * 100
        stable_rate = sum(1 for r in self.test_results if r.grasp_stable) / len(self.test_results) * 100
        
        avg_contact_time = sum(r.time_to_contact_sec for r in self.test_results if r.time_to_contact_sec > 0) / \
                          max(1, sum(1 for r in self.test_results if r.time_to_contact_sec > 0))
        
        avg_max_current = sum(r.max_current_ma for r in self.test_results) / len(self.test_results)
        avg_peak_temp = sum(r.peak_temperature_c for r in self.test_results) / len(self.test_results)
        
        self.logger.info(f"Success Rate:        {success_rate:.1f}%")
        self.logger.info(f"Stability Rate:      {stable_rate:.1f}%")
        self.logger.info(f"Avg Contact Time:    {avg_contact_time:.2f}s")
        self.logger.info(f"Avg Max Current:     {avg_max_current:.0f}mA")
        self.logger.info(f"Avg Peak Temp:       {avg_peak_temp:.1f}°C")
        self.logger.info(f"{'='*60}\n")
    
    def save_results(self, filename: str = None):
        """Save test results to JSON file"""
        if not filename:
            filename = f"force_test_results_{self.side}_{int(time.time())}.json"
        
        data = {
            'side': self.side,
            'device': self.device,
            'timestamp': time.time(),
            'test_count': len(self.test_results),
            'results': [r.to_dict() for r in self.test_results]
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        self.logger.info(f"💾 Results saved to {filename}")
    
    def interactive_mode(self):
        """Interactive mode for manual testing"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"🎮 Interactive Force Optimization Mode")
        self.logger.info(f"{'='*60}\n")
        
        while True:
            print("\nOptions:")
            print("  1. Run single grasp test")
            print("  2. Run continuous test (10 cycles)")
            print("  3. Adjust force settings")
            print("  4. Adjust timing settings")
            print("  5. View current settings")
            print("  6. View test summary")
            print("  7. Save results")
            print("  8. Exit")
            
            choice = input("\nSelect option (1-8): ").strip()
            
            if choice == '1':
                self.run_grasp_test(target_position=0.0)
                
            elif choice == '2':
                cycles = input("Number of cycles [10]: ").strip()
                cycles = int(cycles) if cycles else 10
                rest = input("Rest time between cycles [3.0]: ").strip()
                rest = float(rest) if rest else 3.0
                self.run_continuous_test(cycles=cycles, rest_time_sec=rest)
                
            elif choice == '3':
                print("\nCurrent Force Settings:")
                print(f"  Moving Force: {self.current_profile.moving_force_pct}%")
                print(f"  Grasping Force: {self.current_profile.grasping_force_pct}%")
                print(f"  Idle Force: {self.current_profile.idle_force_pct}%")
                
                moving = input(f"Moving force % [{self.current_profile.moving_force_pct}]: ").strip()
                grasping = input(f"Grasping force % [{self.current_profile.grasping_force_pct}]: ").strip()
                idle = input(f"Idle force % [{self.current_profile.idle_force_pct}]: ").strip()
                
                profile = ForceProfile(
                    moving_force_pct=float(moving) if moving else self.current_profile.moving_force_pct,
                    grasping_force_pct=float(grasping) if grasping else self.current_profile.grasping_force_pct,
                    idle_force_pct=float(idle) if idle else self.current_profile.idle_force_pct,
                    contact_settle_time_ms=self.current_profile.contact_settle_time_ms,
                    grasp_hold_time_sec=self.current_profile.grasp_hold_time_sec,
                    consecutive_samples=self.current_profile.consecutive_samples,
                    stall_tolerance_pct=self.current_profile.stall_tolerance_pct
                )
                self.update_force_profile(profile)
                
            elif choice == '4':
                print("\nCurrent Timing Settings:")
                print(f"  Contact Settle Time: {self.current_profile.contact_settle_time_ms}ms")
                print(f"  Grasp Hold Time: {self.current_profile.grasp_hold_time_sec}s")
                print(f"  Consecutive Samples: {self.current_profile.consecutive_samples}")
                print(f"  Stall Tolerance: {self.current_profile.stall_tolerance_pct}%")
                
                settle = input(f"Contact settle time ms [{self.current_profile.contact_settle_time_ms}]: ").strip()
                hold = input(f"Grasp hold time sec [{self.current_profile.grasp_hold_time_sec}]: ").strip()
                samples = input(f"Consecutive samples [{self.current_profile.consecutive_samples}]: ").strip()
                tolerance = input(f"Stall tolerance % [{self.current_profile.stall_tolerance_pct}]: ").strip()
                
                profile = ForceProfile(
                    moving_force_pct=self.current_profile.moving_force_pct,
                    grasping_force_pct=self.current_profile.grasping_force_pct,
                    idle_force_pct=self.current_profile.idle_force_pct,
                    contact_settle_time_ms=int(settle) if settle else self.current_profile.contact_settle_time_ms,
                    grasp_hold_time_sec=float(hold) if hold else self.current_profile.grasp_hold_time_sec,
                    consecutive_samples=int(samples) if samples else self.current_profile.consecutive_samples,
                    stall_tolerance_pct=float(tolerance) if tolerance else self.current_profile.stall_tolerance_pct
                )
                self.update_force_profile(profile)
                
            elif choice == '5':
                print("\n" + "="*60)
                print("Current Settings")
                print("="*60)
                print(f"Moving Force:        {self.current_profile.moving_force_pct}%")
                print(f"Grasping Force:      {self.current_profile.grasping_force_pct}%")
                print(f"Idle Force:          {self.current_profile.idle_force_pct}%")
                print(f"Contact Settle:      {self.current_profile.contact_settle_time_ms}ms")
                print(f"Grasp Hold:          {self.current_profile.grasp_hold_time_sec}s")
                print(f"Consecutive Samples: {self.current_profile.consecutive_samples}")
                print(f"Stall Tolerance:     {self.current_profile.stall_tolerance_pct}%")
                print("="*60)
                
            elif choice == '6':
                self._print_test_summary()
                
            elif choice == '7':
                filename = input("Filename [auto]: ").strip()
                self.save_results(filename if filename else None)
                
            elif choice == '8':
                print("\nExiting...")
                break
                
            else:
                print("Invalid option")


def main():
    parser = argparse.ArgumentParser(description='Force Optimization Tool for EZGripper')
    parser.add_argument('--side', required=True, choices=['left', 'right'],
                       help='Gripper side')
    parser.add_argument('--dev', default='/dev/ttyUSB0',
                       help='Serial device (default: /dev/ttyUSB0)')
    parser.add_argument('--auto', action='store_true',
                       help='Run automated test sequence')
    parser.add_argument('--cycles', type=int, default=10,
                       help='Number of cycles for continuous test (default: 10)')
    
    args = parser.parse_args()
    
    # Create tool
    tool = ForceOptimizationTool(side=args.side, device=args.dev)
    
    if args.auto:
        # Automated test sequence
        tool.logger.info("Running automated test sequence...")
        tool.run_continuous_test(cycles=args.cycles)
        tool.save_results()
    else:
        # Interactive mode
        tool.interactive_mode()


if __name__ == '__main__':
    main()
