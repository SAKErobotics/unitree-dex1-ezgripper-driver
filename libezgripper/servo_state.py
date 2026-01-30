"""Servo state data structures for bulk operations"""

from dataclasses import dataclass
import struct
import time


@dataclass
class ServoState:
    """
    Atomic snapshot of servo state from bulk read
    All data captured at same moment in time
    """
    timestamp: float
    current_raw: int        # Raw current value
    position_raw: int       # Raw position value (ticks)
    load_raw: int          # Raw load value
    error_code: int        # Hardware error code
    temperature_raw: int   # Temperature (°C)
    
    @classmethod
    def from_bulk_read(cls, data: bytes, timestamp: float = None) -> 'ServoState':
        """
        Parse bulk read data into ServoState
        
        Expected data format (10 bytes):
        - Bytes 0-1: Present Current (int16, address 126)
        - Bytes 2-5: Present Position (int32, address 132)
        - Bytes 6-7: Present Load (int16, address 128) - CORRECTED ADDRESS
        - Byte 8: Hardware Error (uint8, address 70)
        - Byte 9: Present Temperature (uint8, address 146)
        """
        if len(data) < 10:
            raise ValueError(f"Expected 10 bytes, got {len(data)}")
        
        current_raw = struct.unpack('<h', data[0:2])[0]  # Signed int16
        position_raw = struct.unpack('<i', data[2:6])[0]  # Signed int32
        load_raw = struct.unpack('<h', data[6:8])[0]     # Signed int16
        error_code = data[8]
        temperature_raw = data[9]
        
        return cls(
            timestamp=timestamp or time.time(),
            current_raw=current_raw,
            position_raw=position_raw,
            load_raw=load_raw,
            error_code=error_code,
            temperature_raw=temperature_raw
        )
    
    @property
    def current_ma(self) -> float:
        """Current in milliamps (mA)"""
        # MX-64: 1 unit = 3.36 mA
        return abs(self.current_raw) * 3.36
    
    @property
    def current_amps(self) -> float:
        """Current in amps (A)"""
        return self.current_ma / 1000.0
    
    @property
    def load_percent(self) -> float:
        """Load as percentage (0-100%)"""
        return (abs(self.load_raw) / 1023.0) * 100.0
    
    @property
    def temperature_celsius(self) -> float:
        """Temperature in Celsius"""
        return float(self.temperature_raw)
    
    def has_error(self) -> bool:
        """Check if any error is present"""
        return self.error_code != 0
    
    def get_error_description(self) -> str:
        """Get human-readable error description"""
        if self.error_code == 0:
            return "No error"
        
        errors = []
        if self.error_code & 0x01:
            errors.append("Input Voltage")
        if self.error_code & 0x04:
            errors.append("Overheating")
        if self.error_code & 0x08:
            errors.append("Motor Encoder")
        if self.error_code & 0x10:
            errors.append("Electrical Shock")
        if self.error_code & 0x20:
            errors.append("Overload")
        
        return ", ".join(errors) if errors else f"Unknown error: {self.error_code}"
