#!/usr/bin/env python3
"""
Collision reaction strategies for EZGripper

Provides modular, pluggable reactions to collision events.
Each strategy defines what happens when a collision is detected.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from .grasp_controller import GraspController, GraspState


class CollisionReaction(ABC):
    """Base class for collision reaction strategies"""
    
    @abstractmethod
    def on_collision(self, gripper, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Called when collision is detected
        
        Args:
            gripper: Gripper instance (to call goto_position, etc)
            sensor_data: Current sensor readings
            
        Returns:
            dict: Reaction result with keys:
                - 'action_taken': str description
                - 'new_position': Optional[float] if position changed
                - 'new_effort': Optional[float] if effort changed
                - 'stop_monitoring': bool if collision monitoring should stop
        """
        pass


class CalibrationReaction(CollisionReaction):
    """Reaction for calibration: record zero position and relax to 50%"""
    
    def on_collision(self, gripper, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record zero position and move to 50% open"""
        # Record zero position from collision
        # Store NEGATIVE of collision position as offset
        # During bulk read, adding this offset gives position relative to zero
        collision_position = sensor_data.get('position_raw', 0)
        gripper.zero_positions[0] = -collision_position
        
        print(f"  📍 Collision at: {collision_position}, offset set to: {-collision_position}")
        print(f"  🔄 Relaxing to position 50%...")
        
        # Move to position 50 to reduce load (fast with 100% effort)
        gripper.goto_position(50, 100)
        
        # Diagnostic: Check servo state after command
        import time
        time.sleep(0.01)  # Small delay for servo to process
        try:
            torque = gripper.servos[0].read_word(64)
            present_pos = gripper.servos[0].read_address(132, 4)
            present_pos_val = present_pos[0] + (present_pos[1] << 8) + (present_pos[2] << 16) + (present_pos[3] << 24)
            if present_pos_val & 0x80000000:
                present_pos_val = present_pos_val - 0x100000000
            hw_error = gripper.servos[0].read_word(70)
            
            print(f"  🔍 Servo state after command:")
            print(f"     Torque enabled: {torque}")
            print(f"     Present position: {present_pos_val}")
            print(f"     Hardware error: {hw_error} (0x{hw_error:02x})")
        except Exception as e:
            print(f"  ⚠️  Could not read servo state: {e}")
        
        # Stop calibration
        gripper.calibration_active = False
        gripper.collision_detected = True
        
        return {
            'action_taken': 'calibration_complete',
            'new_position': 50,
            'new_effort': 30,
            'stop_monitoring': True,
            'zero_position': collision_position
        }


class GraspReaction(CollisionReaction):
    """
    Simple grasping reaction - DEFAULT for production use
    
    Behavior:
    - On contact: reduce effort to holding level
    - Maintain current target position
    - Continue monitoring for slip/changes
    """
    
    def __init__(self, holding_effort: float = 30):
        """
        Args:
            holding_effort: Effort to use after contact (0-100%)
        """
        self.holding_effort = holding_effort
        self.contact_detected = False
    
    def on_collision(self, gripper, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Reduce effort to holding level on contact"""
        
        if not self.contact_detected:
            self.contact_detected = True
            current_position = sensor_data.get('position', 0)
            
            print(f"  ✋ Contact detected at position {current_position:.1f}%")
            print(f"  🔽 Reducing effort: {gripper.target_effort}% → {self.holding_effort}%")
        
        # Maintain target position but reduce effort
        gripper.goto_position(gripper.target_position, self.holding_effort)
        
        # Mark collision but continue monitoring
        gripper.collision_detected = True
        
        return {
            'action_taken': 'grasp_set',
            'new_position': gripper.target_position,
            'new_effort': self.holding_effort,
            'stop_monitoring': False,  # Keep monitoring
            'contact_position': sensor_data.get('position', 0)
        }


# Alias for backward compatibility
AdaptiveGripReaction = GraspReaction


class HoldPositionReaction(CollisionReaction):
    """
    Reaction for holding: stop movement, maintain current position
    
    Use case: Gripper moving to target, hits obstacle, stops immediately
    """
    
    def __init__(self, hold_effort: float = 50):
        """
        Args:
            hold_effort: Effort to use when holding position
        """
        self.hold_effort = hold_effort
    
    def on_collision(self, gripper, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Stop at current position"""
        current_position = sensor_data.get('position', 0)
        
        print(f"  🛑 Obstacle detected at position {current_position:.1f}%")
        print(f"  🔒 Holding position with {self.hold_effort}% effort")
        
        # Command current position to stop movement
        gripper.goto_position(current_position, self.hold_effort)
        
        gripper.collision_detected = True
        
        return {
            'action_taken': 'hold_position',
            'new_position': current_position,
            'new_effort': self.hold_effort,
            'stop_monitoring': True,  # Stop after holding
            'hold_position': current_position
        }


class RelaxReaction(CollisionReaction):
    """
    Reaction for safety: immediately open gripper to safe position
    
    Use case: Excessive force detected, open to prevent damage
    """
    
    def __init__(self, safe_position: float = 80, safe_effort: float = 20):
        """
        Args:
            safe_position: Position to open to (0-100%)
            safe_effort: Effort to use when opening
        """
        self.safe_position = safe_position
        self.safe_effort = safe_effort
    
    def on_collision(self, gripper, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Open to safe position"""
        current_position = sensor_data.get('position', 0)
        current_current = sensor_data.get('current', 0)
        
        print(f"  ⚠️  Excessive force detected: {current_current}mA at {current_position:.1f}%")
        print(f"  🔓 Opening to safe position {self.safe_position}%")
        
        # Open to safe position
        gripper.goto_position(self.safe_position, self.safe_effort)
        
        gripper.collision_detected = True
        
        return {
            'action_taken': 'safety_relax',
            'new_position': self.safe_position,
            'new_effort': self.safe_effort,
            'stop_monitoring': True,
            'trigger_current': current_current
        }


class SmartGraspReaction(CollisionReaction):
    """
    Smart grasping with force curve and temperature-aware holding
    
    This is the DEFAULT reaction for production use.
    
    Features:
    - 5-cycle moving window filter for current and position
    - Rapid force reduction during grasp: max → 50% as position stabilizes
    - Detects grasp set when position change = 0
    - Temperature-aware holding algorithm
    - Monitors temperature and adjusts force dynamically
    
    Use case: Fast close → contact → ramp down force → hold with temp monitoring
    """
    
    def __init__(self, 
                 max_force: float = 100,
                 grasp_set_force: float = 50,
                 holding_force_low: float = 30,
                 holding_force_mid: float = 50,
                 temp_warning: float = 60,
                 temp_critical: float = 70):
        """
        Args:
            max_force: Initial closing force (0-100%)
            grasp_set_force: Force when grasp is set (0-100%)
            holding_force_low: Low holding force (0-100%)
            holding_force_mid: Mid holding force (0-100%)
            temp_warning: Temperature warning threshold (°C)
            temp_critical: Temperature critical threshold (°C)
        """
        self.controller = GraspController(
            max_force=max_force,
            grasp_set_force=grasp_set_force,
            holding_force_low=holding_force_low,
            holding_force_mid=holding_force_mid,
            temp_warning_threshold=temp_warning,
            temp_critical_threshold=temp_critical
        )
        self.initialized = False
    
    def on_collision(self, gripper, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Called every cycle during grasping operation
        
        Note: This is called continuously, not just once on collision.
        The GraspController manages the state machine internally.
        """
        # Update controller with sensor data
        control_output = self.controller.update(sensor_data)
        
        # Apply force command
        current_position = sensor_data.get('position', 0)
        target_force = control_output['force']
        
        # Command gripper with updated force
        gripper.goto_position(current_position, target_force)
        
        # Check if we should stop monitoring (grasp released or error)
        stop_monitoring = False
        if control_output['state'] == GraspState.RELEASED:
            stop_monitoring = True
        
        return {
            'action_taken': 'smart_grasp',
            'grasp_state': control_output['state'],
            'current_force': target_force,
            'new_position': current_position,
            'new_effort': target_force,
            'stop_monitoring': stop_monitoring,
            'control_output': control_output
        }


class CustomReaction(CollisionReaction):
    """
    Custom reaction using user-provided callback
    
    Use case: Application-specific logic
    """
    
    def __init__(self, callback):
        """
        Args:
            callback: Function(gripper, sensor_data) -> dict
        """
        self.callback = callback
    
    def on_collision(self, gripper, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute custom callback"""
        return self.callback(gripper, sensor_data)


# Factory for easy creation
def create_reaction(reaction_type: str, **kwargs) -> CollisionReaction:
    """
    Factory function to create collision reactions
    
    Args:
        reaction_type: Type of reaction ('calibration', 'adaptive_grip', 'hold', 'relax', 'custom')
        **kwargs: Arguments for the specific reaction type
        
    Returns:
        CollisionReaction instance
    """
    reactions = {
        'calibration': CalibrationReaction,
        'adaptive_grip': AdaptiveGripReaction,
        'smart_grasp': SmartGraspReaction,
        'hold': HoldPositionReaction,
        'relax': RelaxReaction,
        'custom': CustomReaction
    }
    
    if reaction_type not in reactions:
        raise ValueError(f"Unknown reaction type: {reaction_type}. Choose from {list(reactions.keys())}")
    
    return reactions[reaction_type](**kwargs)
