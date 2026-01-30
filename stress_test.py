#!/usr/bin/env python3
"""
System stress test to verify real-time control under load
Creates CPU, memory, and disk I/O stress
"""

import multiprocessing
import time
import argparse
import sys

def cpu_stress_worker(duration):
    """CPU-intensive computation"""
    end_time = time.time() + duration
    count = 0
    while time.time() < end_time:
        # CPU-intensive operations
        for i in range(10000):
            _ = i ** 2 * 3.14159 / 2.71828
        count += 1
    return count

def memory_stress_worker(duration, size_mb=100):
    """Memory allocation stress"""
    end_time = time.time() + duration
    arrays = []
    while time.time() < end_time:
        # Allocate and fill memory
        try:
            arr = bytearray(size_mb * 1024 * 1024)
            for i in range(0, len(arr), 4096):
                arr[i] = i % 256
            arrays.append(arr)
            if len(arrays) > 10:
                arrays.pop(0)  # Keep memory pressure constant
        except MemoryError:
            arrays.clear()
        time.sleep(0.1)

def disk_io_stress_worker(duration, file_path="/tmp/stress_test.dat"):
    """Disk I/O stress"""
    end_time = time.time() + duration
    data = b"X" * (1024 * 1024)  # 1 MB chunks
    count = 0
    
    while time.time() < end_time:
        try:
            # Write
            with open(file_path, 'wb') as f:
                for _ in range(10):
                    f.write(data)
            # Read
            with open(file_path, 'rb') as f:
                _ = f.read()
            count += 1
        except Exception as e:
            print(f"I/O error: {e}")
        time.sleep(0.01)
    
    # Cleanup
    try:
        import os
        os.remove(file_path)
    except:
        pass
    
    return count

def run_stress_test(test_type, duration, num_workers):
    """Run stress test with multiple workers"""
    print(f"\n{'='*60}")
    print(f"Starting {test_type.upper()} stress test")
    print(f"Workers: {num_workers}, Duration: {duration}s")
    print(f"{'='*60}\n")
    
    if test_type == "cpu":
        worker_func = cpu_stress_worker
    elif test_type == "memory":
        worker_func = memory_stress_worker
    elif test_type == "disk":
        worker_func = disk_io_stress_worker
    else:
        print(f"Unknown test type: {test_type}")
        return
    
    # Start workers
    pool = multiprocessing.Pool(processes=num_workers)
    start_time = time.time()
    
    try:
        # Run workers
        results = pool.map_async(worker_func, [duration] * num_workers)
        
        # Monitor progress
        while not results.ready():
            elapsed = time.time() - start_time
            remaining = duration - elapsed
            print(f"[{elapsed:.1f}s] {test_type.upper()} stress running... {remaining:.1f}s remaining", end='\r')
            time.sleep(1)
        
        results.get()
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        pool.terminate()
    finally:
        pool.close()
        pool.join()
    
    elapsed = time.time() - start_time
    print(f"\n\n{test_type.upper()} stress test completed in {elapsed:.1f}s")

def run_combined_stress(duration):
    """Run all stress tests simultaneously"""
    print(f"\n{'='*60}")
    print(f"Starting COMBINED stress test (CPU + Memory + Disk I/O)")
    print(f"Duration: {duration}s")
    print(f"{'='*60}\n")
    
    num_cpus = multiprocessing.cpu_count()
    
    # Start all stress types
    pool = multiprocessing.Pool(processes=num_cpus + 4)
    start_time = time.time()
    
    try:
        # CPU stress (use all CPUs)
        cpu_tasks = [pool.apply_async(cpu_stress_worker, (duration,)) for _ in range(num_cpus)]
        
        # Memory stress (2 workers)
        mem_tasks = [pool.apply_async(memory_stress_worker, (duration, 50)) for _ in range(2)]
        
        # Disk I/O stress (2 workers)
        io_tasks = [pool.apply_async(disk_io_stress_worker, (duration, f"/tmp/stress_{i}.dat")) for i in range(2)]
        
        # Monitor progress
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            remaining = duration - elapsed
            cpu_load = num_cpus
            print(f"[{elapsed:.1f}s] COMBINED stress: {cpu_load} CPU + 2 Memory + 2 I/O workers... {remaining:.1f}s remaining", end='\r')
            time.sleep(1)
        
        # Wait for completion
        for task in cpu_tasks + mem_tasks + io_tasks:
            task.get()
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        pool.terminate()
    finally:
        pool.close()
        pool.join()
    
    elapsed = time.time() - start_time
    print(f"\n\nCOMBINED stress test completed in {elapsed:.1f}s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="System stress test for real-time control verification")
    parser.add_argument("--type", choices=["cpu", "memory", "disk", "combined", "all"], default="combined",
                        help="Type of stress test")
    parser.add_argument("--duration", type=int, default=30,
                        help="Duration of each test in seconds")
    parser.add_argument("--workers", type=int, default=None,
                        help="Number of workers (default: CPU count)")
    
    args = parser.parse_args()
    
    if args.workers is None:
        args.workers = multiprocessing.cpu_count()
    
    print(f"System: {multiprocessing.cpu_count()} CPUs available")
    print(f"Stress test configuration:")
    print(f"  Type: {args.type}")
    print(f"  Duration: {args.duration}s per test")
    print(f"  Workers: {args.workers}")
    
    if args.type == "all":
        # Run all tests sequentially
        for test_type in ["cpu", "memory", "disk", "combined"]:
            run_stress_test(test_type, args.duration, args.workers)
            print("\nWaiting 5 seconds before next test...")
            time.sleep(5)
    elif args.type == "combined":
        run_combined_stress(args.duration)
    else:
        run_stress_test(args.type, args.duration, args.workers)
    
    print("\n✅ Stress test complete!")
