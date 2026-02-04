"""
Grasp Manager - Simplified State-based Grasping

Simplified system:
- Constant force budget (30% holding, 50% moving)
- Position-only input from DDS
- Simple 4-state machine: idle, moving, contact, grasping
- Manages position in context of grasp/no-grasp

Core loop owns state and goal. DDS position commands are inputs that influence
(but don't directly control) the goal when in grasping state.
"""

from typing import Dict, Any, Tuple
from enum import Enum
import time


class GraspState(Enum):
    """Simplified 4-state machine"""
    IDLE = "idle"              # At rest, no goal
    MOVING = "moving"          # Moving to DDS position (no contact)
    CONTACT = "contact"        # Just detected contact, settling
    GRASPING = "grasping"      # Holding object at contact position


class GraspManager:
    """
    Simplified state-based grasp manager
    
    Percentage-based force system:
    - All forces are percentages (0-100%)
    - Config defines force for each state
    - Hardware limit enforced by register 38
    
    Position-only input:
    - DDS sends position commands (0-100%)
    - Force is managed internally based on state
    
    Simple state machine:
    - Manages position in context of grasp/no-grasp
    """
    
    def __init__(self, config):
        """
        Initialize grasp manager from config
        
        Args:
            config: Config object with force_management and collision_detection settings
        """
        # Load force percentages from config
        force_mgmt = config._config.get('servo', {}).get('force_management', {})
        self.MOVING_FORCE = force_mgmt.get('moving_force_pct', 80)
        self.HOLDING_FORCE = force_mgmt.get('holding_force_pct', 30)
        self.CONTACT_FORCE = force_mgmt.get('contact_force_pct', 30)
        self.IDLE_FORCE = force_mgmt.get('idle_force_pct', 0)
        
        # Load collision detection settings from config
        collision = config._config.get('servo', {}).get('collision_detection', {})
        self.current_threshold_pct = collision.get('current_spike_threshold_pct', 50)
        self.movement_threshold = collision.get('stagnation_movement_units', 2)
        self.consecutive_required = collision.get('consecutive_samples_required', 3)
        self.settling_duration = collision.get('settling_cycles', 10)
        
        # State
        self.state = GraspState.IDLE
        self.previous_state = GraspState.IDLE
        
        # Goals (what we want the gripper to do)
        self.goal_position = 50.0  # Start at 50% open
        self.goal_effort = 0.0     # No effort initially
        
        # Contact tracking
        self.contact_position = None
        self.contact_time = None
        self.settling_cycles = 0
        
        # Contact detection (simple consecutive samples)
        self.current_spike_count = 0
        self.stagnation_count = 0
        self.last_position = None
        
        # Timing
        self.state_entry_time = time.time()
        
        print(f"  GraspManager initialized:")
        print(f"    Forces: MOVING={self.MOVING_FORCE}%, HOLDING={self.HOLDING_FORCE}%, CONTACT={self.CONTACT_FORCE}%")
        print(f"    Thresholds: current={self.current_threshold_pct}%, movement={self.movement_threshold} units")
        print(f"    Filtering: {self.consecutive_required} consecutive samples, {self.settling_duration} settling cycles")
        
    def process_cycle(self, 
                     dds_position: float, 
                     dds_effort: float,
                     sensor_data: Dict[str, Any],
                     hardware_current_limit_ma: float = 1600) -> Tuple[float, float]:
        """
        Process one cycle - simplified position-only system
        
        Args:
            dds_position: Desired position from DDS (0-100%)
            dds_effort: Ignored - force is internal constant
            sensor_data: Current sensor readings (position, current, etc.)
            hardware_current_limit_ma: Hardware current limit from config (for percentage conversion)
            
        Returns:
            (goal_position, goal_effort): Managed goal to execute
        """
        current_position = sensor_data.get('position', 0.0)
        current_ma = abs(sensor_data.get('current', 0))
        
        # Convert current to percentage of hardware limit
        current_pct = (current_ma / hardware_current_limit_ma) * 100.0
        
        # DEBUG: Log state and inputs every 30 cycles (once per second at 30Hz)
        if not hasattr(self, '_debug_counter'):
            self._debug_counter = 0
        self._debug_counter += 1
        if self._debug_counter % 30 == 0:
            import logging
            logger = logging.getLogger('corrected_left')
            logger.info(f"🔧 GM: state={self.state.value}, dds={dds_position:.1f}%, current_pos={current_position:.1f}%, contact_pos={self.contact_position}")
        
        # Simple contact detection (percentage-based)
        contact_detected = self._detect_contact(current_position, current_pct)
        
        # Update state machine
        self._update_state(dds_position, current_position, contact_detected)
        
        # Update goal based on state
        self._update_goal(dds_position, current_position)
        
        return self.goal_position, self.goal_effort
    
    def _detect_contact(self, current_position: float, current_pct: float) -> bool:
        """
        Simple contact detection with consecutive sample filtering
        
        Contact detected by EITHER:
        1. Current spike: 3 consecutive readings > threshold_pct
        2. Position stagnation: 3 consecutive cycles with movement < threshold units
        
        Args:
            current_position: Current position (0-100%)
            current_pct: Current as percentage of hardware limit (0-100%)
        
        Returns:
            True if contact detected
        """
        # Check 1: Current spike (consecutive samples)
        if current_pct > self.current_threshold_pct:
            self.current_spike_count += 1
        else:
            self.current_spike_count = 0
        
        if self.current_spike_count >= self.consecutive_required:
            print(f"  ✋ Contact: current spike {current_pct:.0f}% ({self.consecutive_required} consecutive)")
            return True
        
        # Check 2: Position stagnation (consecutive samples)
        if self.last_position is not None:
            movement = abs(current_position - self.last_position)
            
            if movement < self.movement_threshold:
                self.stagnation_count += 1
            else:
                self.stagnation_count = 0
            
            if self.stagnation_count >= self.consecutive_required:
                print(f"  ✋ Contact: position stagnation (movement={movement:.1f}, 3 consecutive)")
                return True
        
        self.last_position = current_position
        return False
    
    def _update_state(self, 
                     dds_position: float,
                     current_position: float,
                     contact_detected: bool):
        """Simplified state machine - position-only input"""
        
        old_state = self.state
        
        if self.state == GraspState.IDLE:
            # Check if DDS wants us to move
            position_diff = abs(dds_position - current_position)
            if position_diff > 5:
                self.state = GraspState.MOVING
                print(f"  → MOVING to {dds_position:.1f}% (diff={position_diff:.1f}%)")
            else:
                # DEBUG: Log why we're not moving
                import logging
                logger = logging.getLogger('corrected_left')
                logger.debug(f"IDLE: dds={dds_position:.1f}%, current={current_position:.1f}%, diff={position_diff:.1f}% (threshold=5%)")
                
        elif self.state == GraspState.MOVING:
            # Check for contact
            if contact_detected:
                self.state = GraspState.CONTACT
                self.contact_position = current_position
                self.contact_time = time.time()
                self.settling_cycles = 0
                print(f"  → CONTACT at {current_position:.1f}%")
            # Check if reached target (within 2%)
            elif abs(dds_position - current_position) < 2:
                self.state = GraspState.IDLE
                print(f"  → IDLE (reached target)")
                
        elif self.state == GraspState.CONTACT:
            # Settling period (10 cycles = 330ms)
            self.settling_cycles += 1
            
            # Check for release command during settling
            if dds_position > self.contact_position + 20:
                self.state = GraspState.MOVING
                self.contact_position = None
                print(f"  → MOVING (release during settling)")
            # Check if settling complete
            elif self.settling_cycles >= self.settling_duration:
                self.state = GraspState.GRASPING
                print(f"  → GRASPING (settled after {self.settling_cycles} cycles)")
                
        elif self.state == GraspState.GRASPING:
            # Check if DDS wants to release (significant position change)
            if dds_position > self.contact_position + 20:
                self.state = GraspState.MOVING
                self.contact_position = None
                print(f"  → MOVING (release from grasp)")
            # Otherwise, stay in GRASPING and ignore DDS position commands
        
        # Log state transitions
        if old_state != self.state:
            self.previous_state = old_state
            self.state_entry_time = time.time()
    
    def _update_goal(self,
                    dds_position: float,
                    current_position: float):
        """Update goal based on current state - constant force"""
        
        if self.state == GraspState.IDLE:
            # No active goal - no effort
            self.goal_position = current_position
            self.goal_effort = 0
            
        elif self.state == GraspState.MOVING:
            # Follow DDS position with MOVING_FORCE (50%)
            self.goal_position = dds_position
            self.goal_effort = self.MOVING_FORCE
            
        elif self.state == GraspState.CONTACT:
            # Hold at contact position with HOLDING_FORCE (30%) during settling
            self.goal_position = self.contact_position
            self.goal_effort = self.HOLDING_FORCE
            
        elif self.state == GraspState.GRASPING:
            # Hold at contact position with HOLDING_FORCE (30%)
            # IGNORE DDS position commands (unless release, handled in state machine)
            self.goal_position = self.contact_position
            self.goal_effort = self.HOLDING_FORCE
    
    def reset(self):
        """Reset manager to idle state"""
        self.state = GraspState.IDLE
        self.previous_state = GraspState.IDLE
        self.goal_position = 50.0
        self.goal_effort = 0.0
        self.contact_position = None
        self.contact_time = None
        self.settling_cycles = 0
        self.current_spike_count = 0
        self.stagnation_count = 0
        self.last_position = None
        print("  🔄 GraspManager reset to IDLE")
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get current state information for monitoring"""
        return {
            'state': self.state.value,
            'previous_state': self.previous_state.value,
            'goal_position': self.goal_position,
            'goal_effort': self.goal_effort,
            'contact_position': self.contact_position,
            'time_in_state': time.time() - self.state_entry_time
        }
