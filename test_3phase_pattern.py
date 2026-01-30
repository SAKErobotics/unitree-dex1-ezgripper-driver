"""
3-Phase Gripper Test Pattern

Tests gripper through 3 distinct operational phases:
1. Smooth oscillation (sine wave)
2. Random jumps
3. Instant point-to-point jumps

Sends commands via DDS (simulating XR teleoperate controller).
"""

import time
import random
import logging
import argparse
import math
from unitree_sdk2py.core.channel import ChannelPublisher, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_


class ThreePhaseTest:
    """3-phase gripper test pattern"""
    
    PHASE_DURATION = 25.0  # Total cycle duration (seconds)
    
    def __init__(self, side: str, rate_hz: float = 200.0, domain: int = 1):
        """
        Initialize 3-phase test
        
        Args:
            side: 'left' or 'right'
            rate_hz: Command rate in Hz (default 200 Hz for G1 XR)
            domain: DDS domain (default 1 for simulation)
        """
        self.side = side
        self.rate_hz = rate_hz
        self.period = 1.0 / rate_hz
        self.domain = domain
        
        self.logger = logging.getLogger(f"3phase_test_{side}")
        
        # Initialize DDS
        ChannelFactoryInitialize(domain)
        
        # Create DDS publisher for commands
        self.cmd_topic = f'rt/dex1/{side}/cmd'
        self.publisher = ChannelPublisher(self.cmd_topic, MotorCmds_)
        self.publisher.Init()
        
        # Dex1 mapping: 0% = 0.0 rad (closed), 100% = 1.94 rad (open)
        self.close_radians = 0.0
        self.open_radians = 1.94
        
        self.logger.info(f"3-phase test ready: {side} side at {rate_hz} Hz")
        self.logger.info(f"Publishing to: {self.cmd_topic}")
    
    def get_phase(self, elapsed: float) -> tuple[int, str]:
        """
        Determine current phase based on elapsed time
        
        Returns:
            (phase_number, phase_name)
        """
        t = elapsed % self.PHASE_DURATION
        
        if t < 10.0:
            return (1, "Smooth oscillation")
        elif t < 15.0:
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
        
        if phase == 1:
            # Phase 1: Smooth oscillation (sine wave)
            # 10 second period: 0% -> 100% -> 0%
            phase_time = t  # Start at t=0
            normalized = (math.sin(2 * math.pi * phase_time / 10.0) + 1.0) / 2.0
            return normalized * 100.0
        
        elif phase == 2:
            # Phase 2: Random jumps every second
            phase_time = t - 10.0
            jump_index = int(phase_time)
            random.seed(jump_index + 1000)  # Consistent random sequence
            return random.uniform(0.0, 100.0)
        
        else:
            # Phase 3: Instant point-to-point jumps
            phase_time = t - 15.0
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
                self.send_dds_command(position_pct)
                
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
            self.shutdown()
    
    def send_dds_command(self, position_pct: float):
        """Send DDS command for target position"""
        # Convert position percentage to radians
        # 0% = closed (0.0 rad), 100% = open (1.94 rad)
        q_radians = self.close_radians + (position_pct / 100.0) * (self.open_radians - self.close_radians)
        
        # Create motor command
        motor_cmd = unitree_go_msg_dds__MotorCmd_()
        motor_cmd.q = q_radians
        motor_cmd.dq = 0.0
        motor_cmd.tau = 0.0
        motor_cmd.kp = 5.0
        motor_cmd.kd = 0.05
        
        # Create motor commands message
        motor_cmds = MotorCmds_()
        motor_cmds.cmds = [motor_cmd]
        
        # Publish
        self.publisher.Write(motor_cmds)
    
    def shutdown(self):
        """Shutdown DDS publisher"""
        self.logger.info("Closing DDS publisher...")
        self.publisher.Close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="3-Phase Gripper Test Pattern")
    parser.add_argument("--side", required=True, choices=["left", "right"],
                       help="Gripper side (left/right)")
    parser.add_argument("--rate", type=float, default=200.0,
                       help="Command rate in Hz (default: 200)")
    parser.add_argument("--domain", type=int, default=1,
                       help="DDS domain (default: 1 for simulation)")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run test
    test = ThreePhaseTest(side=args.side, rate_hz=args.rate, domain=args.domain)
    test.run()


if __name__ == "__main__":
    main()
