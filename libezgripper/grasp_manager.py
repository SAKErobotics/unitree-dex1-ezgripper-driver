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
        # Load config from servo.force_management structure (not state_machine)
        force_mgmt = config._config['servo']['force_management']
        
        # Force settings per state - no fallbacks, config is single source of truth
        self.MOVING_FORCE = force_mgmt['moving_force_pct']
        self.GRASPING_FORCE = force_mgmt['grasping_force_pct']
        self.IDLE_FORCE = force_mgmt['idle_force_pct']
        
        # Contact detection settings - read from collision_detection
        collision = config._config['servo']['collision_detection']
        self.CONSECUTIVE_SAMPLES_REQUIRED = collision['consecutive_samples_required']
        self.STALL_TOLERANCE_PCT = collision['stall_tolerance_pct']
        self.ZERO_TARGET_TOLERANCE_PCT = collision['zero_target_tolerance_pct']
        
        # Transition thresholds - read from collision_detection
        self.POSITION_CHANGE_THRESHOLD = collision['position_change_threshold_pct']
        self.COMMAND_CHANGE_THRESHOLD = collision['command_change_threshold_pct']
        
        # Contact settling delay - wait for stable grasp before transitioning to GRASPING
        self.CONTACT_SETTLING_DELAY = 0.5  # seconds
        
        # State
        self.state = GraspState.IDLE
        
        # Tracking
        self.last_dds_position = None
        self.last_servo_command = None
        self.contact_position = None
        self.contact_time = None  # Time when contact was detected
        self.grasping_setpoint = None  # DDS command position when grasp was established
        self.last_current_pct = 0.0
        self.position_history = []  # Track last 3 positions for range check
        self.contact_sample_count = 0  # For consecutive sample filtering
        
        logger = logging.getLogger(__name__)
        logger.info("  ✅ GraspManager V2 Clean Implementation Loaded")
        logger.info(f"    Forces: MOVING={self.MOVING_FORCE}%, GRASPING={self.GRASPING_FORCE}%, IDLE={self.IDLE_FORCE}%")
        logger.info(f"    Contact Detection: samples={self.CONSECUTIVE_SAMPLES_REQUIRED}, stall_tolerance={self.STALL_TOLERANCE_PCT}% (position stagnation only)")
        logger.info(f"    Thresholds: position_change={self.POSITION_CHANGE_THRESHOLD}%, command_change={self.COMMAND_CHANGE_THRESHOLD}%")
    
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
        contact_detected = self._detect_contact(current_position, current_pct, commanded_position)
        
        # Update state machine (driven by position commands AND servo state)
        self._update_state(commanded_position, current_position, contact_detected)
        
        # Determine goal based on state
        goal_position, goal_effort = self._compute_goal(commanded_position, current_position)
        
        # Track for next cycle
        self.last_dds_position = commanded_position
        self.last_current_pct = current_pct
        
        return goal_position, goal_effort
    
    def _detect_contact(self, current_position: float, current_pct: float, commanded_position: float) -> bool:
        """
        Stall detection based purely on position (no current check):
        1. Only check when in MOVING state
        2. Track last 3 positions
        3. If all 3 positions are within stall tolerance (2.0%) of each other → stagnant
        4. Contact detection:
           - Normal closing: If stagnant while closing → contact detected
           - Zero target special case: Allow grasping beyond zero with very tight tolerance
        5. Require N consecutive stagnant readings to trigger
        
        The zero target special case enables strong grasp on objects that can be
        compressed or have geometry allowing fingers to close past nominal zero.
        
        This is separate from collision detection (which uses current).
        Stall detection triggers before overload can occur.
        """
        # Only check for contact when actively moving
        if self.state != GraspState.MOVING:
            self.contact_sample_count = 0
            return False
        
        # Only detect stalls when CLOSING (commanded < current)
        # Opening movements should not trigger stall detection
        # Exception: Allow detection when at target 0% to enable grasping beyond zero
        is_closing = commanded_position < current_position
        at_zero_target = commanded_position < 1.0 and current_position <= 1.0
        if not is_closing and not at_zero_target:
            self.contact_sample_count = 0
            return False
        
        # Debug: Log every call when in MOVING state
        logger = logging.getLogger(__name__)
        if len(self.position_history) == 0 or len(self.position_history) % 30 == 0:  # Log every second
            logger.info(f"🔧 DETECT_CONTACT called: pos={current_position:.2f}%, target={commanded_position:.2f}%, closing={is_closing}")
        
        # Criteria: Position stagnation - range check across 3 samples
        # Track last 3 positions and check if they're all within stall tolerance
        self.position_history.append(current_position)
        if len(self.position_history) > 3:
            self.position_history.pop(0)
        
        position_stagnant = False
        position_range = 0.0
        
        if len(self.position_history) >= 3:
            # Check if all 3 positions are within stall tolerance of each other
            pos_min = min(self.position_history)
            pos_max = max(self.position_history)
            position_range = pos_max - pos_min
            position_stagnant = position_range < self.STALL_TOLERANCE_PCT
        
        # Detect stall based on position stagnation:
        # Case 1: Closing to any position - if stagnant, contact detected
        # Case 2: At zero target - allow grasping beyond zero with very tight tolerance
        target_is_zero = commanded_position < 1.0
        reached_zero = current_position <= 1.0  # At 0% or more closed
        very_stable = position_range < self.ZERO_TARGET_TOLERANCE_PCT  # 1 tick = 0.04%, very tight tolerance
        
        if target_is_zero and reached_zero and very_stable:
            # Special case: at zero target, allow grasping beyond zero
            is_stuck = True
        else:
            # Normal case: any position stagnation while closing
            is_stuck = position_stagnant
        
        if is_stuck and len(self.position_history) >= 3:
            self.contact_sample_count += 1
            # Log stall detection progress - only when incrementing
            logger = logging.getLogger(__name__)
            if target_is_zero and reached_zero and very_stable:
                logger.info(f"🔍 STALL (ZERO TARGET): pos={current_position:.2f}%, target={commanded_position:.2f}%, "
                           f"range={position_range:.4f}%, count={self.contact_sample_count}/{self.CONSECUTIVE_SAMPLES_REQUIRED}")
            else:
                logger.info(f"🔍 STALL: pos={current_position:.2f}%, target={commanded_position:.2f}%, "
                           f"range={position_range:.2f}%, count={self.contact_sample_count}/{self.CONSECUTIVE_SAMPLES_REQUIRED}")
        else:
            # Log when counter resets
            if self.contact_sample_count > 0:
                logger = logging.getLogger(__name__)
                logger.info(f"↻ STALL RESET: pos={current_position:.2f}% (moving or opening)")
            self.contact_sample_count = 0
        
        # Require N consecutive samples before declaring contact
        contact_triggered = self.contact_sample_count >= self.CONSECUTIVE_SAMPLES_REQUIRED
        if contact_triggered:
            logger = logging.getLogger(__name__)
            logger.info(f"🖐️ CONTACT DETECTED at {current_position:.2f}%")
        
        return contact_triggered
    
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
            if contact_detected:
                self.state = GraspState.CONTACT
                self.contact_position = current_position
                self.contact_time = time.time()  # Record when contact was detected
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
            # Wait for settling period before transitioning to GRASPING
            # This ensures stable contact before force changes
            if self.contact_time is None:
                self.contact_time = time.time()
            
            elapsed = time.time() - self.contact_time
            if elapsed >= self.CONTACT_SETTLING_DELAY:
                self.state = GraspState.GRASPING
                self.grasping_setpoint = dds_position  # Remember commanded position when grasp established
                logger = logging.getLogger(__name__)
                logger.info(f"⏱️  Contact settled after {elapsed:.3f}s, transitioning to GRASPING")
        
        elif self.state == GraspState.GRASPING:
            # Exit GRASPING only on OPENING commands (dds > setpoint)
            # Stay in GRASPING for closing/same commands (active grasp management)
            # Continuous command stream at 30Hz: only opening overrides grasp
            if self.grasping_setpoint is not None and dds_position > self.grasping_setpoint + self.POSITION_CHANGE_THRESHOLD:
                self.state = GraspState.MOVING
                self.contact_position = None
                self.grasping_setpoint = None
        
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
            # No active command - stay at current position with IDLE_FORCE (10% from config)
            return current_position, self.IDLE_FORCE
        
        elif self.state == GraspState.MOVING:
            # Follow DDS position command with MOVING_FORCE (17% from config)
            return dds_position, self.MOVING_FORCE
        
        elif self.state == GraspState.CONTACT:
            # Hold at contact position with MOVING_FORCE (17%) during settling period
            # This maintains the closing force until grasp is verified stable
            return self.contact_position, self.MOVING_FORCE
        
        elif self.state == GraspState.GRASPING:
            # Hold at commanded position with GRASPING_FORCE (configured per test)
            # Test script sets this to 15%, 20%, or 25% via config file
            return dds_position, self.GRASPING_FORCE
        
        # No fallback - config must provide all values
        raise RuntimeError(f"Invalid state: {self.state}")
    
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
