#!/bin/bash
# Wrapper script to run driver with clean logs

# Clear previous log
rm -f /tmp/driver_test.log

# Run driver with tee
python3 ezgripper_dds_driver.py --side left --dev /dev/ttyUSB0 2>&1 | tee /tmp/driver_test.log
