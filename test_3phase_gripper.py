#!/usr/bin/env python3
"""
3-Phase EZGripper Test Script

Tests the gripper through three distinct phases:
1. Full open/close cycles (2 times)
2. Random position movements (5 seconds, 1 second intervals)
3. Continuous smooth movement (open to close and back, 5 seconds total)

Uses G1 DDS interface to control Dex1 gripper.
"""

import time
import random
import argparse
import numpy as np
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_, MotorStates_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_

class ThreePhaseGripperTest:
    """3-Phase gripper test using DDS interface"""
    
    def __init__(self, side: str = 'left', domain: int = 0):
        self.side = side
        self.domain = domain
        
        # Initialize DDS
        ChannelFactoryInitialize(domain)
        
        # Topics
        self.cmd_topic = f"rt/dex1/{side}/cmd"
        self.state_topic = f"rt/dex1/{side}/state"
        
        # Setup publisher for commands
        self.cmd_publisher = ChannelPublisher(self.cmd_topic, MotorCmds_)
        self.cmd_publisher.Init()
        
        # Setup subscriber for state feedback
        self.state_subscriber = ChannelSubscriber(self.state_topic, MotorStates_)
        self.state_subscriber.Init()
        
        print(f"🤖 3-Phase Gripper Test: {side} side")
        print(f"📡 Command Topic: {self.cmd_topic}")
        print(f"📡 State Topic: {self.state_topic}")
        print()
    
    def send_position_command(self, position_rad: float, description: str = ""):
        """
        Send position command to gripper
        position_rad: 0.0 = fully closed, 5.4 = fully open
        """
        # Clamp to valid range
        position_rad = max(0.0, min(5.4, position_rad))
        
        # Create command message
        cmd_msg = MotorCmds_()
        cmd_msg.cmds = [unitree_go_msg_dds__MotorCmd_()]
        
        # Set motor parameters (matching xr_teleoperate)
        cmd_msg.cmds[0].q = position_rad
        cmd_msg.cmds[0].dq = 0.0
        cmd_msg.cmds[0].tau = 0.0
        cmd_msg.cmds[0].kp = 5.00
        cmd_msg.cmds[0].kd = 0.05
        
        # Send command
        self.cmd_publisher.Write(cmd_msg)
        
        # Print status
        percentage = (position_rad / 5.4) * 100.0
        if description:
            print(f"  → {description}: {position_rad:.2f} rad ({percentage:.0f}%)")
        else:
            print(f"  → Position: {position_rad:.2f} rad ({percentage:.0f}%)")
    
    def get_current_position(self):
        """Read current gripper position from state"""
        state_msg = self.state_subscriber.Read()
        if state_msg and hasattr(state_msg, 'states') and state_msg.states:
            return float(state_msg.states[0].q)
        return None
    
    def phase1_full_cycles(self):
        """
        Phase 1: Full open/close cycles (2 times)
        """
        print("=" * 60)
        print("PHASE 1: Full Open/Close Cycles (2x)")
        print("=" * 60)
        
        for cycle in range(2):
            print(f"\n🔄 Cycle {cycle + 1}/2:")
            
            # Full close
            print("  Closing...")
            self.send_position_command(0.0, "Full Close")
            time.sleep(2.0)
            
            # Full open
            print("  Opening...")
            self.send_position_command(5.4, "Full Open")
            time.sleep(2.0)
        
        print("\n✅ Phase 1 Complete\n")
    
    def phase2_random_positions(self):
        """
        Phase 2: Random position movements (5 seconds, 1 second intervals)
        """
        print("=" * 60)
        print("PHASE 2: Random Position Movements (5 positions)")
        print("=" * 60)
        
        for i in range(5):
            # Generate random position between 0.0 and 5.4
            random_pos = random.uniform(0.0, 5.4)
            
            print(f"\n🎲 Random Position {i + 1}/5:")
            self.send_position_command(random_pos, f"Random")
            time.sleep(1.0)
        
        print("\n✅ Phase 2 Complete\n")
    
    def phase3_continuous_movement(self):
        """
        Phase 3: Continuous smooth movement (open to close and back, 5 seconds total)
        """
        print("=" * 60)
        print("PHASE 3: Continuous Smooth Movement (5 seconds)")
        print("=" * 60)
        
        duration = 5.0  # Total duration
        update_rate = 20  # Hz
        dt = 1.0 / update_rate
        
        start_time = time.time()
        
        print("\n🌊 Smooth movement: Open → Close → Open")
        
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            
            # Create smooth sinusoidal movement
            # Goes from 5.4 (open) → 0.0 (close) → 5.4 (open) over 5 seconds
            phase = (elapsed / duration) * 2 * np.pi
            position = 2.7 + 2.7 * np.cos(phase)  # Oscillates between 0 and 5.4
            
            self.send_position_command(position, f"Smooth (t={elapsed:.1f}s)")
            time.sleep(dt)
        
        print("\n✅ Phase 3 Complete\n")
    
    def run_full_test(self):
        """Run all three phases"""
        print("\n" + "=" * 60)
        print("🧪 STARTING 3-PHASE GRIPPER TEST")
        print("=" * 60)
        print()
        
        try:
            # Phase 1: Full cycles
            self.phase1_full_cycles()
            time.sleep(1.0)
            
            # Phase 2: Random positions
            self.phase2_random_positions()
            time.sleep(1.0)
            
            # Phase 3: Continuous movement
            self.phase3_continuous_movement()
            
            # Return to safe position
            print("=" * 60)
            print("🏁 TEST COMPLETE - Returning to safe position (50%)")
            print("=" * 60)
            self.send_position_command(2.7, "Safe Position")
            time.sleep(1.0)
            
            print("\n🎉 All phases completed successfully!")
            return True
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Test interrupted by user")
            print("Returning to safe position...")
            self.send_position_command(2.7, "Safe Position")
            time.sleep(1.0)
            return False
        
        except Exception as e:
            print(f"\n\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            print("\nReturning to safe position...")
            self.send_position_command(2.7, "Safe Position")
            time.sleep(1.0)
            return False

def main():
    parser = argparse.ArgumentParser(description="3-Phase EZGripper Test")
    parser.add_argument('--side', choices=['left', 'right'], default='left', help="Gripper side")
    parser.add_argument('--domain', type=int, default=0, help="DDS domain ID")
    
    args = parser.parse_args()
    
    # Create and run test
    test = ThreePhaseGripperTest(args.side, args.domain)
    success = test.run_full_test()
    
    exit(0 if success else 1)

if __name__ == "__main__":
    main()
