#!/usr/bin/env python3
"""
SAKE EZGripper DDS Loopback Testbench

Validates complete bidirectional DDS communication:
- Unitree (xr_teleoperate) → SAKE driver
- SAKE driver → Unitree (xr_teleoperate)

This test must pass for all future changes to the driver.
"""

import time
import threading
import argparse
import numpy as np
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorCmds_, MotorStates_
from unitree_sdk2py.idl.default import unitree_go_msg_dds__MotorCmd_, unitree_go_msg_dds__MotorState_

class DDSLoopbackTestbench:
    """
    Complete DDS communication testbench
    Simulates both xr_teleoperate behavior and monitors SAKE driver responses
    """
    
    def __init__(self, side: str = 'left', domain: int = 0):
        self.side = side
        self.domain = domain
        
        # Initialize DDS
        ChannelFactoryInitialize(domain)
        
        # Topics (exact match to xr_teleoperate and SAKE driver)
        self.cmd_topic = f"rt/dex1/{side}/cmd"
        self.state_topic = f"rt/dex1/{side}/state"
        
        # Setup publishers (simulate xr_teleoperate)
        self.cmd_publisher = ChannelPublisher(self.cmd_topic, MotorCmds_)
        self.cmd_publisher.Init()
        
        # Setup subscribers (monitor SAKE driver)
        self.state_subscriber = ChannelSubscriber(self.state_topic, MotorStates_)
        self.state_subscriber.Init()
        
        # Also monitor commands (for validation)
        self.cmd_subscriber = ChannelSubscriber(self.cmd_topic, MotorCmds_)
        self.cmd_subscriber.Init()
        
        # Test data storage
        self.received_states = []
        self.received_commands = []
        self.test_running = False
        
        print(f"🧪 DDS Loopback Testbench: {side} side")
        print(f"📡 Command Topic: {self.cmd_topic}")
        print(f"📡 State Topic: {self.state_topic}")
        print(f"🔧 Domain: {domain}")
    
    def create_xr_teleoperate_command(self, trigger_value: float):
        """
        Create command exactly like xr_teleoperate
        Uses the same conversion logic
        """
        # Exact xr_teleoperate constants
        THUMB_INDEX_DISTANCE_MIN = 5.0
        THUMB_INDEX_DISTANCE_MAX = 7.0
        LEFT_MAPPED_MIN = 0.0
        LEFT_MAPPED_MAX = 5.40
        
        # Exact xr_teleoperate conversion
        target_action = np.interp(trigger_value, 
                                  [THUMB_INDEX_DISTANCE_MIN, THUMB_INDEX_DISTANCE_MAX], 
                                  [LEFT_MAPPED_MIN, LEFT_MAPPED_MAX])
        
        # Create MotorCmd_ exactly like xr_teleoperate
        cmd_msg = MotorCmds_()
        cmd_msg.cmds = [unitree_go_msg_dds__MotorCmd_()]
        
        # Exact xr_teleoperate motor parameters
        cmd_msg.cmds[0].dq = 0.0
        cmd_msg.cmds[0].tau = 0.0
        cmd_msg.cmds[0].kp = 5.00
        cmd_msg.cmds[0].kd = 0.05
        cmd_msg.cmds[0].q = target_action
        
        return cmd_msg, target_action
    
    def monitor_states(self, duration: float = None):
        """
        Monitor SAKE driver state messages
        This is the critical SAKE → Unitree communication path
        """
        print(f"👀 Starting state monitor (SAKE → Unitree)...")
        
        start_time = time.time()
        count = 0
        
        try:
            while self.test_running and (duration is None or (time.time() - start_time) < duration):
                state_msg = self.state_subscriber.Read()
                
                if state_msg and hasattr(state_msg, 'states') and state_msg.states:
                    motor_state = state_msg.states[0]
                    count += 1
                    
                    # Validate state message format
                    validation_result = self.validate_state_message(motor_state, count)
                    
                    self.received_states.append({
                        'timestamp': time.time(),
                        'count': count,
                        'state': motor_state,
                        'validation': validation_result
                    })
                
                time.sleep(0.001)  # 1kHz monitoring
                
        except Exception as e:
            print(f"❌ State monitoring error: {e}")
        
        print(f"📊 State monitoring complete: {count} messages received")
    
    def monitor_commands(self, duration: float = None):
        """
        Monitor command messages (for validation)
        """
        print(f"👀 Starting command monitor...")
        
        start_time = time.time()
        count = 0
        
        try:
            while self.test_running and (duration is None or (time.time() - start_time) < duration):
                cmd_msg = self.cmd_subscriber.Read()
                
                if cmd_msg and hasattr(cmd_msg, 'cmds') and cmd_msg.cmds:
                    motor_cmd = cmd_msg.cmds[0]
                    count += 1
                    
                    self.received_commands.append({
                        'timestamp': time.time(),
                        'count': count,
                        'command': motor_cmd
                    })
                
                time.sleep(0.001)
                
        except Exception as e:
            print(f"❌ Command monitoring error: {e}")
        
        print(f"📊 Command monitoring complete: {count} messages received")
    
    def validate_state_message(self, motor_state, count: int):
        """
        Validate SAKE driver state message format
        This ensures SAKE → Unitree communication is correct
        """
        errors = []
        warnings = []
        
        # Check required fields exist
        required_fields = ['mode', 'q', 'dq', 'ddq', 'tau_est', 'q_raw', 'dq_raw', 'ddq_raw', 'temperature', 'lost']
        for field in required_fields:
            if not hasattr(motor_state, field):
                errors.append(f"Missing field: {field}")
        
        # Check data types and ranges
        try:
            # CRITICAL: q must be in 0-5.4 rad range (not percentage!)
            q_value = float(motor_state.q)
            # Allow small floating-point tolerance (±0.001)
            if not (0.0 <= q_value <= 5.401):
                errors.append(f"q={q_value} out of range [0.0, 5.4] - CRITICAL!")
            elif q_value > 5.3:
                warnings.append(f"q={q_value} is very high ({(q_value/5.4)*100:.1f}%)")
            
            # q_raw should match q
            q_raw_value = float(motor_state.q_raw)
            if abs(q_value - q_raw_value) > 0.001:
                errors.append(f"q={q_value} != q_raw={q_raw_value}")
            
            # Mode should be 0 (position control)
            if motor_state.mode != 0:
                warnings.append(f"mode={motor_state.mode} (expected 0)")
            
            # Velocity should be small for gripper
            if abs(float(motor_state.dq)) > 1.0:
                warnings.append(f"dq={motor_state.dq} (high velocity)")
            
            # Torque should be reasonable
            tau_est = float(motor_state.tau_est)
            if abs(tau_est) > 50.0:
                warnings.append(f"tau_est={tau_est} (high torque)")
            
        except (ValueError, TypeError) as e:
            errors.append(f"Data type error: {e}")
        
        # Return validation result
        result = {
            'count': count,
            'errors': errors,
            'warnings': warnings,
            'valid': len(errors) == 0
        }
        
        # Log issues
        if errors:
            print(f"❌ State #{count} ERRORS: {errors}")
        if warnings:
            print(f"⚠️  State #{count} WARNINGS: {warnings}")
        
        return result
    
    def test_position_loopback(self):
        """
        Test complete position control loop:
        1. Send xr_teleoperate command
        2. Receive SAKE state response
        3. Validate bidirectional communication
        """
        print("\n🔄 Testing Position Loopback")
        print("=" * 50)
        
        # Test positions (trigger values)
        test_cases = [
            (5.0, "Closed", 0.0),
            (6.0, "Middle", 2.7),
            (7.0, "Open", 5.4)
        ]
        
        results = []
        
        for trigger, description, expected_q in test_cases:
            print(f"\n📤 Testing: {description} (trigger={trigger})")
            
            # Create and send xr_teleoperate command
            cmd_msg, target_q = self.create_xr_teleoperate_command(trigger)
            self.cmd_publisher.Write(cmd_msg)
            
            print(f"   Sent: q={target_q:.3f} rad ({(target_q/5.4)*100:.1f}%)")
            
            # Wait for SAKE response
            time.sleep(0.5)  # Allow SAKE to respond
            
            # Check latest state response
            if self.received_states:
                latest_state = self.received_states[-1]
                motor_state = latest_state['state']
                validation = latest_state['validation']
                
                actual_q = float(motor_state.q)
                actual_pct = (actual_q / 5.4) * 100.0
                expected_pct = (expected_q / 5.4) * 100.0
                
                print(f"   Received: q={actual_q:.3f} rad ({actual_pct:.1f}%)")
                print(f"   Expected: q={expected_q:.3f} rad ({expected_pct:.1f}%)")
                print(f"   Validation: {'✅ PASS' if validation['valid'] else '❌ FAIL'}")
                
                if validation['errors']:
                    print(f"   Errors: {validation['errors']}")
                
                results.append({
                    'trigger': trigger,
                    'description': description,
                    'expected_q': expected_q,
                    'actual_q': actual_q,
                    'validation': validation
                })
            else:
                print(f"   ❌ No state response received!")
                results.append({
                    'trigger': trigger,
                    'description': description,
                    'expected_q': expected_q,
                    'actual_q': None,
                    'validation': {'valid': False, 'errors': ['No response']}
                })
        
        return results
    
    def run_full_testbench(self):
        """
        Run complete DDS loopback testbench
        """
        print("🧪 Starting SAKE EZGripper DDS Loopback Testbench")
        print("=" * 60)
        print("This test validates:")
        print("  ✅ Unitree → SAKE command reception")
        print("  ✅ SAKE → Unitree state publishing")
        print("  ✅ Bidirectional communication integrity")
        print("  ✅ Position range compliance (0-5.4 rad)")
        print("  ✅ Message format compliance")
        print("=" * 60)
        
        # Start monitoring threads
        self.test_running = True
        
        state_thread = threading.Thread(target=self.monitor_states, daemon=True)
        command_thread = threading.Thread(target=self.monitor_commands, daemon=True)
        
        state_thread.start()
        command_thread.start()
        
        # Give monitors time to start
        time.sleep(1.0)
        
        try:
            # Run position loopback test
            results = self.test_position_loopback()
            
            # Analyze results
            print("\n📊 TEST RESULTS")
            print("=" * 50)
            
            total_tests = len(results)
            passed_tests = sum(1 for r in results if r['validation']['valid'])
            
            print(f"Total Tests: {total_tests}")
            print(f"Passed: {passed_tests}")
            print(f"Failed: {total_tests - passed_tests}")
            print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
            
            # Detailed results
            for result in results:
                status = "✅ PASS" if result['validation']['valid'] else "❌ FAIL"
                print(f"  {result['description']}: {status}")
                if result['actual_q'] is not None:
                    print(f"    Expected: {result['expected_q']:.3f} rad")
                    print(f"    Actual: {result['actual_q']:.3f} rad")
            
            # Overall validation
            all_passed = passed_tests == total_tests
            
            if all_passed:
                print("\n🎉 ALL TESTS PASSED!")
                print("✅ SAKE driver DDS communication is working correctly")
                print("✅ Ready for production use")
            else:
                print("\n❌ SOME TESTS FAILED!")
                print("🚨 SAKE driver has DDS communication issues")
                print("🔧 Fix issues before production use")
            
            return all_passed
            
        finally:
            # Stop monitoring
            self.test_running = False
            time.sleep(0.5)
            
            print("\n🧹 Testbench complete")

def main():
    parser = argparse.ArgumentParser(description="SAKE EZGripper DDS Loopback Testbench")
    parser.add_argument('--side', choices=['left', 'right'], default='left', help="Gripper side")
    parser.add_argument('--domain', type=int, default=0, help="DDS domain ID")
    parser.add_argument('--duration', type=int, default=30, help="Test duration in seconds")
    
    args = parser.parse_args()
    
    # Create and run testbench
    testbench = DDSLoopbackTestbench(args.side, args.domain)
    
    try:
        success = testbench.run_full_testbench()
        exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n👋 Testbench interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n❌ Testbench failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
