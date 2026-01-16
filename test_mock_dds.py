#!/usr/bin/env python3
"""
Mock DDS Interface for Testing Unitree Dex1 EZGripper Driver

This creates a mock DDS implementation to test the translation layer
without requiring the cyclonedds Python package.
"""

import time
import threading
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Callable, Optional

# Mock DDS message types (same structure as real DDS)
@dataclass
class MotorCmd_:
    """Mock motor command - same structure as Unitree DDS"""
    mode: int = 0
    q: float = 0.0          # Position (radians)
    dq: float = 0.0
    tau: float = 0.0        # Torque/effort
    kp: float = 0.0
    kd: float = 0.0
    reserve: List[int] = None

@dataclass
class MotorCmds_:
    """Mock motor commands array"""
    cmds: List[MotorCmd_] = None

@dataclass
class MotorState_:
    """Mock motor state - same structure as Unitree DDS"""
    mode: int = 0
    q: float = 0.0
    dq: float = 0.0
    ddq: float = 0.0
    tau_est: float = 0.0
    q_raw: float = 0.0
    dq_raw: float = 0.0
    ddq_raw: float = 0.0
    temperature: int = 0
    lost: int = 0
    reserve: List[int] = None

@dataclass
class MotorStates_:
    """Mock motor states array"""
    states: List[MotorState_] = None

@dataclass
class EzGripperCmd:
    """Mock EZGripper command"""
    target_name: str = ""
    seq: int = 0
    stamp_ns: int = 0
    mode: int = 0
    position_pct: float = 0.0
    effort_pct: float = 0.0
    request_ack: bool = False

@dataclass
class EzGripperState:
    """Mock EZGripper state"""
    source_name: str = ""
    seq: int = 0
    stamp_ns: int = 0
    connected: bool = False
    present_position_pct: float = 0.0
    present_effort_pct: float = 0.0
    is_moving: bool = False
    error_code: int = 0

class MockDDSParticipant:
    """Mock DDS participant"""
    def __init__(self, domain: int = 0):
        self.domain = domain
        self.topics: Dict[str, 'MockTopic'] = {}

class MockTopic:
    """Mock DDS topic"""
    def __init__(self, participant: MockDDSParticipant, name: str, msg_type):
        self.participant = participant
        self.name = name
        self.msg_type = msg_type
        participant.topics[name] = self

class MockDataReader:
    """Mock DDS data reader"""
    def __init__(self, participant: MockDDSParticipant, topic: MockTopic):
        self.participant = participant
        self.topic = topic
        self.buffer: List = []
        self.lock = threading.Lock()

    def take(self, N: int = 1) -> List:
        """Take samples from buffer"""
        with self.lock:
            if len(self.buffer) == 0:
                return []
            result = self.buffer[:N]
            self.buffer = self.buffer[N:]
            return result

    def write_sample(self, sample):
        """Write sample to buffer (for testing)"""
        with self.lock:
            self.buffer.append(sample)

class MockDataWriter:
    """Mock DDS data writer"""
    def __init__(self, participant: MockDDSParticipant, topic: MockTopic):
        self.participant = participant
        self.topic = topic
        self.last_written = None
        self.write_count = 0

    def write(self, sample):
        """Write sample"""
        self.last_written = sample
        self.write_count += 1
        print(f"DDS WRITE [{self.topic.name}]: {sample}")

class MockDDS:
    """Mock DDS system for testing"""
    def __init__(self):
        self.participants: List[MockDDSParticipant] = []
        self.readers: Dict[str, MockDataReader] = {}
        self.writers: Dict[str, MockDataWriter] = {}

    def create_participant(self, domain: int = 0) -> MockDDSParticipant:
        """Create mock participant"""
        participant = MockDDSParticipant(domain)
        self.participants.append(participant)
        return participant

    def create_reader(self, participant: MockDDSParticipant, topic_name: str, msg_type) -> MockDataReader:
        """Create mock reader"""
        topic = MockTopic(participant, topic_name, msg_type)
        reader = MockDataReader(participant, topic)
        self.readers[topic_name] = reader
        return reader

    def create_writer(self, participant: MockDDSParticipant, topic_name: str, msg_type) -> MockDataWriter:
        """Create mock writer"""
        topic = MockTopic(participant, topic_name, msg_type)
        writer = MockDataWriter(participant, topic)
        self.writers[topic_name] = writer
        return writer

    def inject_command(self, topic_name: str, cmd):
        """Inject command for testing"""
        if topic_name in self.readers:
            self.readers[topic_name].write_sample(cmd)

# Global mock DDS instance
mock_dds = MockDDS()

# Mock cyclonedds module interface
class MockIdlStruct:
    """Mock IdlStruct base class"""
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()

class MockCycloneDDS:
    """Mock cyclonedds module"""
    def __init__(self):
        self.domain = MockDDSParticipant
        self.topic = MockTopic
        self.sub = type('sub', (), {'DataReader': MockDataReader})()
        self.pub = type('pub', (), {'DataWriter': MockDataWriter})()
        self.qos = type('qos', (), {'Qos': object, 'Policy': object})()
        self.idl = type('idl', (), {'IdlStruct': MockIdlStruct})()

# Install mock cyclonedds
import sys
sys.modules['cyclonedds'] = MockCycloneDDS()
sys.modules['cyclonedds.domain'] = type('domain', (), {'DomainParticipant': MockDDSParticipant})()
sys.modules['cyclonedds.topic'] = type('topic', (), {'Topic': MockTopic})()
sys.modules['cyclonedds.sub'] = type('sub', (), {'DataReader': MockDataReader})()
sys.modules['cyclonedds.pub'] = type('pub', (), {'DataWriter': MockDataWriter})()
sys.modules['cyclonedds.qos'] = type('qos', (), {'Qos': object, 'Policy': object})()
sys.modules['cyclonedds.idl'] = type('idl', (), {'IdlStruct': MockIdlStruct})()

if __name__ == "__main__":
    print("Mock DDS Interface Loaded")
    print("Available topics:", list(mock_dds.readers.keys()), list(mock_dds.writers.keys()))
