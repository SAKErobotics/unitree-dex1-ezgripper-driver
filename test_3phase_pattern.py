"""
3-Phase Gripper Test Pattern

Tests gripper through 3 distinct operational phases:
1. Smooth oscillation (sine wave)
2. Random jumps
3. Instant point-to-point jumps

Uses the unified Dex1HandInterface to command the gripper.
"""

import time
import random
import logging
import argparse
import math
from dex1_hand_interface import Dex1HandInterface


class ThreePhaseTest:
    """3-phase gripper test pattern"""
    
    PHASE_DURATION = 25.0  # Total cycle duration (seconds)
    
    def __init__(self, side: str, rate_hz: float = 200.0):
        """
        Initialize 3-phase test
        
        Args:
            side: 'left' or 'right'
            rate_hz: Command rate in Hz (default 200 Hz for G1 XR)
        """
        self.side = side
        self.rate_hz = rate_hz
        self.period = 1.0 / rate_hz
        
        self.logger = logging.getLogger(f"3phase_test_{side}")
        
        # Create hand interface
        self.hand = Dex1HandInterface(side=side, rate_hz=rate_hz)
        
        self.logger.info(f"3-phase test ready: {side} side at {rate_hz} Hz")
    
    def get_phase(self, elapsed: float) -> tuple[int, str]:
        """
        Determine current phase based on elapsed time
        
        Returns:
            (phase_number, phase_name)
        """
        t = elapsed % self.PHASE_DURATION
        
        if t < 5.0:
            return (0, "Calibration")
        elif t < 15.0:
            return (1, "Smooth oscillation")
        elif t < 20.0:
            return (2, "Random jumps")
        else:
            return (3, "Instant jumps")
    
    def calculate_position(self, elapsed: float) -> float:
        """
        Calculate target position based on current phase
        
        Returns:
            Position percentage (0-100)
        """
        t = elapsed % self.PHASE_DURATION
        phase, _ = self.get_phase(elapsed)
        
        if phase == 0:
            # Phase 0: Calibration - close gripper
            return 0.0
        
        elif phase == 1:
            # Phase 1: Smooth oscillation (sine wave)
            # 10 second period: 0% -> 100% -> 0%
            phase_time = t - 5.0
            normalized = (math.sin(2 * math.pi * phase_time / 10.0) + 1.0) / 2.0
            return normalized * 100.0
        
        elif phase == 2:
            # Phase 2: Random jumps every second
            phase_time = t - 15.0
            jump_index = int(phase_time)
            random.seed(jump_index + 1000)  # Consistent random sequence
            return random.uniform(0.0, 100.0)
        
        else:
            # Phase 3: Instant point-to-point jumps
            phase_time = t - 20.0
            jump_index = int(phase_time)
            random.seed(jump_index + 2000)  # Different random sequence
            return random.uniform(0.0, 100.0)
    
    def run(self):
        """Run continuous 3-phase test pattern"""
        self.logger.info("Starting 3-phase test pattern...")
        self.logger.info(f"Publishing commands at {self.rate_hz} Hz")
        
        start_time = time.time()
        last_phase = -1
        last_log_time = 0.0
        
        try:
            while True:
                loop_start = time.time()
                elapsed = loop_start - start_time
                
                # Get current phase
                phase, phase_name = self.get_phase(elapsed)
                
                # Log phase transitions
                if phase != last_phase:
                    phase_time = elapsed % self.PHASE_DURATION
                    self.logger.info(f"PHASE {phase}: {phase_name} ({phase_time:.1f}s)")
                    last_phase = phase
                
                # Calculate and send position command
                position_pct = self.calculate_position(elapsed)
                self.hand.set_position(position_pct)
                
                # Log every command for correlation with gripper movement
                print(f"[{elapsed:6.2f}s] Phase {phase}: Command {position_pct:5.1f}%", flush=True)
                
                # Also log phase info every 1 second
                if elapsed - last_log_time >= 1.0:
                    last_log_time = elapsed
                
                # Sleep to maintain rate
                loop_time = time.time() - loop_start
                sleep_time = max(0, self.period - loop_time)
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down 3-phase test...")
        finally:
            self.hand.shutdown()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="3-Phase Gripper Test Pattern")
    parser.add_argument("--side", required=True, choices=["left", "right"],
                       help="Gripper side (left/right)")
    parser.add_argument("--rate", type=float, default=200.0,
                       help="Command rate in Hz (default: 200)")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run test
    test = ThreePhaseTest(side=args.side, rate_hz=args.rate)
    test.run()


if __name__ == "__main__":
    main()
