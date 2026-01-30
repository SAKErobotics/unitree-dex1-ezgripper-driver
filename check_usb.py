#!/usr/bin/env python3
import serial.tools.list_ports

print("USB Serial Devices:")
for port in serial.tools.list_ports.comports():
    print(f"  {port.device}: {port.description}")
