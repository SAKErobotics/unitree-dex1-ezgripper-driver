#!/usr/bin/env python3
"""
lib_robotis.py wrapper using Dynamixel SDK as backend

This provides the same interface as lib_robotis.py but uses the official
Dynamixel SDK for Protocol 2.0 communication instead of custom implementation.
"""

import time
import threading
from dynamixel_sdk import *

class CommunicationError(Exception):
    pass

class ErrorResponse(Exception):
    pass

class USB2Dynamixel_Device:
    """USB2Dynamixel device using Dynamixel SDK backend"""
    
    def __init__(self, dev_name, baudrate=1000000):
        self.dev_name = dev_name
        self.baudrate = baudrate
        self.lock = threading.Lock()
        
        # Initialize Dynamixel SDK
        self.portHandler = PortHandler(dev_name)
        self.packetHandler = PacketHandler(2.0)  # Protocol 2.0
        
        # Open port
        if not self.portHandler.openPort():
            raise CommunicationError(f"Failed to open port {dev_name}")
        
        # Set baudrate
        if not self.portHandler.setBaudRate(baudrate):
            raise CommunicationError(f"Failed to set baudrate to {baudrate}")
        
        time.sleep(0.1)  # Stabilization delay

class Robotis_Servo:
    """Robotis servo control using Dynamixel SDK backend"""
    
    def __init__(self, dyn, servo_id):
        self.dyn = dyn
        self.servo_id = servo_id
        self.retry_count = 3
        
        # Verify servo responds
        model_num, comm_result, error = self.dyn.packetHandler.ping(
            self.dyn.portHandler, self.servo_id
        )
        
        if comm_result != COMM_SUCCESS:
            raise CommunicationError(
                f"Could not find ID ({servo_id}) on bus ({dyn.dev_name}), "
                f"or USB2Dynamixel 3-way switch in wrong position."
            )
    
    def read_address(self, address, nBytes=1):
        """Read nBytes from address"""
        with self.dyn.lock:
            if nBytes == 1:
                value, comm_result, error = self.dyn.packetHandler.read1ByteTxRx(
                    self.dyn.portHandler, self.servo_id, address
                )
                if comm_result != COMM_SUCCESS:
                    raise CommunicationError(
                        self.dyn.packetHandler.getTxRxResult(comm_result)
                    )
                if error != 0:
                    raise ErrorResponse(error)
                return [value]
            
            elif nBytes == 2:
                value, comm_result, error = self.dyn.packetHandler.read2ByteTxRx(
                    self.dyn.portHandler, self.servo_id, address
                )
                if comm_result != COMM_SUCCESS:
                    raise CommunicationError(
                        self.dyn.packetHandler.getTxRxResult(comm_result)
                    )
                if error != 0:
                    raise ErrorResponse(error)
                # Return as list of bytes
                return [value & 0xFF, (value >> 8) & 0xFF]
            
            elif nBytes == 4:
                value, comm_result, error = self.dyn.packetHandler.read4ByteTxRx(
                    self.dyn.portHandler, self.servo_id, address
                )
                if comm_result != COMM_SUCCESS:
                    raise CommunicationError(
                        self.dyn.packetHandler.getTxRxResult(comm_result)
                    )
                if error != 0:
                    raise ErrorResponse(error)
                # Return as list of bytes
                return [
                    value & 0xFF,
                    (value >> 8) & 0xFF,
                    (value >> 16) & 0xFF,
                    (value >> 24) & 0xFF
                ]
            else:
                raise ValueError(f"Unsupported read size: {nBytes}")
    
    def write_address(self, address, data):
        """Write data at the address"""
        with self.dyn.lock:
            nBytes = len(data)
            
            if nBytes == 1:
                comm_result, error = self.dyn.packetHandler.write1ByteTxRx(
                    self.dyn.portHandler, self.servo_id, address, data[0]
                )
            elif nBytes == 2:
                value = data[0] + (data[1] << 8)
                comm_result, error = self.dyn.packetHandler.write2ByteTxRx(
                    self.dyn.portHandler, self.servo_id, address, value
                )
            elif nBytes == 4:
                value = data[0] + (data[1] << 8) + (data[2] << 16) + (data[3] << 24)
                comm_result, error = self.dyn.packetHandler.write4ByteTxRx(
                    self.dyn.portHandler, self.servo_id, address, value
                )
            else:
                raise ValueError(f"Unsupported write size: {nBytes}")
            
            if comm_result != COMM_SUCCESS:
                raise CommunicationError(
                    self.dyn.packetHandler.getTxRxResult(comm_result)
                )
            if error != 0:
                raise ErrorResponse(error)
            
            return []
    
    def write_addressX(self, address, data):
        """Write data at the address, return error instead of raising"""
        try:
            self.write_address(address, data)
            return [], 0
        except ErrorResponse as e:
            return [], e.args[0]
        except CommunicationError:
            return [], 255  # Communication error
    
    def read_word(self, addr):
        """Read 2-byte word from address"""
        data = self.read_address(addr, 2)
        return data[0] + (data[1] << 8)
    
    def write_word(self, addr, word):
        """Write word to address with correct byte size for MX-64 Protocol 2.0"""
        # MX-64 register sizes (from control table)
        # 1-byte registers
        ONE_BYTE_REGS = {5, 7, 8, 9, 10, 11, 13, 16, 17, 18, 19, 20}
        # 4-byte registers
        FOUR_BYTE_REGS = {44, 48, 52, 100, 102, 104, 108, 112, 116, 120, 124, 126, 128, 132, 136, 140, 144, 146, 148, 152, 156, 160, 168, 172, 176, 180, 578, 580, 582, 584, 586, 588, 590, 592, 594, 596, 600, 604, 606, 610, 612, 614, 616}
        # Everything else is 2-byte
        
        if addr in ONE_BYTE_REGS:
            data = [word & 0xFF]
        elif addr in FOUR_BYTE_REGS:
            data = [word & 0xFF, (word >> 8) & 0xFF, (word >> 16) & 0xFF, (word >> 24) & 0xFF]
        else:
            # Default 2-byte
            data = [word & 0xFF, (word >> 8) & 0xFF]
        
        self.write_address(addr, data)
    
    def read_wordX(self, addr):
        """Read 2-byte word, return error instead of raising"""
        try:
            value = self.read_word(addr)
            return value, 0
        except ErrorResponse as e:
            return 0, e.args[0]
        except CommunicationError:
            return 0, 255
    
    def read_addressX(self, address, nBytes=1):
        """Read nBytes from address, return error instead of raising"""
        try:
            data = self.read_address(address, nBytes)
            return data, 0
        except ErrorResponse as e:
            return [], e.args[0]
        except CommunicationError:
            return [], 255
    
    def process_err(self, err):
        """Process error code"""
        raise ErrorResponse(err)
    
    def ensure_byte_set(self, address, byte):
        """Ensure a byte value is set at address, write if different"""
        value = self.read_address(address)[0]
        if value != byte:
            print('Servo [%d]: change setting %d from %d to %d'%(self.servo_id, address, value, byte))
            self.write_address(address, [byte])
    
    def ensure_word_set(self, address, word):
        """Ensure a word value is set at address, write if different"""
        value = self.read_word(address)
        if value != word:
            print('Servo [%d]: change setting %d from %d to %d (word)'%(self.servo_id, address, value, word))
            self.write_word(address, word)
    
    def read_encoder(self):
        """Read current encoder position (Present Position register 132)"""
        data = self.read_address(132, 4)
        position = data[0] + (data[1] << 8) + (data[2] << 16) + (data[3] << 24)
        # Handle signed 32-bit integer
        if position >= 2147483648:
            position -= 4294967296
        return position
    
    def read_word_signed(self, addr):
        """Read signed word from address (handles 4-byte registers as signed)"""
        # For Protocol 2.0, position registers are 4 bytes
        if addr >= 100:
            data = self.read_address(addr, 4)
            value = data[0] + (data[1] << 8) + (data[2] << 16) + (data[3] << 24)
            # Handle signed 32-bit integer
            if value >= 2147483648:
                value -= 4294967296
        else:
            data = self.read_address(addr, 2)
            value = data[0] + (data[1] << 8)
            # Handle signed 16-bit integer
            if value >= 32768:
                value -= 65536
        return value

def create_connection(dev_name, baudrate=1000000):
    """Create USB2Dynamixel connection"""
    return USB2Dynamixel_Device(dev_name, baudrate)

def find_servos_on_all_ports(baudrate=1000000):
    """Find servos on all available serial ports"""
    import serial.tools.list_ports
    
    servos = []
    ports = serial.tools.list_ports.comports()
    
    for port in ports:
        try:
            dyn = USB2Dynamixel_Device(port.device, baudrate)
            # Try to ping servo IDs 1-10
            for servo_id in range(1, 11):
                try:
                    servo = Robotis_Servo(dyn, servo_id)
                    servos.append((port.device, servo_id))
                except:
                    pass
        except:
            pass
    
    return servos
