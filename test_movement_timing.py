"""
Gripper Movement Timing Test

Measures the actual time it takes for the gripper to move through its full range.
This data is used to calibrate the predictive position feedback model.

The test:
1. Commands gripper to 100% (full open)
2. Waits for movement to complete
3. Commands gripper to 0% (full close)
4. Measures time for full range movement
5. Repeats multiple times for accuracy
"""

import time
import logging
import argparse
from dex1_hand_interface import Dex1HandInterface


class MovementTimingTest:
    """Measure gripper movement timing for predictive model calibration"""
    
    def __init__(self, side: str):
        """
        Initialize timing test
        
        Args:
            side: 'left' or 'right'
        """
        self.side = side
        self.logger = logging.getLogger(f"timing_test_{side}")
        
        # Create hand interface
        self.hand = Dex1HandInterface(side=side, rate_hz=200.0)
        
        self.logger.info(f"Movement timing test ready: {side} side")
    
    def wait_for_stable_position(self, target_pct: float, tolerance: float = 5.0, timeout: float = 10.0) -> bool:
        """
        Wait for gripper to reach and stabilize at target position
        
        Args:
            target_pct: Target position percentage
            tolerance: Position tolerance (%)
            timeout: Maximum wait time (seconds)
        
        Returns:
            True if position reached, False if timeout
        """
        start_time = time.time()
        stable_count = 0
        required_stable_readings = 5  # Need 5 consecutive stable readings
        
        while time.time() - start_time < timeout:
            state = self.hand.get_state()
            
            if state:
                error = abs(state.position_pct - target_pct)
                
                if error < tolerance:
                    stable_count += 1
                    if stable_count >= required_stable_readings:
                        return True
                else:
                    stable_count = 0
            
            time.sleep(0.1)
        
        return False
    
    def measure_movement_time(self, start_pct: float, end_pct: float) -> float:
        """
        Measure time to move from start to end position
        
        Args:
            start_pct: Starting position percentage
            end_pct: Ending position percentage
        
        Returns:
            Movement time in seconds
        """
        # Command to start position
        print(f"\nCommanding to {start_pct:.0f}%...")
        self.hand.set_position(start_pct)
        
        # Wait for position to stabilize
        if not self.wait_for_stable_position(start_pct, timeout=10.0):
            print(f"WARNING: Failed to reach {start_pct:.0f}% within timeout")
        
        time.sleep(0.5)  # Extra settling time
        
        # Get initial state
        initial_state = self.hand.get_state()
        if initial_state:
            print(f"Starting position: {initial_state.position_pct:.1f}%")
        
        # Command to end position and start timer
        print(f"Commanding to {end_pct:.0f}%...")
        start_time = time.time()
        self.hand.set_position(end_pct)
        
        # Wait for movement to complete
        if not self.wait_for_stable_position(end_pct, timeout=10.0):
            print(f"WARNING: Failed to reach {end_pct:.0f}% within timeout")
        
        end_time = time.time()
        
        # Get final state
        final_state = self.hand.get_state()
        if final_state:
            print(f"Final position: {final_state.position_pct:.1f}%")
        
        movement_time = end_time - start_time
        print(f"Movement time: {movement_time:.2f}s")
        
        return movement_time
    
    def run_calibration(self, num_cycles: int = 3):
        """
        Run full calibration test
        
        Args:
            num_cycles: Number of open-close cycles to measure
        """
        print("=" * 60)
        print("GRIPPER MOVEMENT TIMING CALIBRATION")
        print("=" * 60)
        print(f"Side: {self.side}")
        print(f"Cycles: {num_cycles}")
        print()
        
        open_times = []
        close_times = []
        
        for cycle in range(num_cycles):
            print(f"\n{'=' * 60}")
            print(f"CYCLE {cycle + 1} of {num_cycles}")
            print(f"{'=' * 60}")
            
            # Measure close time (80% -> 20%)
            print("\n--- Measuring CLOSE time (80% -> 20%) ---")
            close_time = self.measure_movement_time(80.0, 20.0)
            close_times.append(close_time)
            
            time.sleep(1.0)  # Pause between movements
            
            # Measure open time (20% -> 80%)
            print("\n--- Measuring OPEN time (20% -> 80%) ---")
            open_time = self.measure_movement_time(20.0, 80.0)
            open_times.append(open_time)
            
            time.sleep(1.0)  # Pause between cycles
        
        # Calculate statistics
        print("\n" + "=" * 60)
        print("CALIBRATION RESULTS")
        print("=" * 60)
        
        avg_close = sum(close_times) / len(close_times)
        avg_open = sum(open_times) / len(open_times)
        avg_60pct_range = (avg_close + avg_open) / 2
        
        # Scale to full 100% range
        avg_full_range = avg_60pct_range * (100.0 / 60.0)
        movement_speed = 100.0 / avg_full_range
        
        print(f"\nClose times (80% -> 20%): {close_times}")
        print(f"Average close time: {avg_close:.2f}s")
        
        print(f"\nOpen times (20% -> 80%): {open_times}")
        print(f"Average open time: {avg_open:.2f}s")
        
        print(f"\nAverage 60% range time: {avg_60pct_range:.2f}s")
        print(f"Scaled to 100% range time: {avg_full_range:.2f}s")
        print(f"Estimated movement speed: {movement_speed:.1f} %/sec")
        
        print("\n" + "=" * 60)
        print("PREDICTIVE MODEL PARAMETERS")
        print("=" * 60)
        print(f"movement_speed_pct_per_sec = {movement_speed:.2f}")
        print(f"full_range_time_sec = {avg_full_range:.2f}")
        print(f"range_60pct_time_sec = {avg_60pct_range:.2f}")
        print(f"close_time_sec = {avg_close:.2f}")
        print(f"open_time_sec = {avg_open:.2f}")
        print("=" * 60)
        
        # Return to 50%
        print("\nReturning to 50%...")
        self.hand.set_position(50.0)
        time.sleep(2.0)
        
        self.hand.shutdown()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Gripper Movement Timing Calibration")
    parser.add_argument("--side", required=True, choices=["left", "right"],
                       help="Gripper side (left/right)")
    parser.add_argument("--cycles", type=int, default=3,
                       help="Number of test cycles (default: 3)")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run calibration
    test = MovementTimingTest(side=args.side)
    test.run_calibration(num_cycles=args.cycles)


if __name__ == "__main__":
    main()
