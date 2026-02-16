#!/usr/bin/env python3
"""
Custom DDS Message Types for EZGripper Interface

These messages provide advanced gripper management capabilities
that are orthogonal to the basic Dex1 position/force interface.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class EZGripperAction(IntEnum):
    """EZGripper management actions (non-position/force control)"""
    NO_OP = 0                    # No operation
    GET_STATUS = 1               # Request detailed status
    CALIBRATE = 2                # Calibrate gripper zero position
    CLEAR_ERRORS = 3             # Clear hardware errors (torque cycle)


class GraspState(IntEnum):
    """GraspManager state machine states"""
    IDLE = 0                     # No movement, no contact
    MOVING = 1                   # Actively moving to target
    CONTACT = 2                  # Contact detected, managing force
    GRASPING = 3                 # Stable grasp achieved
    ERROR = 4                    # Error state
    CALIBRATING = 5              # Calibration in progress


@dataclass
class EZGripperCmd:
    """EZGripper control message for advanced management"""
    action: EZGripperAction      # What action to perform
    parameters: Optional[dict] = None           # Additional parameters
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


@dataclass
class EZGripperState:
    """EZGripper state message for detailed status"""
    timestamp: float             # Message timestamp
    
    # Basic State (for reference, not control)
    actual_position_pct: float   # Current actual position (0-100%)
    actual_effort_pct: float     # Current actual effort (0-100%)
    
    # GraspManager State
    grasp_state: GraspState      # Current grasp state
    grasp_state_description: str # Human-readable state name
    
    # Hardware Status
    temperature_c: float         # Servo temperature (°C)
    current_ma: float            # Current draw (mA)
    voltage_v: float             # Supply voltage (V)
    hardware_error: int          # Hardware error register
    hardware_error_description: str  # Human-readable error
    
    # Calibration Status
    is_calibrated: bool          # Calibration status
    calibration_offset: float    # Current calibration offset
    serial_number: str           # Hardware serial number
    
    # Health Monitoring
    is_moving: bool              # Servo currently moving
    contact_detected: bool       # Contact detection status
    
    # State Machine Details (from GraspManager)
    contact_position: Optional[float] = None    # Position where contact was detected
    last_dds_position: Optional[float] = None   # Last commanded position from DDS
    last_servo_command: Optional[float] = None  # Last position sent to servo
    
    def to_dict(self):
        """Convert to dictionary for easy serialization"""
        return {
            'timestamp': self.timestamp,
            'position': {
                'actual_pct': self.actual_position_pct
            },
            'effort': {
                'actual_pct': self.actual_effort_pct
            },
            'grasp_manager': {
                'state': int(self.grasp_state),
                'state_name': self.grasp_state_description
            },
            'hardware': {
                'temperature_c': self.temperature_c,
                'current_ma': self.current_ma,
                'voltage_v': self.voltage_v,
                'error': self.hardware_error,
                'error_description': self.hardware_error_description
            },
            'calibration': {
                'is_calibrated': self.is_calibrated,
                'offset': self.calibration_offset,
                'serial_number': self.serial_number
            },
            'health': {
                'is_moving': self.is_moving,
                'contact_detected': self.contact_detected
            },
            'state_machine': {
                'contact_position': self.contact_position,
                'last_dds_position': self.last_dds_position,
                'last_servo_command': self.last_servo_command
            },
            'hardware': {
                'position_raw': self.position_raw
            }
        }


# Message type aliases for DDS
EZGripperCmd_ = EZGripperCmd
EZGripperState_ = EZGripperState
