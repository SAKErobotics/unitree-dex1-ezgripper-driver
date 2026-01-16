from .lib_robotis import create_connection, find_servos_on_all_ports
from .ezgripper_base import Gripper

# Create EzGripper class for compatibility
class EzGripper(Gripper):
    """EZGripper class - wrapper around Gripper for compatibility"""
    pass

