#!/usr/bin/env python3
"""
Unitree Dex1 EZGripper Driver

Allows SAKE Robotics EZGripper to be connected to Unitree G1 robot
and controlled through the standard Dex1 DDS interface.

This driver provides a drop-in replacement for the Unitree Dex1 gripper service,
enabling seamless integration with XR teleoperate and other G1 control systems.

Key Features:
- DDS-to-DDS translation layer (Dex1 commands → EZGripper commands)
- Hardware abstraction boundary for future Dynamixel API 2.0 migration
- Language-agnostic architecture - all tools use same DDS interface
- Motor driver level compatibility using only q (position) and tau (torque)
- Optimized grasping: uses close mode when q ≤ 0.1 for improved grip strength
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


# EZGripper DDS Message Types (from ezgripper-dds-driver)
@dataclass
class EzGripperCmd(IdlStruct, typename="ezgripper.msg.dds_.EzGripperCmd"):
    """EZGripper command message"""
    target_name: str = ""
    seq: int = 0
    stamp_ns: int = 0
    mode: int = 0           # ControlMode: 0=position, 1=open, 2=close
    position_pct: float = 0.0  # 0-100%
    effort_pct: float = 0.0    # 0-100%
    request_ack: bool = False

@dataclass
class EzGripperState(IdlStruct, typename="ezgripper.msg.dds_.EzGripperState"):
    """EZGripper state message"""
    source_name: str = ""
    seq: int = 0
    stamp_ns: int = 0
    connected: bool = False
    present_position_pct: float = 0.0  # 0-100%
    present_effort_pct: float = 0.0    # 0-100%
    is_moving: bool = False
    error_code: int = 0


class UnitreeDex1EZGripperDriver:
    """
    Unitree Dex1 EZGripper Driver
    
    DDS-to-DDS translation layer that converts Dex1 commands to EZGripper commands.
    Provides hardware abstraction boundary for future migration and language-agnostic development.
    """
    
    def __init__(self, side: str, gripper_name: str, domain: int = 0):
        self.side = side
        self.gripper_name = gripper_name
        self.domain = domain
        
        # Setup logging
        self.logger = logging.getLogger(f"dex1_ezgripper_{side}")
        
        # Current state tracking
        self.current_position_pct = 0.0
        self.current_effort_pct = 0.0
        self.last_cmd_time = time.time()
        self.last_ezgripper_state = None
        
        # Setup DDS interfaces
        self._setup_dds()
        
        self.logger.info(f"Unitree Dex1 EZGripper driver ready: {side} side → {gripper_name}")
    
    def _setup_dds(self):
        """Setup DDS interfaces for Dex1 and EZGripper communication"""
        self.participant = DomainParticipant(self.domain)
        
        # Dex1 interface (standard Dex1 topics)
        dex1_cmd_topic = f"rt/dex1/{self.side}/cmd"
        dex1_state_topic = f"rt/dex1/{self.side}/state"
        
        self.dex1_cmd_topic = Topic(self.participant, dex1_cmd_topic, MotorCmds_)
        self.dex1_cmd_reader = DataReader(self.participant, self.dex1_cmd_topic)
        
        self.dex1_state_topic = Topic(self.participant, dex1_state_topic, MotorStates_)
        self.dex1_state_writer = DataWriter(self.participant, self.dex1_state_topic)
        
        # EZGripper interface (ezgripper-dds-driver topics)
        ezgripper_cmd_topic = f"rt/ezgripper/{self.gripper_name}/cmd"
        ezgripper_state_topic = f"rt/ezgripper/{self.gripper_name}/state"
        
        self.ezgripper_cmd_topic = Topic(self.participant, ezgripper_cmd_topic, EzGripperCmd)
        self.ezgripper_cmd_writer = DataWriter(self.participant, self.ezgripper_cmd_topic)
        
        self.ezgripper_state_topic = Topic(self.participant, ezgripper_state_topic, EzGripperState)
        self.ezgripper_state_reader = DataReader(self.participant, self.ezgripper_state_topic)
        
        self.logger.info(f"DDS interfaces: Dex1 {dex1_cmd_topic}→{dex1_state_topic}, EZGripper {ezgripper_cmd_topic}→{ezgripper_state_topic}")
    
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
        """Process Dex1 DDS commands and translate to EZGripper DDS commands"""
        samples = self.dex1_cmd_reader.take(N=1)
        
        for sample in samples:
            if sample and sample.cmds and len(sample.cmds) > 0:
                # Get first motor command (Dex1 format)
                motor_cmd = sample.cmds[0]
                
                # Translate Dex1 command to EZGripper command
                ezgripper_cmd = self._translate_dex1_to_ezgripper(motor_cmd)
                
                # Publish EZGripper command via DDS
                self.ezgripper_cmd_writer.write(ezgripper_cmd)
                
                # Update tracking state
                self.current_position_pct = ezgripper_cmd.position_pct
                self.current_effort_pct = ezgripper_cmd.effort_pct
                self.last_cmd_time = time.time()
                
                self.logger.debug(f"Dex1→EZGripper: q={motor_cmd.q:.3f}rad → {ezgripper_cmd.position_pct:.1f}%, "
                                f"tau={motor_cmd.tau:.3f} → {ezgripper_cmd.effort_pct:.1f}%, mode={ezgripper_cmd.mode}")
    
    def _process_ezgripper_state(self):
        """Process EZGripper DDS state and update tracking"""
        samples = self.ezgripper_state_reader.take(N=1)
        
        for sample in samples:
            if sample:
                self.last_ezgripper_state = sample
                # Update tracking from actual EZGripper state
                self.current_position_pct = sample.present_position_pct
                self.current_effort_pct = sample.present_effort_pct
    
    def _publish_dex1_state(self):
        """Publish current EZGripper state as Dex1 motor state"""
        # Use actual EZGripper state if available, otherwise use tracking state
        if self.last_ezgripper_state:
            position_pct = self.last_ezgripper_state.present_position_pct
            effort_pct = self.last_ezgripper_state.present_effort_pct
            connected = self.last_ezgripper_state.connected
        else:
            position_pct = self.current_position_pct
            effort_pct = self.current_effort_pct
            connected = False
        
        # Convert EZGripper state back to Dex1 motor units
        current_q = self._position_pct_to_q(position_pct)
        current_tau = self._effort_pct_to_tau(effort_pct)
        
        # Create Dex1 compatible motor state
        motor_state = MotorState_(
            mode=1 if connected else 0,  # FOC mode if connected, brake mode if not
            q=current_q,
            dq=0.0,
            ddq=0.0,
            tau_est=current_tau,
            q_raw=current_q,
            dq_raw=0.0,
            ddq_raw=0.0,
            temperature=25,
            lost=0 if connected else 1,
            reserve=[0, 0]
        )
        
        # Publish to Dex1 state topic
        motor_states = MotorStates_(states=[motor_state])
        self.dex1_state_writer.write(motor_states)
    
    def _translate_dex1_to_ezgripper(self, motor_cmd: MotorCmd_) -> EzGripperCmd:
        """Translate Dex1 motor command to EZGripper command"""
        # Extract position and torque from Dex1 command
        target_position_pct = self._q_to_position_pct(motor_cmd.q)
        target_effort_pct = self._tau_to_effort_pct(motor_cmd.tau)
        
        # Use default effort if tau is zero
        if target_effort_pct == 0.0:
            target_effort_pct = 80.0  # Default grip strength
        
        # Determine EZGripper control mode based on Dex1 position
        if motor_cmd.q <= 0.1:  # Close to 0 radians (fully closed)
            mode = 2  # MODE_CLOSE - use EZGripper's optimized close mode
        elif motor_cmd.q >= 6.0:  # Close to 2π radians (fully open)
            mode = 1  # MODE_OPEN
        else:
            mode = 0  # MODE_POSITION - normal position control
        
        # Create EZGripper command
        return EzGripperCmd(
            target_name=self.gripper_name,
            seq=int(time.time() * 1000),  # Simple sequence number
            stamp_ns=time.time_ns(),
            mode=mode,
            position_pct=target_position_pct,
            effort_pct=target_effort_pct,
            request_ack=False
        )
    
    def run(self):
        """Main Dex1 EZGripper driver loop (DDS-to-DDS translation)"""
        self.logger.info("Starting Unitree Dex1 EZGripper driver (DDS translation layer)")
        
        state_period = 0.1  # 10 Hz state publishing (Dex1 compatible)
        last_state_time = 0
        
        try:
            while True:
                # Process incoming Dex1 commands → translate to EZGripper commands
                self._process_dex1_commands()
                
                # Process EZGripper state updates
                self._process_ezgripper_state()
                
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


def main():
    parser = argparse.ArgumentParser(description="Unitree Dex1 EZGripper Driver (DDS Translation Layer)")
    parser.add_argument("--side", required=True, choices=["left", "right"],
                       help="Gripper side (left/right)")
    parser.add_argument("--gripper-name", required=True,
                       help="EZGripper name (matches ezgripper-dds-driver config)")
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
    
    # Create and run Dex1 EZGripper driver (DDS translation layer)
    driver = UnitreeDex1EZGripperDriver(
        side=args.side,
        gripper_name=args.gripper_name,
        domain=args.domain
    )
    
    driver.run()


if __name__ == "__main__":
    main()
