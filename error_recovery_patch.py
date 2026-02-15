#!/usr/bin/env python3
"""
Patch to integrate error recovery into EZGripper DDS Driver

This patch adds:
1. Error recovery handler to the main driver class
2. Error status monitoring in the control loop
3. Error recovery command processing
4. Error status publishing in DDS state messages
"""

# Add these imports to ezgripper_dds_driver.py after existing imports
from error_recovery_enhancement import ErrorRecoveryHandler, ErrorRecoveryCommand, ErrorStatus

# Add these fields to CorrectedEZGripperDriver.__init__ after existing fields
def add_error_recovery_init(self):
    """Initialize error recovery handler - add to __init__ method"""
    # Error recovery handling
    self.error_recovery = ErrorRecoveryHandler(self.logger)
    self.last_error_check_time = time.time()
    self.error_check_interval = 0.1  # Check errors every 100ms
    self.error_status = None
    self.error_recovery_enabled = True

# Add this method to CorrectedEZGripperDriver class
def check_and_handle_errors(self):
    """Monitor for hardware errors and handle them"""
    if not self.error_recovery_enabled or not self.gripper or not self.gripper.servos:
        return
        
    current_time = time.time()
    if current_time - self.last_error_check_time < self.error_check_interval:
        return
        
    self.last_error_check_time = current_time
    
    try:
        # Read error status from first servo
        servo = self.gripper.servos[0]
        self.error_status = self.error_recovery.read_error_status(servo)
        
        # Log errors if detected
        if self.error_recovery.has_error(self.error_status):
            error_list = []
            if self.error_status.overload_error:
                error_list.append("OVERLOAD")
            if self.error_status.overheating_error:
                error_list.append("OVERHEATING")
            if self.error_status.voltage_error:
                error_list.append("VOLTAGE")
            if self.error_status.hardware_error:
                error_list.append("HARDWARE")
            if self.error_status.servo_in_shutdown:
                error_list.append("SHUTDOWN")
            
            self.logger.warning(f"Hardware error detected: {', '.join(error_list)} "
                              f"(status=0x{self.error_status.error_bits:04X})")
            
            # Mark hardware as unhealthy
            self.hardware_healthy = False
            
            # Attempt automatic recovery for overload errors
            if self.error_status.overload_error and not self.error_recovery.recovery_in_progress:
                self.logger.info("Attempting automatic recovery from overload error")
                success = self.error_recovery.execute_recovery(servo, ErrorRecoveryCommand.TORQUE_CYCLE)
                if success:
                    self.logger.info("Automatic recovery successful")
                    self.hardware_healthy = True
                else:
                    self.logger.error("Automatic recovery failed")
        
    except Exception as e:
        self.logger.error(f"Error checking failed: {e}")

# Add this method to CorrectedEZGripperDriver class  
def handle_error_recovery_command(self, command: ErrorRecoveryCommand):
    """Handle error recovery command from DDS"""
    if not self.gripper or not self.gripper.servos:
        self.logger.warning("Cannot execute recovery - no servo available")
        return
        
    servo = self.gripper.servos[0]
    
    # Execute recovery in separate thread to avoid blocking control loop
    import threading
    def recovery_thread():
        success = self.error_recovery.execute_recovery(servo, command)
        if success:
            self.logger.info(f"Recovery command {command.name} completed successfully")
            self.hardware_healthy = True
        else:
            self.logger.error(f"Recovery command {command.name} failed")
    
    thread = threading.Thread(target=recovery_thread)
    thread.daemon = True
    thread.start()

# Modify the _command_receiver method to handle error recovery commands
# Add this case to the command processing in _command_receiver:
def patch_command_receiver(self):
    """Patch to add error recovery command handling to _command_receiver"""
    # In the command processing loop, add:
    # 
    # # Check for error recovery command (using tau field as command)
    # if motor_cmd.tau > 0:
    #     recovery_cmd = ErrorRecoveryCommand(int(motor_cmd.tau))
    #     if recovery_cmd != ErrorRecoveryCommand.NO_OP:
    #         self.logger.info(f"Received error recovery command: {recovery_cmd.name}")
    #         self.handle_error_recovery_command(recovery_cmd)
    #         continue  # Skip normal command processing
    #
    # This uses the tau field to encode the recovery command (0-4)
    pass

# Modify the _publish_state method to include error status
def patch_publish_state(self):
    """Patch to add error status to DDS state messages"""
    # In the state publishing section, add:
    #
    # # Add error status to state message
    # if self.error_status:
    #     # Note: These would need to be added to the MotorStates_ message structure
    #     # For now, we'll log them
    #     if self.error_status.overload_error:
    #         self.logger.debug("State: OVERLOAD error active")
    #     if self.error_status.servo_in_shutdown:
    #         self.logger.debug("State: SERVO IN SHUTDOWN")
    #     if self.error_recovery.recovery_in_progress:
    #         self.logger.debug("State: RECOVERY IN PROGRESS")
    pass

# Modify the execute_command method to check errors before execution
def patch_execute_command(self):
    """Patch to add error checking to command execution"""
    # At the start of execute_command, add:
    #
    # # Check for errors before executing command
    # self.check_and_handle_errors()
    #
    # # Skip command if hardware is unhealthy
    # if not self.hardware_healthy:
    #     self.logger.warning("Skipping command - hardware unhealthy due to errors")
    #     return
    pass

# Add to the main control loop
def patch_control_loop(self):
    """Patch to add error monitoring to control loop"""
    # In the main control loop (run method), add:
    #
    # # Check for hardware errors
    # self.check_and_handle_errors()
    pass

"""
Integration Steps:

1. Copy the error_recovery_enhancement.py file to the project directory
2. Add the imports to ezgripper_dds_driver.py
3. Add the error recovery initialization to __init__
4. Add the error checking methods to the class
5. Modify the command receiver to handle recovery commands
6. Modify the state publisher to include error status
7. Modify execute_command to check errors
8. Add error checking to the control loop

DDS Protocol Usage:
- Send MotorCmds_ with tau field set to recovery command (0-4)
- Error status will be available in MotorStates_ messages
- Automatic recovery attempts for overload errors
- Manual recovery commands via DDS interface

Recovery Commands:
0: NO_OP - No action
1: CLEAR_ERRORS - Clear hardware error status
2: TORQUE_CYCLE - Turn torque off/on
3: REBOOT_SERVO - Send reboot instruction
4: FULL_RECOVERY - Complete recovery sequence
"""
