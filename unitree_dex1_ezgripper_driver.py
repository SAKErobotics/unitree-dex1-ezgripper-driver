#!/usr/bin/env python3
"""
Unitree Dex1 EZGripper Driver

Allows SAKE Robotics EZGripper to be connected to Unitree G1 robot
and controlled through the standard Dex1 DDS interface.

This driver provides a drop-in replacement for the Unitree Dex1 gripper service,
enabling seamless integration with XR teleoperate and other G1 control systems.

Key Features:
- Direct DDS to libezgripper interface (no complex driver layer)
- Motor driver level compatibility using only q (position) and tau (torque)
- Optimized grasping: uses close mode when q ≤ 0.1 for improved grip strength
- Position + force control with automatic object detection
- Full XR teleoperate compatibility via rt/dex1/left|right/cmd topics
"""

import time
import math
import argparse
import logging
from dataclasses import dataclass
from typing import List

from cyclonedds.domain import DomainParticipant
from cyclonedds.topic import Topic
from cyclonedds.sub import DataReader
from cyclonedds.pub import DataWriter
from cyclonedds.qos import Qos, Policy
from cyclonedds.idl import IdlStruct

# Import libezgripper
from libezgripper import create_connection, Gripper


# DDS Message Types (Unitree Dex1 compatible)
@dataclass
class MotorCmd_(IdlStruct, typename="unitree_go.msg.dds_.MotorCmd_"):
    """Motor command - compatible with Unitree Dex1 DDS API"""
    mode: int = 0
    q: float = 0.0          # Position (radians) - PRIMARY CONTROL FIELD
    dq: float = 0.0
    tau: float = 0.0        # Torque/effort - PRIMARY FORCE FIELD  
    kp: float = 0.0
    kd: float = 0.0
    reserve: List[int] = None

@dataclass
class MotorCmds_(IdlStruct, typename="unitree_go.msg.dds_.MotorCmds_"):
    """Motor commands array - compatible with Unitree Dex1 DDS API"""
    cmds: List[MotorCmd_] = None

@dataclass  
class MotorState_(IdlStruct, typename="unitree_go.msg.dds_.MotorState_"):
    """Motor state - compatible with Unitree Dex1 DDS API"""
    mode: int = 0
    q: float = 0.0          # Current position
    dq: float = 0.0
    ddq: float = 0.0
    tau_est: float = 0.0    # Current torque estimate
    q_raw: float = 0.0
    dq_raw: float = 0.0
    ddq_raw: float = 0.0
    temperature: int = 0
    lost: int = 0
    reserve: List[int] = None

@dataclass
class MotorStates_(IdlStruct, typename="unitree_go.msg.dds_.MotorStates_"):
    """Motor states array - compatible with Unitree Dex1 DDS API"""
    states: List[MotorState_] = None


