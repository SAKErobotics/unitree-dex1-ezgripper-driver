#!/usr/bin/env python3
"""Check actual servo operating mode and configuration"""

from libezgripper import create_connection
from libezgripper.lib_robotis import Robotis_Servo

connection = create_connection('/dev/ttyUSB0')
servo = Robotis_Servo(connection, 1)

print("=" * 60)
print("SERVO CONFIGURATION CHECK")
print("=" * 60)

# Read operating mode (register 11)
operating_mode = servo.read_byte(11)
print(f"\nOperating Mode (register 11): {operating_mode}")
mode_names = {
    0: "Current Control",
    1: "Velocity Control", 
    3: "Position Control",
    4: "Extended Position Control",
    5: "Current-based Position Control",
    16: "PWM Control"
}
print(f"  Mode name: {mode_names.get(operating_mode, 'Unknown')}")

# Read torque enable
torque = servo.read_byte(64)
print(f"\nTorque Enable (register 64): {torque}")

# Read current limit
current_limit = servo.read_word(38)
print(f"\nCurrent Limit (register 38): {current_limit} mA")

# Read profile velocity
profile_vel = servo.read_word(112)
print(f"\nProfile Velocity (register 112): {profile_vel}")

# Read profile acceleration  
profile_accel = servo.read_word(108)
print(f"\nProfile Acceleration (register 108): {profile_accel}")

print("\n" + "=" * 60)
