#!/usr/bin/env python3
"""
Control Loop Speed Benchmark

Measures the actual control loop speed for:
1. Goal Current updates (torque modulation)
2. Goal Position updates
3. Reading position/current feedback
4. Combined read+write cycles

This determines how fast we can modulate holding torque.
"""

import sys
import time
import statistics

sys.path.insert(0, '/home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver')

from libezgripper.config import load_config
from libezgripper import create_connection, Gripper

def benchmark_goal_current_writes(gripper, config, iterations=100):
    """Measure Goal Current write speed (torque modulation)"""
    print(f"\n1. Goal Current Write Speed (Torque Modulation)")
    print(f"   Testing {iterations} rapid current changes...")
    
    times = []
    currents = [300, 400, 500, 600, 700]
    
    for i in range(iterations):
        current = currents[i % len(currents)]
        
        start = time.time()
        data = [current & 0xFF, (current >> 8) & 0xFF]
        gripper.servos[0].write_address(config.reg_goal_current, data)
        elapsed = time.time() - start
        
        times.append(elapsed * 1000)  # Convert to ms
    
    avg_time = statistics.mean(times)
    min_time = min(times)
    max_time = max(times)
    std_dev = statistics.stdev(times)
    
    print(f"   Average: {avg_time:.3f} ms")
    print(f"   Min: {min_time:.3f} ms")
    print(f"   Max: {max_time:.3f} ms")
    print(f"   Std Dev: {std_dev:.3f} ms")
    print(f"   → Max control rate: {1000/avg_time:.1f} Hz")
    
    return avg_time

def benchmark_goal_position_writes(gripper, config, iterations=100):
    """Measure Goal Position write speed"""
    print(f"\n2. Goal Position Write Speed")
    print(f"   Testing {iterations} position commands...")
    
    times = []
    positions = [1000, 1500, 2000, 2500, 3000]
    
    for i in range(iterations):
        pos = positions[i % len(positions)]
        
        start = time.time()
        gripper.servos[0].write_word(config.reg_goal_position, pos)
        elapsed = time.time() - start
        
        times.append(elapsed * 1000)
    
    avg_time = statistics.mean(times)
    min_time = min(times)
    max_time = max(times)
    
    print(f"   Average: {avg_time:.3f} ms")
    print(f"   Min: {min_time:.3f} ms")
    print(f"   Max: {max_time:.3f} ms")
    print(f"   → Max command rate: {1000/avg_time:.1f} Hz")
    
    return avg_time

def benchmark_position_reads(gripper, config, iterations=100):
    """Measure position read speed"""
    print(f"\n3. Position Read Speed (Feedback)")
    print(f"   Testing {iterations} position reads...")
    
    times = []
    
    for i in range(iterations):
        start = time.time()
        pos = gripper.servos[0].read_word_signed(config.reg_present_position)
        elapsed = time.time() - start
        
        times.append(elapsed * 1000)
    
    avg_time = statistics.mean(times)
    min_time = min(times)
    max_time = max(times)
    
    print(f"   Average: {avg_time:.3f} ms")
    print(f"   Min: {min_time:.3f} ms")
    print(f"   Max: {max_time:.3f} ms")
    print(f"   → Max read rate: {1000/avg_time:.1f} Hz")
    
    return avg_time

def benchmark_current_reads(gripper, config, iterations=100):
    """Measure current read speed"""
    print(f"\n4. Current Read Speed (Force Feedback)")
    print(f"   Testing {iterations} current reads...")
    
    times = []
    
    for i in range(iterations):
        start = time.time()
        current_raw = gripper.servos[0].read_word_signed(config.reg_present_current)
        elapsed = time.time() - start
        
        times.append(elapsed * 1000)
    
    avg_time = statistics.mean(times)
    
    print(f"   Average: {avg_time:.3f} ms")
    print(f"   → Max read rate: {1000/avg_time:.1f} Hz")
    
    return avg_time

