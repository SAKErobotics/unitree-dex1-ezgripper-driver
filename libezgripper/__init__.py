from .lib_robotis import create_connection, find_servos_on_all_ports
from .ezgripper_base import Gripper
from .config import load_config

# Create EzGripper class for compatibility
class EzGripper(Gripper):
    """EZGripper class - wrapper around Gripper for compatibility"""
    pass

def create_gripper(connection, name, servo_ids, config=None):
    """Helper function to create Gripper with config - prevents missing config errors"""
    if config is None:
        config = load_config()
    return Gripper(connection, name, servo_ids, config)

