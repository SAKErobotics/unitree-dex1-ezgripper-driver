#!/usr/bin/env python3
"""
Collision reaction strategies for EZGripper

Provides modular, pluggable reactions to collision events.
Each strategy defines what happens when a collision is detected.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


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
        collision_position = sensor_data.get('position_raw', 0)
        gripper.zero_positions[0] = collision_position
        
        print(f"  📍 Zero position set to: {collision_position}")
        print(f"  🔄 Relaxing to position 50%...")
        
        # Move to position 50 to reduce load
        gripper.goto_position(50, 30)
        
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


class AdaptiveGripReaction(CollisionReaction):
    """
    Reaction for adaptive gripping: reduce effort when contact detected
    
    Use case: Gripper closing fast (100% effort) hits object, 
    immediately reduces to holding effort (e.g., 30%)
    """
    
    def __init__(self, holding_effort: float = 30):
        """
        Args:
            holding_effort: Effort to use after contact (0-100%)
        """
        self.holding_effort = holding_effort
    
    def on_collision(self, gripper, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Reduce effort to holding level, maintain position"""
        current_position = sensor_data.get('position', 0)
        
        print(f"  ✋ Contact detected at position {current_position:.1f}%")
        print(f"  🔽 Reducing effort: {gripper.target_effort}% → {self.holding_effort}%")
        
        # Maintain current position but reduce effort
        gripper.goto_position(gripper.target_position, self.holding_effort)
        
        # Mark collision but continue monitoring
        gripper.collision_detected = True
        
        return {
            'action_taken': 'adaptive_grip',
            'new_position': gripper.target_position,
            'new_effort': self.holding_effort,
            'stop_monitoring': False,  # Keep monitoring for slip/changes
            'contact_position': current_position
        }


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
        'hold': HoldPositionReaction,
        'relax': RelaxReaction,
        'custom': CustomReaction
    }
    
    if reaction_type not in reactions:
        raise ValueError(f"Unknown reaction type: {reaction_type}. Choose from {list(reactions.keys())}")
    
    return reactions[reaction_type](**kwargs)
