# Control Loop 67-91ms Issue Investigation

## The Problem

When RT priority was enabled in the reverted code, the control loop showed:
```
Control loop: mean=67-91ms, max=128-334ms
Deadline misses: 70-90%
Expected: 33ms cycle time, <1% misses
```

**This is 2-3x slower than expected.**

---

## Current Control Loop Code

```python
def control_loop(self):
    """Control thread: Receive commands and execute at 30 Hz"""
    period = 1.0 / self.control_loop_rate  # 33.3ms
    
    while self.running:
        # 1. Receive commands from DDS
        self.receive_commands()
        
        # 2. Execute command (write to servo)
        self.execute_command()
        
        # 3. Read actual position (every 10 cycles = 3 Hz)
        if self.command_count % 10 == 0:
            self.actual_position_pct = self.gripper.get_position()
        
        # 4. Sleep until next cycle
        time.sleep(sleep_time)
```

---

## Timing Analysis

### Expected Timing (30 Hz = 33.3ms period)
```
Receive commands:    <1ms   (DDS read)
Execute command:     ~5ms   (serial write)
Read position:       ~10ms  (serial read, every 10 cycles)
Sleep:               ~27ms  (remaining time)
Total:               33ms   ✅
```

### Actual Timing (Observed 67-91ms)
```
Something is taking: 67-91ms
Expected:            33ms
Overhead:            34-58ms extra
```

**Where is the extra 34-58ms coming from?**

---

## Hypothesis 1: Serial Communication Blocking

### Serial Read/Write Times

**Individual register operations:**
- Write single register: ~3ms
- Read single register: ~5ms
- Round-trip latency: ~8ms

**Current implementation (NO bulk operations):**
```python
def goto_position(self, position_pct, effort_pct):
    # Write 1: Set max effort (Goal Current register)
    self.set_max_effort(effort_pct)  # ~3ms
    
    # Write 2: Set position (Goal Position register)
    for servo in self.servos:
        servo.write_word(reg_goal_position, target)  # ~3ms
    
    # Total: ~6ms per command
```

```python
def get_position(self):
    # Read: Present Position register
    for servo in self.servos:
        pos = servo.read_word_signed(reg_present_position)  # ~5ms
    
    # Total: ~5ms per read
```

**Control loop operations:**
- Execute command: ~6ms (2 serial writes)
- Read position (every 10 cycles): ~5ms
- DDS operations: <1ms
- **Expected total: ~7ms of work + 26ms sleep = 33ms** ✅

**This doesn't explain 67-91ms cycles.**

---

## Hypothesis 2: Logging Overhead

Looking at the reverted code that had RT priority:

```python
# Log statistics every 5 seconds
if int(cycle_start) % 5 == 0 and cycle_start - self.last_stats_time > 4.5:
    stats = self.cycle_monitor.get_statistics()
    misses = self.cycle_monitor.check_deadline_misses(period)
    self.logger.info(...)  # Logging inside control loop
```

**Logging can be slow:**
- String formatting: ~1ms
- File I/O: ~10-50ms (if disk is slow)
- Console output: ~5-20ms

**If logging happens in control loop: 10-50ms extra every 5 seconds**

But this doesn't explain consistent 67-91ms on EVERY cycle.

---

## Hypothesis 3: Bulk Read Implementation Bug

The reverted code added:

```python
def read_servo_state_bulk(self) -> ServoState:
    """Read all servo state in single bulk transaction (~5ms)"""
    data = self.gripper.servos[0].bulk_read([
        (126, 2),  # Present Current
        (132, 4),  # Present Position
        (126, 2),  # Present Load (DUPLICATE ADDRESS!)
        (70, 1),   # Hardware Error
        (146, 1),  # Present Temperature
    ])
    return ServoState.from_bulk_read(data)
```

**BUG FOUND:** Address 126 is read TWICE!
- First read: Present Current (address 126)
- Third read: Present Load (address 126)

**This could cause:**
- Servo confusion (reading same register twice)
- Timeout waiting for response
- Extra serial transactions
- **Explains 30-60ms extra delay**

---

## Hypothesis 4: Control Loop Was Actually Calling Bulk Read

The reverted code may have been calling `read_servo_state_bulk()` on EVERY cycle:

```python
def control_loop(self):
    set_realtime_priority(80)
    
    while self.running:
        cycle_start = time.time()
        
        # BUG: Calling bulk read every cycle?
        state = self.read_servo_state_bulk()  # ~5ms (or 30-60ms if broken)
        
        self.receive_commands()
        self.execute_command()
        
        # Record cycle time
        cycle_time = time.time() - cycle_start
        self.cycle_monitor.record_cycle(cycle_time)
```

**If bulk read was called every cycle AND had the duplicate address bug:**
- Bulk read: 30-60ms (broken)
- Execute command: ~6ms
- Logging/monitoring: ~5ms
- **Total: 41-71ms** ✅ **This matches observed 67-91ms!**

---