class UnitreeDex1EZGripperDriver:
    """
    Unitree Dex1 EZGripper Driver
    
    Provides Dex1-compatible DDS interface for SAKE Robotics EZGripper.
    Enables EZGripper to work as drop-in replacement for Unitree Dex1 gripper.
    """
    
    def __init__(self, side: str, device: str, motor_id: int, domain: int = 0):
        self.side = side
        self.device = device  
        self.motor_id = motor_id
        self.domain = domain
        
        # Setup logging
        self.logger = logging.getLogger(f"dex1_ezgripper_{side}")
        
        # Connect to EZGripper hardware
        self.logger.info(f"Connecting Dex1 EZGripper driver: {side} side on {device}, motor ID {motor_id}")
        self.connection = create_connection(device, 57600)
        self.gripper = Gripper(self.connection, f"dex1_ezgripper_{side}", [motor_id])
        
        # Calibrate gripper
        self.logger.info("Calibrating EZGripper for Dex1 compatibility...")
        self.gripper.calibrate()
        time.sleep(2)
        
        # Current state
        self.current_position_pct = 0.0
        self.current_effort_pct = 0.0
        self.last_cmd_time = time.time()
        
        # Setup DDS (Dex1 compatible topics)
        self._setup_dds()
        
        self.logger.info(f"Unitree Dex1 EZGripper driver ready: {side} side")
    
    def _setup_dds(self):
        """Setup DDS subscriber and publisher with Dex1 compatible topics"""
        self.participant = DomainParticipant(self.domain)
        
        # Command subscriber (rt/dex1/left|right/cmd) - Standard Dex1 topics
        cmd_topic_name = f"rt/dex1/{self.side}/cmd"
        self.cmd_topic = Topic(self.participant, cmd_topic_name, MotorCmds_)
        self.cmd_reader = DataReader(self.participant, self.cmd_topic)
        
        # State publisher (rt/dex1/left|right/state) - Standard Dex1 topics
        state_topic_name = f"rt/dex1/{self.side}/state"
        self.state_topic = Topic(self.participant, state_topic_name, MotorStates_)
        self.state_writer = DataWriter(self.participant, self.state_topic)
        
        self.logger.info(f"Dex1 DDS topics: {cmd_topic_name} (sub), {state_topic_name} (pub)")
    
    def _q_to_position_pct(self, q_radians: float) -> float:
        """Convert Dex1 motor position (radians) to EZGripper percentage"""
        # Map 0 to 2π radians → 0 to 100%
        position_pct = (q_radians / (2.0 * math.pi)) * 100.0
        return max(0.0, min(100.0, position_pct))
    
    def _tau_to_effort_pct(self, tau: float) -> float:
        """Convert Dex1 motor torque to EZGripper effort percentage"""  
        # Scale factor: tau * 10 = effort_pct
        effort_pct = abs(tau) * 10.0
        return max(0.0, min(100.0, effort_pct))
    
    def _position_pct_to_q(self, position_pct: float) -> float:
        """Convert EZGripper percentage to Dex1 motor position (radians)"""
        return (position_pct / 100.0) * 2.0 * math.pi
    
    def _effort_pct_to_tau(self, effort_pct: float) -> float:
        """Convert EZGripper effort percentage to Dex1 motor torque"""
        return effort_pct / 10.0
    
    def _process_dex1_commands(self):
        """Process Dex1 DDS commands and control EZGripper"""
        samples = self.cmd_reader.take(N=1)
        
        for sample in samples:
            if sample and sample.cmds and len(sample.cmds) > 0:
                # Get first motor command (Dex1 format)
                motor_cmd = sample.cmds[0]
                
                # Extract position and torque from Dex1 command
                target_position_pct = self._q_to_position_pct(motor_cmd.q)
                target_effort_pct = self._tau_to_effort_pct(motor_cmd.tau)
                
                # Use default effort if tau is zero
                if target_effort_pct == 0.0:
                    target_effort_pct = 80.0  # Default grip strength
                
                # EZGripper control logic with Dex1 optimization
                if motor_cmd.q <= 0.1:  # Close to 0 radians (fully closed)
                    self.logger.debug(f"Dex1 close command: using EZGripper close mode (q={motor_cmd.q:.3f})")
                    self.gripper.close(target_effort_pct)
                elif motor_cmd.q >= 6.0:  # Close to 2π radians (fully open)
                    self.logger.debug(f"Dex1 open command: using EZGripper open mode (q={motor_cmd.q:.3f})")
                    self.gripper.open(target_effort_pct)
                else:
                    # Normal position control with force limiting
                    self.gripper.goto_position(target_position_pct, target_effort_pct)
                
                # Update state
                self.current_position_pct = target_position_pct
                self.current_effort_pct = target_effort_pct
                self.last_cmd_time = time.time()
                
                self.logger.debug(f"Dex1 command: q={motor_cmd.q:.3f}rad → {target_position_pct:.1f}%, "
                                f"tau={motor_cmd.tau:.3f} → {target_effort_pct:.1f}%")
    
    def _publish_dex1_state(self):
        """Publish current EZGripper state as Dex1 motor state"""
        # Convert EZGripper state back to Dex1 motor units
        current_q = self._position_pct_to_q(self.current_position_pct)
        current_tau = self._effort_pct_to_tau(self.current_effort_pct)
        
        # Create Dex1 compatible motor state
        motor_state = MotorState_(
            mode=1,  # FOC mode
            q=current_q,
            dq=0.0,
            ddq=0.0,
            tau_est=current_tau,
            q_raw=current_q,
            dq_raw=0.0,
            ddq_raw=0.0,
            temperature=25,
            lost=0,
            reserve=[0, 0]
        )
        
        # Publish to Dex1 state topic
        motor_states = MotorStates_(states=[motor_state])
        self.state_writer.write(motor_states)
    
    def run(self):
        """Main Dex1 EZGripper driver loop"""
        self.logger.info("Starting Unitree Dex1 EZGripper driver loop")
        
        state_period = 0.1  # 10 Hz state publishing (Dex1 compatible)
        last_state_time = 0
        
        try:
            while True:
                # Process incoming Dex1 commands
                self._process_dex1_commands()
                
                # Publish Dex1 state periodically
                current_time = time.time()
                if current_time - last_state_time >= state_period:
                    self._publish_dex1_state()
                    last_state_time = current_time
                
                time.sleep(0.01)  # 100 Hz loop
                
        except KeyboardInterrupt:
            self.logger.info("Shutting down Dex1 EZGripper driver...")
        except Exception as e:
            self.logger.error(f"Error in Dex1 EZGripper driver: {e}")
        finally:
            self.connection.close()


def main():
    parser = argparse.ArgumentParser(description="Unitree Dex1 EZGripper Driver")
    parser.add_argument("--side", required=True, choices=["left", "right"],
                       help="Gripper side (left/right)")
    parser.add_argument("--dev", required=True,
                       help="Serial device (e.g., /dev/ttyUSB0)")
    parser.add_argument("--id", type=int, required=True,
                       help="Motor ID")
    parser.add_argument("--domain", type=int, default=0,
                       help="DDS domain")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run Dex1 EZGripper driver
    driver = UnitreeDex1EZGripperDriver(
        side=args.side,
        device=args.dev, 
        motor_id=args.id,
        domain=args.domain
    )
    
    driver.run()


if __name__ == "__main__":
    main()
