"""
Overhead Characterization Test

Measures movement times for multiple distance ranges to separate:
- Fixed overhead (DDS latency, command processing, settling time)
- Distance-dependent movement time (actual gripper speed)

Tests ranges: 20-30%, 20-40%, 20-50%, 20-60%, 20-70%, 20-80%
"""

import time
import logging
import argparse
from dex1_hand_interface import Dex1HandInterface


class OverheadCharacterizationTest:
    """Characterize system overhead vs actual gripper movement speed"""
    
    def __init__(self, side: str):
        """
        Initialize overhead characterization test
        
        Args:
            side: 'left' or 'right'
        """
        self.side = side
        self.logger = logging.getLogger(f"overhead_test_{side}")
        
        # Create hand interface
        self.hand = Dex1HandInterface(side=side, rate_hz=200.0)
        
        self.logger.info(f"Overhead characterization test ready: {side} side")
    
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
        required_stable_readings = 5
        
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
        self.hand.set_position(start_pct)
        
        # Wait for position to stabilize
        if not self.wait_for_stable_position(start_pct, timeout=10.0):
            print(f"WARNING: Failed to reach {start_pct:.0f}% within timeout")
        
        time.sleep(0.5)  # Extra settling time
        
        # Command to end position and start timer
        start_time = time.time()
        self.hand.set_position(end_pct)
        
        # Wait for movement to complete
        if not self.wait_for_stable_position(end_pct, timeout=10.0):
            print(f"WARNING: Failed to reach {end_pct:.0f}% within timeout")
        
        end_time = time.time()
        
        movement_time = end_time - start_time
        
        return movement_time
    
    def run_characterization(self, trials_per_range: int = 3):
        """
        Run overhead characterization test
        
        Args:
            trials_per_range: Number of trials per distance range
        """
        print("=" * 70)
        print("OVERHEAD CHARACTERIZATION TEST")
        print("=" * 70)
        print(f"Side: {self.side}")
        print(f"Trials per range: {trials_per_range}")
        print()
        
        # Define test ranges (all starting from 20%)
        ranges = [
            (20, 30, 10),   # 10% distance
            (20, 40, 20),   # 20% distance
            (20, 50, 30),   # 30% distance
            (20, 60, 40),   # 40% distance
            (20, 70, 50),   # 50% distance
            (20, 80, 60),   # 60% distance
        ]
        
        results = []
        
        for start, end, distance in ranges:
            print(f"\n{'=' * 70}")
            print(f"TESTING RANGE: {start}% -> {end}% (distance: {distance}%)")
            print(f"{'=' * 70}")
            
            times = []
            
            for trial in range(trials_per_range):
                print(f"\nTrial {trial + 1}/{trials_per_range}:")
                print(f"  Commanding {start}% -> {end}%...")
                
                movement_time = self.measure_movement_time(start, end)
                times.append(movement_time)
                
                print(f"  Time: {movement_time:.3f}s")
                
                time.sleep(0.5)  # Pause between trials
            
            avg_time = sum(times) / len(times)
            results.append({
                'start': start,
                'end': end,
                'distance': distance,
                'times': times,
                'avg_time': avg_time
            })
            
            print(f"\nAverage time for {distance}% distance: {avg_time:.3f}s")
        
        # Analyze results
        print("\n" + "=" * 70)
        print("ANALYSIS")
        print("=" * 70)
        
        print("\nDistance vs Time:")
        print(f"{'Distance (%)':<15} {'Avg Time (s)':<15} {'Time/Distance (s/%)':<20}")
        print("-" * 50)
        
        for r in results:
            time_per_pct = r['avg_time'] / r['distance'] if r['distance'] > 0 else 0
            print(f"{r['distance']:<15} {r['avg_time']:<15.3f} {time_per_pct:<20.4f}")
        
        # Linear regression to find overhead and speed
        # time = overhead + distance * (1 / speed)
        # Using least squares fit
        
        distances = [r['distance'] for r in results]
        times = [r['avg_time'] for r in results]
        
        n = len(distances)
        sum_x = sum(distances)
        sum_y = sum(times)
        sum_xy = sum(d * t for d, t in zip(distances, times))
        sum_xx = sum(d * d for d in distances)
        
        # Slope = 1/speed (seconds per %)
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)
        
        # Intercept = overhead (seconds)
        intercept = (sum_y - slope * sum_x) / n
        
        # Calculate actual movement speed
        movement_speed = 1.0 / slope if slope > 0 else 0
        
        print("\n" + "=" * 70)
        print("OVERHEAD CHARACTERIZATION RESULTS")
        print("=" * 70)
        
        print(f"\nFixed overhead: {intercept:.3f} seconds")
        print(f"Movement speed: {movement_speed:.2f} %/sec")
        print(f"Time per %: {slope:.4f} seconds/%")
        
        print("\n" + "=" * 70)
        print("PREDICTIVE MODEL PARAMETERS")
        print("=" * 70)
        print(f"fixed_overhead_sec = {intercept:.3f}")
        print(f"movement_speed_pct_per_sec = {movement_speed:.2f}")
        print(f"at_200hz_position_change_per_update = {movement_speed * 0.005:.3f}")
        print("=" * 70)
        
        # Verify fit quality
        print("\nFit Quality:")
        print(f"{'Distance (%)':<15} {'Measured (s)':<15} {'Predicted (s)':<15} {'Error (s)':<15}")
        print("-" * 60)
        
        for r in results:
            predicted = intercept + slope * r['distance']
            error = r['avg_time'] - predicted
            print(f"{r['distance']:<15} {r['avg_time']:<15.3f} {predicted:<15.3f} {error:<15.3f}")
        
        # Return to 50%
        print("\nReturning to 50%...")
        self.hand.set_position(50.0)
        time.sleep(2.0)
        
        self.hand.shutdown()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Overhead Characterization Test")
    parser.add_argument("--side", required=True, choices=["left", "right"],
                       help="Gripper side (left/right)")
    parser.add_argument("--trials", type=int, default=3,
                       help="Number of trials per range (default: 3)")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run characterization
    test = OverheadCharacterizationTest(side=args.side)
    test.run_characterization(trials_per_range=args.trials)


if __name__ == "__main__":
    main()
