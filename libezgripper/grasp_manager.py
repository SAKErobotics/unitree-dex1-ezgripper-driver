"""
GraspManager - Clean First Pass Implementation

Architecture:
- Input: DDS position commands at 200Hz (downsampled to 30Hz by control loop)
- Processing: State machine driven by position commands AND servo state
- Output: Servo commands only when necessary (position change or state transition)

State Machine:
- IDLE: No active command, no effort
- MOVING: Following position command, monitoring for contact
- CONTACT: Detected obstacle, settling before grasp
- GRASPING: Holding object, ignoring small position changes
"""

from typing import Dict, Any, Tuple, Optional
from enum import Enum
import time
import logging


class GraspState(Enum):
    IDLE = "idle"
    MOVING = "moving"
    CONTACT = "contact"
    GRASPING = "grasping"


class GraspManager:
    """
    Clean first-pass grasp manager
    
    Key behaviors:
    1. Pass through position commands when in IDLE/MOVING
    2. Detect contact from servo current/position stagnation
    3. Hold position when grasping
    4. Only send servo commands on significant changes
    """
    
    def __init__(self, config):
        # Load config
        force_mgmt = config._config.get('servo', {}).get('force_management', {})
        self.MOVING_FORCE = force_mgmt.get('moving_force_pct', 80)
        self.HOLDING_FORCE = force_mgmt.get('holding_force_pct', 20)
        
        collision = config._config.get('servo', {}).get('collision_detection', {})
        self.CURRENT_THRESHOLD_PCT = collision.get('current_spike_threshold_pct', 40)
        self.CONSECUTIVE_SAMPLES_REQUIRED = collision.get('consecutive_samples_required', 3)
        self.STAGNATION_THRESHOLD = collision.get('stagnation_movement_units', 0.5)
        self.POSITION_CHANGE_THRESHOLD = 1.0  # % - significant position change (lowered for responsiveness)
        self.COMMAND_CHANGE_THRESHOLD = 3.0   # % - when to send new servo command
        
        # State
        self.state = GraspState.IDLE
        
        # Tracking
        self.last_dds_position = None
        self.last_servo_command = None
        self.contact_position = None
        self.last_current_pct = 0.0
        self.last_position = None  # For stagnation detection
        self.contact_sample_count = 0  # For consecutive sample filtering
        
        logger = logging.getLogger(__name__)
        logger.info("  ✅ GraspManager V2 Clean Implementation Loaded")
        logger.info(f"    Forces: MOVING={self.MOVING_FORCE}%, HOLDING={self.HOLDING_FORCE}%")
        logger.info(f"    Contact Detection: current>{self.CURRENT_THRESHOLD_PCT}%, stagnation<{self.STAGNATION_THRESHOLD}%, samples={self.CONSECUTIVE_SAMPLES_REQUIRED}")
        logger.info(f"    Thresholds: position_change={self.POSITION_CHANGE_THRESHOLD}%")
    
    def process_cycle(self, 
                     sensor_data: Dict[str, Any],
                     hardware_current_limit_ma: float = 1600) -> Tuple[float, float]:
        """
        Process one cycle at 30Hz
        
        Args:
            sensor_data: Dict containing 'position' (actual %), 'current' (mA), 
                        'commanded_position' (target %), etc.
            hardware_current_limit_ma: Max current in mA for percentage conversion
        
        Returns:
            (goal_position, goal_effort): Command to send to servo
        """
        current_position = sensor_data.get('position', 0.0)
        commanded_position = sensor_data.get('commanded_position', current_position)
        current_ma = abs(sensor_data.get('current', 0))
        current_pct = (current_ma / hardware_current_limit_ma) * 100.0
        
        # Detect contact from servo state
        contact_detected = self._detect_contact(current_position, current_pct)
        
        # Update state machine (driven by position commands AND servo state)
        self._update_state(commanded_position, current_position, contact_detected)
        
        # Determine goal based on state
        goal_position, goal_effort = self._compute_goal(commanded_position, current_position)
        
        # Track for next cycle
        self.last_dds_position = commanded_position
        self.last_current_pct = current_pct
        
        return goal_position, goal_effort
    
    def _detect_contact(self, current_position: float, current_pct: float) -> bool:
        """
        Robust contact detection with multiple criteria:
        1. Only check when in MOVING state (avoid false positives during acceleration)
        2. High current (exceeds threshold)
        3. Position stagnation (gripper stuck, not moving)
        4. Consecutive samples (filter transient spikes)
        
        This eliminates oscillation from instantaneous current spikes during movement.
        """
        # Only check for contact when actively moving
        if self.state != GraspState.MOVING:
            self.contact_sample_count = 0
            return False
        
        # Criteria 1: High current
        high_current = current_pct > self.CURRENT_THRESHOLD_PCT
        
        # Criteria 2: Position stagnation (not moving despite command)
        if self.last_position is not None:
            position_change = abs(current_position - self.last_position)
            position_stagnant = position_change < self.STAGNATION_THRESHOLD
        else:
            # First cycle - initialize tracking
            position_stagnant = False
            self.last_position = current_position
            return False
        
        # Update position tracking
        self.last_position = current_position
        
        # Criteria 3: Consecutive samples (both high current AND stagnation)
        if high_current and position_stagnant:
            self.contact_sample_count += 1
        else:
            self.contact_sample_count = 0
        
        # Debug logging for contact detection
        if self.state == GraspState.MOVING and (high_current or position_stagnant):
            logger = logging.getLogger(__name__)
            logger.info(f"🔍 CONTACT CHECK: current={current_pct:.1f}% (thresh={self.CURRENT_THRESHOLD_PCT}%), "
                       f"pos_change={position_change:.2f}% (thresh={self.STAGNATION_THRESHOLD}%), "
                       f"samples={self.contact_sample_count}/{self.CONSECUTIVE_SAMPLES_REQUIRED}")
        
        # Require N consecutive samples before declaring contact
        # This filters out transient spikes during acceleration
        return self.contact_sample_count >= self.CONSECUTIVE_SAMPLES_REQUIRED
    
    def _update_state(self, dds_position: float, current_position: float, contact_detected: bool):
        """
        State machine driven by position commands AND servo state
        """
        old_state = self.state
        
        if self.state == GraspState.IDLE:
            # Position command drives transition to MOVING
            # Transition if commanded position differs from current position
            if abs(dds_position - current_position) > self.POSITION_CHANGE_THRESHOLD:
                self.state = GraspState.MOVING
        
        elif self.state == GraspState.MOVING:
            # Servo state (contact) drives transition to CONTACT
            # If gripper cannot reach commanded position, contact detection will trigger
            # (high current + position stagnation = object blocking movement)
            if contact_detected:
                self.state = GraspState.CONTACT
                self.contact_position = current_position
            # Directional logic: Allow IDLE transition when OPENING, but not when CLOSING
            # Opening (increasing position) = no objects in the way, can reach target
            # Closing (decreasing position) = may hit object, stay in MOVING until contact
            elif abs(current_position - dds_position) < self.POSITION_CHANGE_THRESHOLD:
                # Determine direction
                if self.last_dds_position is not None:
                    direction = dds_position - self.last_dds_position
                    is_opening = direction > 0  # Positive = opening (increasing %)
                    
                    # Only transition to IDLE when opening
                    if is_opening:
                        self.state = GraspState.IDLE
        
        elif self.state == GraspState.CONTACT:
            # Simple first pass: immediately transition to GRASPING
            # Future: Add settling period
            self.state = GraspState.GRASPING
        
        elif self.state == GraspState.GRASPING:
            # Position command (release) drives transition back to MOVING
            # Release when commanded position increases (opens) relative to last command
            if self.last_dds_position is not None:
                position_change = dds_position - self.last_dds_position
                # If commanded position increases (opens), transition to MOVING
                if position_change > self.POSITION_CHANGE_THRESHOLD:
                    self.state = GraspState.MOVING
                    self.contact_position = None
        
        # Log state transitions
        if old_state != self.state:
            logger = logging.getLogger(__name__)
            logger.info(f"🔄 GM STATE: {old_state.value} → {self.state.value} (dds={dds_position:.1f}%, pos={current_position:.1f}%)")
    
    def _compute_goal(self, dds_position: float, current_position: float) -> Tuple[float, float]:
        """
        Compute goal position and effort based on state
        
        Returns:
            (position, effort): Goal for servo
        """
        if self.state == GraspState.IDLE:
            # No active command - stay at current position with minimal holding force
            return current_position, 10.0
        
        elif self.state == GraspState.MOVING:
            # Follow DDS position command
            return dds_position, self.MOVING_FORCE
        
        elif self.state == GraspState.CONTACT:
            # Hold at contact position
            return self.contact_position, self.HOLDING_FORCE
        
        elif self.state == GraspState.GRASPING:
            # Hold at contact position with reduced force
            # Commanding the actual contact position (reachable) prevents continuous
            # force application that causes overload
            return self.contact_position, self.HOLDING_FORCE
        
        # Fallback
        return current_position, 0.0
    
    def should_send_command(self, goal_position: float) -> bool:
        """
        Determine if we should send a new command to servo
        
        Only send when:
        - First command (last_servo_command is None)
        - Significant position change
        - State transition (handled by caller)
        
        This implements the "send only on change" behavior
        """
        if self.last_servo_command is None:
            self.last_servo_command = goal_position
            return True
        
        if abs(goal_position - self.last_servo_command) > self.COMMAND_CHANGE_THRESHOLD:
            self.last_servo_command = goal_position
            return True
        
        return False
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get current state for monitoring"""
        return {
            'state': self.state.value,
            'contact_position': self.contact_position,
            'last_dds_position': self.last_dds_position,
            'last_servo_command': self.last_servo_command
        }
    
    def reset(self):
        """Reset to IDLE state"""
        self.state = GraspState.IDLE
        self.contact_position = None
        self.last_dds_position = None
        self.last_servo_command = None
        print("  GM: Reset to IDLE")
