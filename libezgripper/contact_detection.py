"""Efficient contact detection using bulk sensor data"""

from dataclasses import dataclass
import time
from typing import Optional, Tuple


@dataclass
class ContactInfo:
    """Contact detection result"""
    in_contact: bool
    confidence: float  # 0.0 to 1.0
    method: str  # 'current', 'load', 'combined'
    current_ma: float
    load_percent: float
    timestamp: float


class ContactDetector:
    """Efficient contact detection using bulk sensor data"""
    
    def __init__(self, config: dict = None):
        # Default thresholds (tunable per application)
        self.current_threshold = 100.0  # mA - sudden current spike
        self.load_threshold = 15.0      # % - increased load during contact
        self.current_spike_window = 0.1  # seconds - window for spike detection
        
        # History for trend analysis (minimal memory)
        self.history_size = 3
        self.current_history = []
        self.load_history = []
        
        # State tracking
        self.last_contact_time = 0
        self.last_position_pct = 50.0
        
        # Load config if provided
        if config:
            self.current_threshold = config.get('contact_current_threshold', 100.0)
            self.load_threshold = config.get('contact_load_threshold', 15.0)
    
    def update(self, current_ma: float, load_percent: float, position_pct: float) -> Optional[ContactInfo]:
        """
        Update with new sensor data and detect contact
        Returns None if insufficient data, ContactInfo if detection possible
        """
        timestamp = time.time()
        
        # Add to history (keep minimal)
        self.current_history.append((timestamp, current_ma))
        self.load_history.append((timestamp, load_percent))
        
        # Trim history
        if len(self.current_history) > self.history_size:
            self.current_history.pop(0)
        if len(self.load_history) > self.history_size:
            self.load_history.pop(0)
        
        # Need at least 2 points for trend detection
        if len(self.current_history) < 2:
            return None
        
        # Detect contact using multiple methods
        current_result = self._detect_current_spike(timestamp)
        load_result = self._detect_load_increase()
        
        # Combine results
        if current_result[0] or load_result[0]:
            # Use the method with higher confidence
            if current_result[1] > load_result[1]:
                method = 'current'
                confidence = current_result[1]
            else:
                method = 'load'
                confidence = load_result[1]
            
            # Combined detection has higher confidence
            if current_result[0] and load_result[0]:
                method = 'combined'
                confidence = min(1.0, confidence + 0.2)
            
            self.last_contact_time = timestamp
            
            return ContactInfo(
                in_contact=True,
                confidence=confidence,
                method=method,
                current_ma=current_ma,
                load_percent=load_percent,
                timestamp=timestamp
            )
        
        # No contact detected
        return ContactInfo(
            in_contact=False,
            confidence=0.0,
            method='none',
            current_ma=current_ma,
            load_percent=load_percent,
            timestamp=timestamp
        )
    
    def _detect_current_spike(self, timestamp: float) -> Tuple[bool, float]:
        """Detect sudden current spike"""
        if len(self.current_history) < 2:
            return False, 0.0
        
        # Get recent change
        current_time, current_value = self.current_history[-1]
        prev_time, prev_value = self.current_history[-2]
        
        # Check if within spike detection window
        if current_time - prev_time > self.current_spike_window:
            return False, 0.0
        
        # Calculate rate of change
        dt = current_time - prev_time
        if dt <= 0:
            return False, 0.0
        
        current_rate = (current_value - prev_value) / dt  # mA/second
        
        # Detect spike (simple threshold)
        if current_rate > self.current_threshold:
            confidence = min(1.0, current_rate / (self.current_threshold * 2))
            return True, confidence
        
        return False, 0.0
    
    def _detect_load_increase(self) -> Tuple[bool, float]:
        """Detect sustained load increase"""
        if len(self.load_history) < 2:
            return False, 0.0
        
        # Get current vs baseline (average of history)
        current_load = self.load_history[-1][1]
        baseline_load = sum(h[1] for h in self.load_history[:-1]) / (len(self.load_history) - 1)
        
        # Detect increase
        if current_load > baseline_load + self.load_threshold:
            confidence = min(1.0, (current_load - baseline_load) / (self.load_threshold * 2))
            return True, confidence
        
        return False, 0.0
    
    def is_recent_contact(self, max_age: float = 0.5) -> bool:
        """Check if contact was detected recently"""
        return (time.time() - self.last_contact_time) < max_age
