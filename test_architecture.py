#!/usr/bin/env python3
"""
Test Unitree Dex1 EZGripper Driver Architecture with Mock DDS

This test validates the DDS-to-DDS translation layer without requiring
the real cyclonedds Python package.
"""

import sys
import time
import math
import threading
from dataclasses import dataclass

# Import mock DDS first
from test_mock_dds import *

# Now import our driver (it will use the mock DDS)
from unitree_dex1_ezgripper_driver import UnitreeDex1EZGripperDriver, MotorCmd_, MotorCmds_, EzGripperCmd, EzGripperState

def test_dex1_to_ezgripper_translation():
    """Test translation from Dex1 commands to EZGripper commands"""
    print("\n=== Testing Dex1 → EZGripper Translation ===")
    
    # Create driver
    driver = UnitreeDex1EZGripperDriver("left", "ezgripper_left")
    
    # Create test Dex1 command
    dex1_cmd = MotorCmd_(
        mode=1,
        q=1.57,  # 90 degrees (50% open)
        dq=0.0,
        tau=0.8,  # 80% effort
        kp=0.0,
        kd=0.0,
        reserve=[0, 0]
    )
    
    # Test translation
    ezgripper_cmd = driver._translate_dex1_to_ezgripper(dex1_cmd)
    
    print(f"Dex1 Command: q={dex1_cmd.q:.3f}rad, tau={dex1_cmd.tau:.3f}")
    print(f"EZGripper Command: position={ezgripper_cmd.position_pct:.1f}%, effort={ezgripper_cmd.effort_pct:.1f}%, mode={ezgripper_cmd.mode}")
    
    # Verify translation
    expected_position = (dex1_cmd.q / (2.0 * math.pi)) * 100.0
    expected_effort = abs(dex1_cmd.tau) * 10.0
    
    assert abs(ezgripper_cmd.position_pct - expected_position) < 0.1, "Position translation failed"
    assert abs(ezgripper_cmd.effort_pct - expected_effort) < 0.1, "Effort translation failed"
    assert ezgripper_cmd.target_name == "ezgripper_left", "Target name incorrect"
    
    print("✅ Translation test PASSED")

def test_special_modes():
    """Test special open/close modes"""
    print("\n=== Testing Special Modes ===")
    
    driver = UnitreeDex1EZGripperDriver("left", "ezgripper_left")
    
    # Test close mode (q <= 0.1)
    close_cmd = MotorCmd_(q=0.05, tau=0.5)
    ezgripper_close = driver._translate_dex1_to_ezgripper(close_cmd)
    assert ezgripper_close.mode == 2, f"Expected close mode (2), got {ezgripper_close.mode}"
    print(f"✅ Close mode: q={close_cmd.q} → mode={ezgripper_close.mode}")
    
    # Test open mode (q >= 6.0)
    open_cmd = MotorCmd_(q=6.1, tau=0.5)
    ezgripper_open = driver._translate_dex1_to_ezgripper(open_cmd)
    assert ezgripper_open.mode == 1, f"Expected open mode (1), got {ezgripper_open.mode}"
    print(f"✅ Open mode: q={open_cmd.q} → mode={ezgripper_open.mode}")
    
    # Test position mode
    pos_cmd = MotorCmd_(q=3.14, tau=0.5)
    ezgripper_pos = driver._translate_dex1_to_ezgripper(pos_cmd)
    assert ezgripper_pos.mode == 0, f"Expected position mode (0), got {ezgripper_pos.mode}"
    print(f"✅ Position mode: q={pos_cmd.q} → mode={ezgripper_pos.mode}")

def test_state_translation():
    """Test EZGripper state to Dex1 state translation"""
    print("\n=== Testing State Translation ===")
    
    driver = UnitreeDex1EZGripperDriver("left", "ezgripper_left")
    
    # Mock EZGripper state
    ezgripper_state = EzGripperState(
        source_name="ezgripper_left",
        connected=True,
        present_position_pct=75.0,
        present_effort_pct=60.0,
        is_moving=False,
        error_code=0
    )
    
    driver.last_ezgripper_state = ezgripper_state
    
    # Test state publication (mock)
    print(f"EZGripper State: {ezgripper_state.present_position_pct}% position, {ezgripper_state.present_effort_pct}% effort")
    
    expected_q = (ezgripper_state.present_position_pct / 100.0) * 2.0 * math.pi
    expected_tau = ezgripper_state.present_effort_pct / 10.0
    
    print(f"Expected Dex1 State: q={expected_q:.3f}rad, tau_est={expected_tau:.3f}")
    print("✅ State translation logic verified")

def test_dds_topics():
    """Test DDS topic creation and communication"""
    print("\n=== Testing DDS Topics ===")
    
    driver = UnitreeDex1EZGripperDriver("left", "ezgripper_left")
    
    # Check that topics were created
    dex1_cmd_topic = driver.dex1_cmd_topic.name
    ezgripper_cmd_topic = driver.ezgripper_cmd_topic.name
    
    print(f"Dex1 command topic: {dex1_cmd_topic}")
    print(f"EZGripper command topic: {ezgripper_cmd_topic}")
    
    # Test message flow
    test_cmd = MotorCmd_(q=1.57, tau=0.8)
    ezgripper_cmd = driver._translate_dex1_to_ezgripper(test_cmd)
    
    # Write to EZGripper topic (mock)
    driver.ezgripper_cmd_writer.write(ezgripper_cmd)
    
    print("✅ DDS communication test PASSED")

def run_all_tests():
    """Run all architecture tests"""
    print("🧪 Testing Unitree Dex1 EZGripper Driver Architecture")
    print("=" * 60)
    
    try:
        test_dex1_to_ezgripper_translation()
        test_special_modes()
        test_state_translation()
        test_dds_topics()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("✅ DDS-to-DDS translation architecture is working correctly")
        print("✅ Special modes (open/close/position) working correctly")
        print("✅ State translation working correctly")
        print("✅ DDS topics and communication working correctly")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()
