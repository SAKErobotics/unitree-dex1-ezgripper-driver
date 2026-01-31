#!/usr/bin/env python3
"""
Quick DDS Compliance Validation

Fast validation script for CI/CD and quick checks.
Validates critical DDS communication requirements.
"""

import sys
import time
import argparse
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorStates_

def validate_sake_driver(side: str, domain: int, timeout: float = 5.0):
    """
    Validate SAKE driver DDS compliance
    Returns True if compliant, False otherwise
    """
    print(f"🔍 Validating SAKE Driver DDS Compliance: {side}")
    print(f"⏱️  Timeout: {timeout}s")
    
    # Initialize DDS
    ChannelFactoryInitialize(domain)
    
    # Subscribe to SAKE driver state messages
    state_topic = f"rt/dex1/{side}/state"
    subscriber = ChannelSubscriber(state_topic, MotorStates_)
    subscriber.Init()
    
    print(f"📡 Listening on: {state_topic}")
    
    start_time = time.time()
    message_count = 0
    compliance_errors = []
    
    while time.time() - start_time < timeout:
        state_msg = subscriber.Read()
        
        if state_msg and hasattr(state_msg, 'states') and state_msg.states:
            motor_state = state_msg.states[0]
            message_count += 1
            
            # CRITICAL VALIDATION: q must be in 0-5.4 rad range
            try:
                q_value = float(motor_state.q)
                # Allow small floating-point tolerance (±0.001)
                if not (0.0 <= q_value <= 5.401):
                    compliance_errors.append(f"q={q_value} out of range [0.0, 5.4] - CRITICAL!")
                elif q_value > 5.3:
                    warnings.append(f"q={q_value} is very high ({(q_value/5.4)*100:.1f}%)")
                else:
                    percentage = (q_value / 5.4) * 100.0
                    print(f"✅ Message #{message_count}: q={q_value:.3f} rad ({percentage:.1f}%)")
                    
                    # Additional checks
                    if abs(float(motor_state.q) - float(motor_state.q_raw)) > 0.001:
                        compliance_errors.append(f"q != q_raw")
                        print(f"⚠️  Warning: q != q_raw")
                    
                    if motor_state.mode != 0:
                        print(f"⚠️  Warning: mode={motor_state.mode} (expected 0)")
                
            except (ValueError, TypeError) as e:
                compliance_errors.append(f"Data type error: {e}")
                print(f"❌ Data error: {e}")
            
            # Success after 3 good messages
            if message_count >= 3 and len(compliance_errors) == 0:
                print(f"✅ Compliance validated with {message_count} messages")
                return True
    
    # Timeout or errors
    if message_count == 0:
        print(f"❌ No messages received in {timeout}s")
        print("🚨 Is SAKE driver running?")
    elif compliance_errors:
        print(f"❌ Compliance errors found: {compliance_errors}")
    
    return False

def main():
    parser = argparse.ArgumentParser(description="Quick DDS Compliance Validation")
    parser.add_argument('--side', choices=['left', 'right'], default='left', help="Gripper side")
    parser.add_argument('--domain', type=int, default=0, help="DDS domain ID")
    parser.add_argument('--timeout', type=float, default=5.0, help="Validation timeout")
    
    args = parser.parse_args()
    
    print("🧪 SAKE EZGripper DDS Compliance Validation")
    print("=" * 50)
    
    try:
        success = validate_sake_driver(args.side, args.domain, args.timeout)
        
        if success:
            print("\n🎉 DDS Compliance: PASSED")
            print("✅ SAKE driver is ready for xr_teleoperate")
            sys.exit(0)
        else:
            print("\n❌ DDS Compliance: FAILED")
            print("🚨 Fix DDS issues before use")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n👋 Validation interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