def benchmark_control_loop(gripper, config, iterations=50):
    """Measure full control loop: read position + read current + write current"""
    print(f"\n5. Full Control Loop (Read Feedback + Update Torque)")
    print(f"   Testing {iterations} complete control cycles...")
    
    times = []
    currents = [300, 400, 500, 600]
    
    for i in range(iterations):
        start = time.time()
        
        # Read feedback
        pos = gripper.servos[0].read_word_signed(config.reg_present_position)
        current = gripper.servos[0].read_word_signed(config.reg_present_current)
        
        # Update torque based on feedback (simulated control logic)
        new_current = currents[i % len(currents)]
        data = [new_current & 0xFF, (new_current >> 8) & 0xFF]
        gripper.servos[0].write_address(config.reg_goal_current, data)
        
        elapsed = time.time() - start
        times.append(elapsed * 1000)
    
    avg_time = statistics.mean(times)
    min_time = min(times)
    max_time = max(times)
    
    print(f"   Average: {avg_time:.3f} ms")
    print(f"   Min: {min_time:.3f} ms")
    print(f"   Max: {max_time:.3f} ms")
    print(f"   → Max control loop rate: {1000/avg_time:.1f} Hz")
    
    return avg_time

def main():
    device = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
    
    print("="*70)
    print("  CONTROL LOOP SPEED BENCHMARK")
    print("="*70)
    print(f"\nDevice: {device}")
    print("Measuring actual control loop performance...")
    
    # Load config and connect
    config = load_config()
    connection = create_connection(dev_name=device, baudrate=config.comm_baudrate)
    gripper = Gripper(connection, 'benchmark', [config.comm_servo_id], config)
    
    print(f"\nConfiguration:")
    print(f"  Baudrate: {config.comm_baudrate} bps")
    print(f"  Return Delay: {config.eeprom_return_delay_time} (optimized)")
    print(f"  Status Return Level: {config.eeprom_status_return_level}")
    
    # Run benchmarks
    current_write_time = benchmark_goal_current_writes(gripper, config)
    position_write_time = benchmark_goal_position_writes(gripper, config)
    position_read_time = benchmark_position_reads(gripper, config)
    current_read_time = benchmark_current_reads(gripper, config)
    control_loop_time = benchmark_control_loop(gripper, config)
    
    # Summary
    print("\n" + "="*70)
    print("  SUMMARY - CONTROL LOOP CAPABILITIES")
    print("="*70)
    
    print(f"\nIndividual Operations:")
    print(f"  Goal Current write:  {current_write_time:.3f} ms ({1000/current_write_time:.1f} Hz)")
    print(f"  Goal Position write: {position_write_time:.3f} ms ({1000/position_write_time:.1f} Hz)")
    print(f"  Position read:       {position_read_time:.3f} ms ({1000/position_read_time:.1f} Hz)")
    print(f"  Current read:        {current_read_time:.3f} ms ({1000/current_read_time:.1f} Hz)")
    
    print(f"\nControl Loop Performance:")
    print(f"  Full cycle (read+write): {control_loop_time:.3f} ms")
    print(f"  Maximum control rate:    {1000/control_loop_time:.1f} Hz")
    
    print(f"\nTorque Modulation Capabilities:")
    max_rate = 1000 / current_write_time
    print(f"  Pure torque updates:     {max_rate:.1f} Hz")
    print(f"  With position feedback:  {1000/control_loop_time:.1f} Hz")
    print(f"  With full feedback:      {1000/control_loop_time:.1f} Hz")
    
    print(f"\nPractical Control Rates:")
    if max_rate > 200:
        print(f"  ✓ Excellent: Can achieve >200 Hz torque modulation")
    elif max_rate > 100:
        print(f"  ✓ Good: Can achieve >100 Hz torque modulation")
    elif max_rate > 50:
        print(f"  ✓ Adequate: Can achieve >50 Hz torque modulation")
    else:
        print(f"  ⚠ Limited: <50 Hz torque modulation")
    
    print(f"\nRecommended Control Rates:")
    print(f"  Position control:   50-100 Hz")
    print(f"  Torque modulation:  100-{int(max_rate*0.8)} Hz")
    print(f"  Force control:      50-100 Hz")
    
    print("\n" + "="*70)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted")
    except Exception as e:
        print(f"\n\nBenchmark failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
