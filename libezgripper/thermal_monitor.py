"""Efficient thermal monitoring using bulk sensor data"""

from dataclasses import dataclass
import time
from typing import Optional


@dataclass
class ThermalState:
    """Current thermal state"""
    temperature_celsius: float
    trend: str  # 'rising', 'stable', 'cooling'
    rate_c_per_sec: float
    time_to_shutdown: Optional[float]  # seconds until critical temp
    warning_level: str  # 'normal', 'warning', 'critical'


class ThermalMonitor:
    """Efficient thermal monitoring using bulk sensor data"""
    
    def __init__(self, config: dict = None):
        # Temperature thresholds
        self.normal_max = 50.0      # °C
        self.warning_threshold = 60.0  # °C
        self.critical_threshold = 70.0 # °C
        self.shutdown_threshold = 75.0 # °C
        
        # Trend analysis (minimal memory)
        self.history_size = 5
        self.temp_history: List[tuple] = []  # (timestamp, temperature)
        
        # Rate calculation
        self.trend_window = 2.0  # seconds for trend calculation
        self.heating_rate_max = 2.0  # °C/sec - worst case heating
        
        # Load config
        if config:
            self.normal_max = config.get('temp_normal', 50.0)
            self.warning_threshold = config.get('temp_warning', 60.0)
            self.critical_threshold = config.get('temp_critical', 70.0)
            self.shutdown_threshold = config.get('temp_shutdown', 75.0)
    
    def update(self, temperature_celsius: float) -> ThermalState:
        """
        Update with new temperature and return thermal state
        """
        timestamp = time.time()
        
        # Add to history
        self.temp_history.append((timestamp, temperature_celsius))
        
        # Trim history
        if len(self.temp_history) > self.history_size:
            self.temp_history.pop(0)
        
        # Calculate trend
        trend, rate = self._calculate_trend(timestamp)
        
        # Calculate time to shutdown if heating
        time_to_shutdown = None
        if trend == 'rising' and temperature_celsius >= self.warning_threshold:
            time_to_shutdown = max(0, (self.shutdown_threshold - temperature_celsius) / max(rate, 0.1))
        
        # Determine warning level
        if temperature_celsius >= self.critical_threshold:
            warning_level = 'critical'
        elif temperature_celsius >= self.warning_threshold:
            warning_level = 'warning'
        else:
            warning_level = 'normal'
        
        return ThermalState(
            temperature_celsius=temperature_celsius,
            trend=trend,
            rate_c_per_sec=rate,
            time_to_shutdown=time_to_shutdown,
            warning_level=warning_level
        )
    
    def _calculate_trend(self, current_time: float) -> tuple:
        """Calculate temperature trend and rate"""
        if len(self.temp_history) < 2:
            return 'stable', 0.0
        
        # Find data points within trend window
        cutoff = current_time - self.trend_window
        recent = [(t, temp) for t, temp in self.temp_history if t >= cutoff]
        
        if len(recent) < 2:
            return 'stable', 0.0
        
        # Linear regression for trend
        n = len(recent)
        sum_t = sum(t for t, _ in recent)
        sum_temp = sum(temp for _, temp in recent)
        sum_tt = sum(t * t for t, _ in recent)
        sum_ttemp = sum(t * temp for t, temp in recent)
        
        # Calculate slope (rate)
        denominator = n * sum_tt - sum_t * sum_t
        if abs(denominator) < 1e-10:
            return 'stable', 0.0
        
        rate = (n * sum_ttemp - sum_t * sum_temp) / denominator
        
        # Determine trend
        if rate > 0.5:  # °C/sec
            trend = 'rising'
        elif rate < -0.5:
            trend = 'cooling'
        else:
            trend = 'stable'
        
        return trend, rate
    
    def is_warning(self) -> bool:
        """Check if temperature is at warning level"""
        if not self.temp_history:
            return False
        return self.temp_history[-1][1] >= self.warning_threshold
    
    def is_critical(self) -> bool:
        """Check if temperature is at critical level"""
        if not self.temp_history:
            return False
        return self.temp_history[-1][1] >= self.critical_threshold
    
    def get_average_temperature(self, window_seconds: float = 10.0) -> float:
        """Get average temperature over time window"""
        cutoff = time.time() - window_seconds
        recent = [temp for t, temp in self.temp_history if t >= cutoff]
        return sum(recent) / len(recent) if recent else 0.0
    
    def was_overheated(self, max_age: float = 60.0) -> bool:
        """Check if overheating occurred recently"""
        cutoff = time.time() - max_age
        for _, temp in self.temp_history:
            if temp >= self.warning_threshold:
                return True
        return False
