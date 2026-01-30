#!/usr/bin/env python3
"""
Script to update all test files from Protocol 1.0 to Protocol 2.0 register addresses
"""

import re
import sys
from pathlib import Path

# Protocol 1 -> Protocol 2 register mappings
REGISTER_MAPPINGS = {
    # Read operations
    r'servo\.read_word\(68\)': 'servo.read_word(126)  # Protocol 2.0: Present Current',
    r'servo\.read_word\(40\)': 'servo.read_word(126)  # Protocol 2.0: Present Current (was Load)',
    r'servo\.read_word\(36\)': 'servo.read_word(132)  # Protocol 2.0: Present Position',
    r'servo\.read_word\(38\)': 'servo.read_word(128)  # Protocol 2.0: Present Velocity',
    r'servo\.read_address\(18,': 'servo.read_address(70,  # Protocol 2.0: Hardware Error Status',
    r'servo\.read_address\(24,': 'servo.read_address(64,  # Protocol 2.0: Torque Enable',
    
    # Write operations - Goal Position
    r'servo\.write_word\(30,': 'servo.write_word(116,  # Protocol 2.0: Goal Position',
    
    # Write operations - Torque/Current Limit
    r'servo\.write_word\(34,': 'servo.write_word(38,  # Protocol 2.0: Current Limit',
    
    # Write operations - Goal Torque/Current
    r'servo\.write_word\(71,': 'servo.write_word(102,  # Protocol 2.0: Goal Current',
    
    # Write operations - Torque Mode Enable -> Operating Mode
    r'servo\.write_address\(70, \[1\]\)': 'servo.write_address(11, [0])  # Protocol 2.0: Operating Mode = Current Control',
    r'servo\.write_address\(70, \[0\]\)': 'servo.write_address(11, [3])  # Protocol 2.0: Operating Mode = Position Control',
    
    # Write operations - Torque Enable
    r'servo\.write_address\(24, \[1\]\)': 'servo.write_address(64, [1])  # Protocol 2.0: Torque Enable',
    r'servo\.write_address\(24, \[0\]\)': 'servo.write_address(64, [0])  # Protocol 2.0: Torque Enable',
    
    # Write operations - Error register
    r'servo\.write_address\(18,': 'servo.write_address(70,  # Protocol 2.0: Hardware Error Status',
}

# Comment updates
COMMENT_UPDATES = {
    r'# Register 68': '# Protocol 2.0: Register 126',
    r'# Register 40': '# Protocol 2.0: Register 126',
    r'# Register 36': '# Protocol 2.0: Register 132',
    r'# Register 30': '# Protocol 2.0: Register 116',
    r'# Register 34': '# Protocol 2.0: Register 38',
    r'# Register 71': '# Protocol 2.0: Register 102',
    r'# Register 70': '# Protocol 2.0: Register 11 (Operating Mode)',
    r'# Register 24': '# Protocol 2.0: Register 64',
    r'# Register 18': '# Protocol 2.0: Register 70',
    r'Protocol 1\.0: Register 68': 'Protocol 2.0: Register 126',
    r'MX-64 Protocol 1\.0': 'MX-64 Protocol 2.0',
}

def update_file(filepath):
    """Update a single test file with Protocol 2.0 register addresses"""
    print(f"Updating {filepath}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Apply register mappings
    for pattern, replacement in REGISTER_MAPPINGS.items():
        content = re.sub(pattern, replacement, content)
    
    # Apply comment updates
    for pattern, replacement in COMMENT_UPDATES.items():
        content = re.sub(pattern, replacement, content)
    
    # Write back if changed
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  ✓ Updated {filepath}")
        return True
    else:
        print(f"  - No changes needed for {filepath}")
        return False

def main():
    # Find all test files
    test_files = [
        'test_mode_characterization.py',
        'test_incremental_torque.py',
        'test_movement_current.py',
        'test_simple_positions.py',
        'test_measure_range.py',
        'test_position_mapping.py',
        'test_spring_pullback.py',
        'test_verify_current.py',
    ]
    
    # Also check for any other test_*.py files
    base_dir = Path(__file__).parent
    all_test_files = list(base_dir.glob('test_*.py'))
    
    # Combine and deduplicate
    all_files = set()
    for f in test_files:
        if (base_dir / f).exists():
            all_files.add(base_dir / f)
    for f in all_test_files:
        all_files.add(f)
    
    # Update each file
    updated_count = 0
    for filepath in sorted(all_files):
        if update_file(filepath):
            updated_count += 1
    
    print(f"\n✓ Updated {updated_count} files")
    print("\nNOTE: Current formula (4.5mA * (value - 2048)) assumed same for Protocol 2.")
    print("      This needs empirical verification after migration!")

if __name__ == '__main__':
    main()