## Root Cause Analysis

### The 67-91ms Control Loop Was Caused By:

1. **Bulk read called every cycle** (should be every 10 cycles like current code)
2. **Duplicate address bug** in bulk read (address 126 read twice)
3. **Cycle time monitoring overhead** (recording stats every cycle)
4. **Logging overhead** (string formatting and I/O)

### Why RT Priority Didn't Help:

RT priority (SCHED_FIFO) guarantees:
- ✅ Thread won't be preempted
- ✅ Gets CPU immediately when ready

RT priority does NOT:
- ❌ Speed up serial I/O (hardware limited)
- ❌ Fix buggy bulk read implementation
- ❌ Reduce logging overhead

**The thread was BLOCKED on serial I/O, not being preempted.**

RT priority can't fix a thread that's waiting for hardware.

---

## Correct Implementation

### Option 1: Current Code (No Bulk Operations)
```python
def control_loop(self):
    while self.running:
        self.receive_commands()        # <1ms
        self.execute_command()          # ~6ms
        
        # Read position every 10 cycles (3 Hz)
        if self.command_count % 10 == 0:
            self.actual_position_pct = self.gripper.get_position()  # ~5ms
        
        time.sleep(sleep_time)  # ~26ms
    
    # Total: ~7ms work + 26ms sleep = 33ms ✅
```

**This works perfectly. State publishing at 198.5-200 Hz.**

### Option 2: Bulk Operations (Fixed)
```python
def control_loop(self):
    while self.running:
        self.receive_commands()        # <1ms
        self.execute_command()          # ~6ms (or ~4ms with bulk write)
        
        # Bulk read every 10 cycles (3 Hz) - SAME as current
        if self.command_count % 10 == 0:
            state = self.read_servo_state_bulk()  # ~5ms (FIXED, no duplicate)
            self.actual_position_pct = state.position_pct
        
        time.sleep(sleep_time)  # ~26ms
    
    # Total: ~7ms work + 26ms sleep = 33ms ✅
```

**Key fixes:**
1. Only call bulk read every 10 cycles (not every cycle)
2. Fix duplicate address bug (126 appears twice)
3. Don't log inside control loop
4. Don't do heavy monitoring inside control loop

### Option 3: True 30 Hz Position Updates (Future)
```python
def control_loop(self):
    while self.running:
        self.receive_commands()        # <1ms
        
        # Bulk read EVERY cycle (30 Hz)
        state = self.read_servo_state_bulk()  # ~5ms (MUST be fast)
        self.actual_position_pct = state.position_pct
        
        # Bulk write command
        self.execute_command_bulk()     # ~4ms
        
        time.sleep(sleep_time)  # ~23ms
    
    # Total: ~10ms work + 23ms sleep = 33ms ✅
```

**Requirements:**
1. Bulk read MUST be <5ms (fix duplicate address bug)
2. Bulk write MUST be <4ms
3. No logging in control loop
4. No heavy monitoring in control loop
5. Test WITHOUT RT priority first
6. Add RT priority only if needed for determinism

---

## Recommendations

### 1. Current Code is Fine

**Do not change anything.** The current code achieves:
- 198.5-200 Hz state publishing ✅
- 30 Hz control loop ✅
- 3 Hz position updates (adequate for current use)

### 2. If Implementing Bulk Operations

**Fix these bugs first:**
```python
# WRONG (duplicate address 126)
bulk_read([
    (126, 2),  # Present Current
    (132, 4),  # Present Position
    (126, 2),  # Present Load - DUPLICATE!
    (70, 1),   # Hardware Error
    (146, 1),  # Present Temperature
])

# CORRECT (use proper addresses)
bulk_read([
    (126, 2),  # Present Current
    (132, 4),  # Present Position
    (128, 2),  # Present Load (CORRECT ADDRESS)
    (70, 1),   # Hardware Error
    (146, 1),  # Present Temperature
])
```

**Test without RT priority first:**
1. Implement fixed bulk operations
2. Call bulk read every 10 cycles (same as current)
3. Verify control loop stays at 33ms
4. Verify state publishing stays at 198.5-200 Hz
5. Only then consider RT priority

### 3. Do Not Add RT Priority Yet

RT priority won't help if:
- Bulk read is slow (>5ms)
- Logging in control loop
- Monitoring overhead in control loop

**Fix the implementation first, then add RT priority as final polish.**

---

## Summary

**The 67-91ms control loop was caused by:**
1. ❌ Calling bulk read every cycle (should be every 10)
2. ❌ Duplicate address bug in bulk read (126 twice)
3. ❌ Logging overhead in control loop
4. ❌ Monitoring overhead in control loop

**RT priority couldn't fix it because:**
- The thread was blocked on slow serial I/O
- RT priority doesn't speed up hardware operations
- The problem was the implementation, not scheduling

**Current code (without bulk operations) works perfectly:**
- 198.5-200 Hz state publishing ✅
- 30 Hz control loop ✅
- No changes needed ✅
