#!/usr/bin/env python3
"""
Quick debug script to see what DDS messages we're actually publishing
"""

import time
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import MotorStates_

def debug_dds_messages(side='left', domain=0, count=10):
    ChannelFactoryInitialize(domain)
    
    state_topic = f"rt/dex1/{side}/state"
    subscriber = ChannelSubscriber(state_topic, MotorStates_)
    subscriber.Init()
    
    print(f"🔍 Debug: Listening to {state_topic}")
    print(f"📊 Collecting {count} messages...")
    
    messages = []
    while len(messages) < count:
        state_msg = subscriber.Read()
        
        if state_msg and hasattr(state_msg, 'states') and state_msg.states:
            motor_state = state_msg.states[0]
            messages.append(motor_state)
            
            q_val = float(motor_state.q)
            q_raw_val = float(motor_state.q_raw)
            
            print(f"Message #{len(messages)}:")
            print(f"  q: {q_val} rad ({(q_val/5.4)*100:.1f}% if valid)")
            print(f"  q_raw: {q_raw_val}")
            print(f"  mode: {motor_state.mode}")
            print(f"  tau_est: {motor_state.tau_est}")
            
            # Check if this looks like percentage (bad) or radians (good)
            if q_val > 10.0:
                print(f"  ❌ LIKELY PERCENTAGE: {q_val} (should be 0-5.4 rad)")
            elif 0.0 <= q_val <= 5.4:
                print(f"  ✅ CORRECT RADIANS: {q_val}")
            else:
                print(f"  ⚠️  UNUSUAL VALUE: {q_val}")
            print()
    
    return messages

if __name__ == "__main__":
    debug_dds_messages()
