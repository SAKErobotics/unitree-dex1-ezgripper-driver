"""Efficient error monitoring using bulk sensor data"""

from dataclasses import dataclass
import time
from typing import Dict, List, Optional


@dataclass
class ErrorEvent:
    """Error event with context"""
    error_code: int
    description: str
    timestamp: float
    current_ma: float
    load_percent: float
    temperature_celsius: float
    severity: str  # 'warning', 'error', 'critical'


class ErrorMonitor:
    """Efficient error monitoring using bulk sensor data"""
    
    def __init__(self, config: dict = None):
        # Error tracking (minimal memory)
        self.error_counts: Dict[int, int] = {}
        self.last_error_time = 0
        self.error_history: List[ErrorEvent] = []
        self.max_history = 10  # Keep only recent errors
        
        # Thresholds for proactive detection
        self.temperature_warning = 60.0   # °C
        self.temperature_critical = 70.0  # °C
        self.current_warning = 800.0      # mA
        self.overload_threshold = 80.0    # % load
        
        # Rate limiting
        self.error_cooldown = 0.1  # seconds between same error notifications
        
        # Load config
        if config:
            self.temperature_warning = config.get('temp_warning', 60.0)
            self.temperature_critical = config.get('temp_critical', 70.0)
            self.current_warning = config.get('current_warning', 800.0)
            self.overload_threshold = config.get('overload_threshold', 80.0)
    
    def update(self, error_code: int, current_ma: float, load_percent: float, 
               temperature_celsius: float) -> List[ErrorEvent]:
        """
        Update with new sensor data and check for errors
        Returns list of new error events (empty if none)
        """
        timestamp = time.time()
        new_events = []
        
        # Check hardware error from servo
        if error_code != 0:
            if self._should_notify_error(error_code, timestamp):
                event = ErrorEvent(
                    error_code=error_code,
                    description=self._decode_error(error_code),
                    timestamp=timestamp,
                    current_ma=current_ma,
                    load_percent=load_percent,
                    temperature_celsius=temperature_celsius,
                    severity='error'
                )
                new_events.append(event)
                self._record_error(event)
        
        # Proactive error detection
        if temperature_celsius > self.temperature_critical:
            event = ErrorEvent(
                error_code=0xFF,  # Custom code for critical temperature
                description=f"Critical temperature: {temperature_celsius:.1f}°C",
                timestamp=timestamp,
                current_ma=current_ma,
                load_percent=load_percent,
                temperature_celsius=temperature_celsius,
                severity='critical'
            )
            new_events.append(event)
            self._record_error(event)
        
        elif temperature_celsius > self.temperature_warning:
            event = ErrorEvent(
                error_code=0xFE,  # Custom code for temperature warning
                description=f"High temperature: {temperature_celsius:.1f}°C",
                timestamp=timestamp,
                current_ma=current_ma,
                load_percent=load_percent,
                temperature_celsius=temperature_celsius,
                severity='warning'
            )
            new_events.append(event)
            self._record_error(event)
        
        if load_percent > self.overload_threshold:
            event = ErrorEvent(
                error_code=0xFD,  # Custom code for overload
                description=f"Overload detected: {load_percent:.1f}% load",
                timestamp=timestamp,
                current_ma=current_ma,
                load_percent=load_percent,
                temperature_celsius=temperature_celsius,
                severity='warning'
            )
            new_events.append(event)
            self._record_error(event)
        
        if current_ma > self.current_warning:
            event = ErrorEvent(
                error_code=0xFC,  # Custom code for high current
                description=f"High current: {current_ma:.0f} mA",
                timestamp=timestamp,
                current_ma=current_ma,
                load_percent=load_percent,
                temperature_celsius=temperature_celsius,
                severity='warning'
            )
            new_events.append(event)
            self._record_error(event)
        
        return new_events
    
    def _should_notify_error(self, error_code: int, timestamp: float) -> bool:
        """Check if error should be notified (rate limiting)"""
        if timestamp - self.last_error_time < self.error_cooldown:
            return False
        return True
    
    def _record_error(self, event: ErrorEvent):
        """Record error event"""
        self.last_error_time = event.timestamp
        
        # Count by error code
        self.error_counts[event.error_code] = self.error_counts.get(event.error_code, 0) + 1
        
        # Add to history (keep limited)
        self.error_history.append(event)
        if len(self.error_history) > self.max_history:
            self.error_history.pop(0)
    
    def _decode_error(self, error_code: int) -> str:
        """Decode Dynamixel hardware error code"""
        if error_code == 0:
            return "No error"
        
        errors = []
        if error_code & 0x01:
            errors.append("Input Voltage")
        if error_code & 0x02:
            errors.append("Angle Limit")
        if error_code & 0x04:
            errors.append("Overheating")
        if error_code & 0x08:
            errors.append("Motor Encoder")
        if error_code & 0x10:
            errors.append("Electrical Shock")
        if error_code & 0x20:
            errors.append("Overload")
        if error_code & 0x40:
            errors.append("Stall")
        
        return ", ".join(errors) if errors else f"Unknown error: {error_code}"
    
    def get_error_rate(self, window_seconds: float = 10.0) -> float:
        """Get error rate in last N seconds"""
        cutoff = time.time() - window_seconds
        recent_errors = [e for e in self.error_history if e.timestamp > cutoff]
        return len(recent_errors) / window_seconds
    
    def has_recent_error(self, max_age: float = 1.0) -> bool:
        """Check if error occurred recently"""
        if not self.error_history:
            return False
        return (time.time() - self.error_history[-1].timestamp) < max_age
    
    def get_worst_severity(self) -> str:
        """Get worst severity in recent history"""
        if not self.error_history:
            return 'none'
        
        severities = {'warning': 1, 'error': 2, 'critical': 3}
        worst = 'none'
        worst_level = 0
        
        for event in self.error_history:
            level = severities.get(event.severity, 0)
            if level > worst_level:
                worst = event.severity
                worst_level = level
        
        return worst
