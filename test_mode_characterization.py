"""
Mode Characterization Test

Characterizes position mode vs torque mode current load at closed position.
This helps understand the non-linear relationship between the two modes
and enables smooth handoff when transitioning from position to torque control.

Test procedure:
1. Close gripper to 0% (hard stop)
2. Test position mode at various effort levels (20-100%)
3. Test torque mode at various torque levels (20-75%)
4. Measure current load for each setting
5. Generate mapping table for smooth transitions
"""

import time
import logging
import argparse
import sys
import os

from libezgripper import create_connection, Gripper


class ModeCharacterization:
    """Characterize position mode vs torque mode for smooth handoff"""
    
    def __init__(self, device: str = "/dev/ttyUSB0"):
        """
        Initialize mode characterization test
        
        Args:
            device: Serial device path
        """
        self.device = device
        self.logger = logging.getLogger("mode_characterization")
        
        # Connect to gripper
        self.logger.info(f"Connecting to gripper on {device}")
        self.connection = create_connection(dev_name=device, baudrate=57600)
        self.gripper = Gripper(self.connection, 'test_gripper', [1])
        
        # Results storage
        self.position_mode_results = []
        self.torque_mode_results = []
        
        self.logger.info("Mode characterization ready")
    
    def calibrate_and_shift_zero(self):
        """
        Calibrate gripper normally, then shift zero point by 10%
        
        This makes the gripper think 'closed' (0%) is actually 10% open from true closed.
        When commanding 0-10%, the gripper will press against itself, creating resistance.
        """
        self.logger.info("Step 1: Calibrating gripper to find actual zero point...")
        
        # Calibrate normally - close to find true zero
        self.gripper.calibrate()
        actual_zero = self.gripper.zero_positions[0]
        self.logger.info(f"  Actual zero position: {actual_zero}")
        
        # Calculate shifted zero (10% of actual gripper range before actual zero)
        # GRIP_MAX represents the full gripper range in servo position units
        # This makes commanding 10-20% cause fingers to collide (press against themselves)
        shift_amount = int(self.gripper.GRIP_MAX * 0.10)  # 10% of full range = 250 servo units
        shifted_zero = actual_zero - shift_amount
        
        self.logger.info(f"Step 2: Shifting zero point by -10% ({shift_amount} units)")
        self.logger.info(f"  New zero position: {shifted_zero} (was {actual_zero})")
        self.logger.info(f"  This makes 0% = 10% before true zero (fingers not touching)")
        self.logger.info(f"  Commanding 10-20% will cause fingers to collide and press against themselves")
        
        # Apply shifted zero (software only - don't move gripper yet)
        self.gripper.zero_positions[0] = shifted_zero
        
        self.logger.info("Step 3: Releasing gripper for 10 seconds before starting tests...")
        self.logger.info("  (Disabling torque mode - springs will open gripper naturally)")
        self.logger.info("  (Each test will command 0%, which is 10% before true zero)")
        self.logger.info("  (Gripper will close to true zero and press against itself)")
        
        # Release gripper - disable torque mode, springs open gripper naturally
        servo = self.gripper.servos[0]
        servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control  # Disable torque mode - springs open gripper
        time.sleep(10.0)
        
        self.logger.info("✅ Calibration and shift complete - ready to begin characterization")
    
    def read_current_load(self) -> int:
        """
        Read current load from servo
        
        Returns:
            Current load value (0-2047, where 1024 = no load)
        """
        servo = self.gripper.servos[0]
        load = servo.read_word(126)  # Protocol 2.0: Present Current (was Load)  # Protocol 2.0: Register 126 = Present Load
        return load
    
    def read_actual_current(self) -> int:
        """
        Read actual motor current from servo
        
        MX-64 Protocol 2.0: Register 126 (Current)
        Formula: I = (4.5mA) * (CURRENT - 2048)
        - Idle state (no current): value = 2048
        - Positive current flow: value > 2048
        - Negative current flow: value < 2048
        
        Returns:
            Current in mA (signed value, positive = motor drawing current)
        """
        servo = self.gripper.servos[0]
        current_raw = servo.read_word(126)  # Protocol 2.0: Present Current
        
        # Convert using MX-64 formula: I = 4.5mA * (CURRENT - 2048)
        current_ma = int(4.5 * (current_raw - 2048))
        
        return current_ma
    
    def wait_for_position_stop(self, max_wait: float = 2.0, stable_threshold: int = 5) -> int:
        """
        Wait for gripper position to stop changing (indicating it has reached physical limit)
        
        Args:
            max_wait: Maximum time to wait in seconds
            stable_threshold: Position must not change by more than this many units to be considered stopped
            
        Returns:
            Final position when stopped
        """
        servo = self.gripper.servos[0]
        start_time = time.time()
        prev_position = servo.read_word_signed(36)
        
        while (time.time() - start_time) < max_wait:
            time.sleep(0.05)  # Check every 50ms
            current_position = servo.read_word_signed(36)
            
            # If position hasn't changed significantly, gripper has stopped
            if abs(current_position - prev_position) <= stable_threshold:
                return current_position
            
            prev_position = current_position
        
        # Timeout - return last position
        return prev_position
    
    def read_stable_current(self, num_stable: int = 5, tolerance_pct: float = 2.0, max_duration: float = 2.0, delay_between: float = 0.05) -> tuple[list[int], float]:
        """
        Read current continuously until N consecutive stable readings are found
        
        Args:
            num_stable: Number of consecutive stable readings required (default 5)
            tolerance_pct: Percentage tolerance for stability (default 2.0%)
            max_duration: Maximum time to wait in seconds (default 2.0s)
            delay_between: Delay between readings in seconds (default 0.05 = 50ms)
        
        Returns:
            (list of stable current readings in mA, average current in mA)
        """
        start_time = time.time()
        all_readings = []
        stable_readings = []
        
        while (time.time() - start_time) < max_duration:
            current = self.read_actual_current()
            all_readings.append(current)
            
            # Check if this reading is stable relative to previous readings
            if len(stable_readings) > 0:
                avg_so_far = sum(stable_readings) / len(stable_readings)
                tolerance = abs(avg_so_far * tolerance_pct / 100.0)
                
                if abs(current - avg_so_far) <= tolerance:
                    # Stable - add to stable list
                    stable_readings.append(current)
                else:
                    # Not stable - reset stable list
                    stable_readings = [current]
            else:
                # First reading
                stable_readings = [current]
            
            # Check if we have enough stable readings
            if len(stable_readings) >= num_stable:
                avg_current = sum(stable_readings) / len(stable_readings)
                return stable_readings, avg_current
            
            time.sleep(delay_between)
        
        # Timeout - return what we have
        if len(stable_readings) >= 3:
            avg_current = sum(stable_readings) / len(stable_readings)
            return stable_readings, avg_current
        else:
            # Not enough stable readings, return last N readings
            last_n = all_readings[-num_stable:] if len(all_readings) >= num_stable else all_readings
            avg_current = sum(last_n) / len(last_n) if last_n else 0
            return last_n, avg_current
    
    def read_error_state(self) -> tuple[int, str]:
        """
        Read servo error state
        
        Returns:
            (error_code, error_description)
        """
        servo = self.gripper.servos[0]
        error = servo.read_address(70,  # Protocol 2.0: Hardware Error Status 1)[0]  # Protocol 2.0: Register 70 = Error byte
        
        error_descriptions = []
        if error & 0x01:
            error_descriptions.append("Input Voltage Error")
        if error & 0x04:
            error_descriptions.append("Angle Limit Error")
        if error & 0x08:
            error_descriptions.append("Overheating Error")
        if error & 0x10:
            error_descriptions.append("Range Error")
        if error & 0x20:
            error_descriptions.append("Checksum Error")
        if error & 0x40:
            error_descriptions.append("Overload Error")
        if error & 0x80:
            error_descriptions.append("Instruction Error")
        
        if not error_descriptions:
            error_descriptions.append("No Error")
        
        return error, ", ".join(error_descriptions)
    
    def test_position_mode(self, effort_levels: list[int]):
        """
        Test position mode at various effort levels at 0% position (pressing against itself)
        
        Args:
            effort_levels: List of effort percentages to test (e.g., [20, 30, 40, ...])
        """
        self.logger.info("=" * 70)
        self.logger.info("POSITION MODE CHARACTERIZATION")
        self.logger.info("=" * 70)
        self.logger.info("Testing at 0% position (gripper tries to go 10% beyond true zero)")
        self.logger.info("Methodology: Command 0%, read stable current (max 2s), release 10s")
        
        servo = self.gripper.servos[0]
        # Command 0% which tries to close 10% beyond true zero (pressing against itself)
        close_position = self.gripper.scale(0, self.gripper.GRIP_MAX)
        release_position = self.gripper.scale(50, self.gripper.GRIP_MAX)
        
        for effort in effort_levels:
            self.logger.info(f"\nTesting position mode at {effort}% effort...")
            
            # Pre-position: Move to 8% open at 100% effort (gets gripper close to true zero without pressing)
            # With shifted zero, 8% is just before true zero (10%), so fingers won't press yet
            preposition = self.gripper.scale(8, self.gripper.GRIP_MAX)
            servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control  # Disable torque mode
            servo.write_word(38,  # Protocol 2.0: Current Limit 1023)    # 100% effort
            servo.write_word(116,  # Protocol 2.0: Goal Position preposition)
            time.sleep(1.0)  # Wait for gripper to reach pre-position
            
            # Now apply test effort and command 0% position
            torque_limit = self.gripper.scale(effort, self.gripper.TORQUE_MAX)
            servo.write_word(38,  # Protocol 2.0: Current Limit torque_limit)
            
            # Command 0% position (tries to close 10% beyond true zero - presses against itself)
            servo.write_word(116,  # Protocol 2.0: Goal Position close_position)
            
            # Wait for gripper position to stop changing (reached physical limit)
            final_position = self.wait_for_position_stop(max_wait=2.0, stable_threshold=5)
            self.logger.info(f"  Gripper stopped at position: {final_position}")
            
            # Wait 0.5s for force to stabilize
            time.sleep(0.5)
            
            # Do 5 quick current reads
            current_readings = []
            for i in range(5):
                current = self.read_actual_current()
                current_readings.append(current)
                if i < 4:
                    time.sleep(0.05)  # 50ms between reads
            avg_current = sum(current_readings) / len(current_readings)
            
            # Read load
            load = self.read_current_load()
            
            # Convert load to signed value (1024 = center, 0-1023 = CCW, 1025-2047 = CW)
            if load >= 1024:
                signed_load = load - 1024  # CW direction (closing)
            else:
                signed_load = -(1024 - load)  # CCW direction
            
            self.position_mode_results.append({
                'effort': effort,
                'load': load,
                'signed_load': signed_load,
                'current_readings': current_readings,
                'avg_current': avg_current
            })
            
            self.logger.info(f"  Effort: {effort}% | Load: {load} | Signed: {signed_load}")
            self.logger.info(f"  Current readings (mA): {current_readings}")
            self.logger.info(f"  Average current: {avg_current:.1f} mA")
            
            # Release gripper - disable torque mode, springs open gripper naturally
            self.logger.info(f"  Releasing gripper for 10 seconds...")
            servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control  # Disable torque mode - springs open gripper
            time.sleep(10.0)
    
    def test_torque_mode(self, torque_levels: list[int]):
        """
        Test torque mode at various torque levels with recovery periods
        
        Args:
            torque_levels: List of torque percentages to test (e.g., [20, 30, 40, ...])
        """
        self.logger.info("\n" + "=" * 70)
        self.logger.info("TORQUE MODE CHARACTERIZATION")
        self.logger.info("=" * 70)
        self.logger.info("Testing at 0% position (gripper tries to go 10% beyond true zero)")
        self.logger.info("Methodology: Apply torque, read stable current (max 2s), release 10s")
        
        servo = self.gripper.servos[0]
        # Command 0% which tries to close 10% beyond true zero (pressing against itself)
        close_position = self.gripper.scale(0, self.gripper.GRIP_MAX)
        release_position = self.gripper.scale(50, self.gripper.GRIP_MAX)
        
        for torque in torque_levels:
            self.logger.info(f"\nTesting torque mode at {torque}% torque...")
            
            # Pre-position: Move to 8% open at 100% effort (gets gripper close to true zero without pressing)
            # With shifted zero, 8% is just before true zero (10%), so fingers won't press yet
            preposition = self.gripper.scale(8, self.gripper.GRIP_MAX)
            servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control  # Disable torque mode
            servo.write_word(38,  # Protocol 2.0: Current Limit 1023)    # 100% effort
            servo.write_word(116,  # Protocol 2.0: Goal Position preposition)
            time.sleep(1.0)  # Wait for gripper to reach pre-position
            
            # Read error state before applying torque
            error_code, error_desc = self.read_error_state()
            self.logger.info(f"  Pre-torque error state: {error_code} ({error_desc})")
            
            # Set torque limit (register 34) - limits max value for register 71
            torque_limit = self.gripper.scale(torque, self.gripper.TORQUE_MAX)
            servo.write_word(38,  # Protocol 2.0: Current Limit torque_limit)
            
            # Enable torque mode (register 70)
            servo.write_address(11, [0])  # Protocol 2.0: Operating Mode = Current Control
            
            # Set goal torque (register 71) - 1024 + value for CW direction
            goal_torque = 1024 + torque_limit
            servo.write_word(102,  # Protocol 2.0: Goal Current goal_torque)
            
            # Wait for gripper position to stop changing (reached physical limit)
            final_position = self.wait_for_position_stop(max_wait=2.0, stable_threshold=5)
            self.logger.info(f"  Gripper stopped at position: {final_position}")
            
            # Wait 0.5s for force to stabilize
            time.sleep(0.5)
            
            # Do 5 quick current reads
            current_readings = []
            for i in range(5):
                current = self.read_actual_current()
                current_readings.append(current)
                if i < 4:
                    time.sleep(0.05)  # 50ms between reads
            avg_current = sum(current_readings) / len(current_readings)
            
            # Read load
            load = self.read_current_load()
            
            # Read error state after applying torque
            error_code, error_desc = self.read_error_state()
            
            # Convert load to signed value
            if load >= 1024:
                signed_load = load - 1024  # CW direction (closing)
            else:
                signed_load = -(1024 - load)  # CCW direction
            
            self.torque_mode_results.append({
                'torque': torque,
                'load': load,
                'signed_load': signed_load,
                'current_readings': current_readings,
                'avg_current': avg_current,
                'error_code': error_code,
                'error_desc': error_desc
            })
            
            self.logger.info(f"  Torque: {torque}% | Load: {load} | Signed: {signed_load}")
            self.logger.info(f"  Current readings (mA): {current_readings}")
            self.logger.info(f"  Average current: {avg_current:.1f} mA")
            self.logger.info(f"  Post-torque error state: {error_code} ({error_desc})")
            
            # Release gripper - disable torque mode, springs open gripper naturally
            self.logger.info(f"  Releasing gripper for 10 seconds...")
            servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control  # Disable torque mode - springs open gripper
            time.sleep(10.0)
            
            # Read error state after recovery
            error_code, error_desc = self.read_error_state()
            self.logger.info(f"  Post-recovery error state: {error_code} ({error_desc})")
    
    def analyze_results(self):
        """Analyze and display results"""
        self.logger.info("\n" + "=" * 70)
        self.logger.info("ANALYSIS")
        self.logger.info("=" * 70)
        
        # Position mode summary
        self.logger.info("\nPosition Mode Results:")
        self.logger.info(f"{'Effort (%)':<12} {'Load':<8} {'Signed Load':<12} {'Avg Current (mA)':<18}")
        self.logger.info("-" * 55)
        for r in self.position_mode_results:
            self.logger.info(f"{r['effort']:<12} {r['load']:<8} {r['signed_load']:<12} {r['avg_current']:<18.1f}")
            self.logger.info(f"  Readings: {r['current_readings']}")
        
        # Torque mode summary
        self.logger.info("\nTorque Mode Results:")
        self.logger.info(f"{'Torque (%)':<12} {'Load':<8} {'Signed Load':<12} {'Avg Current (mA)':<18}")
        self.logger.info("-" * 55)
        for r in self.torque_mode_results:
            self.logger.info(f"{r['torque']:<12} {r['load']:<8} {r['signed_load']:<12} {r['avg_current']:<18.1f}")
            self.logger.info(f"  Readings: {r['current_readings']}")
        
        # Find crossover points
        self.logger.info("\n" + "=" * 70)
        self.logger.info("CROSSOVER ANALYSIS")
        self.logger.info("=" * 70)
        
        # Find what torque mode setting matches position mode 100%
        if self.position_mode_results and self.torque_mode_results:
            pos_100_load = next((r['signed_load'] for r in self.position_mode_results if r['effort'] == 100), None)
            
            if pos_100_load:
                self.logger.info(f"\nPosition mode 100% delivers signed load: {pos_100_load}")
                
                # Find closest torque mode setting
                closest_torque = None
                min_diff = float('inf')
                
                for r in self.torque_mode_results:
                    diff = abs(r['signed_load'] - pos_100_load)
                    if diff < min_diff:
                        min_diff = diff
                        closest_torque = r['torque']
                
                if closest_torque:
                    self.logger.info(f"Closest torque mode setting: {closest_torque}%")
                    self.logger.info(f"Difference: {min_diff} load units")
        
        # Generate mapping suggestions
        self.logger.info("\n" + "=" * 70)
        self.logger.info("TRANSITION RECOMMENDATIONS")
        self.logger.info("=" * 70)
        self.logger.info("\nFor smooth handoff from position to torque mode:")
        self.logger.info("1. Detect resistance while in position mode at 100%")
        self.logger.info("2. Read current load")
        self.logger.info("3. Map to equivalent torque mode setting using characterization data")
        self.logger.info("4. Transition to torque mode at equivalent setting")
        self.logger.info("5. Reduce to desired holding torque")
    
    def run(self):
        """Run full characterization test"""
        try:
            # Calibrate and shift zero point by 10%
            self.calibrate_and_shift_zero()
            
            # Test position mode at 0% position (20-100% effort in 10% increments)
            # 0% position is actually trying to close beyond true zero (pressing against itself)
            position_efforts = list(range(20, 101, 10))
            self.test_position_mode(position_efforts)
            
            # Test torque mode at 0% position (20-75% torque in 5% increments with recovery periods)
            torque_levels = list(range(20, 76, 5))
            self.test_torque_mode(torque_levels)
            
            # Analyze results
            self.analyze_results()
            
            # Return to neutral position
            self.logger.info("\n" + "=" * 70)
            self.logger.info("Returning to 50% position...")
            self.gripper.set_max_effort(50)
            self.gripper._goto_position(self.gripper.scale(50, self.gripper.GRIP_MAX))
            time.sleep(2.0)
            
            self.logger.info("Mode characterization complete!")
            
        except Exception as e:
            self.logger.error(f"Test failed: {e}")
            raise


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Mode Characterization Test")
    parser.add_argument("--dev", default="/dev/ttyUSB0",
                       help="Serial device (default: /dev/ttyUSB0)")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run characterization
    test = ModeCharacterization(device=args.dev)
    test.run()


if __name__ == "__main__":
    main()
