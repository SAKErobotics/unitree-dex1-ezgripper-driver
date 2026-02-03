#!/usr/bin/env python3
"""
Apply the critical fix to get_error_details() and verify it persists
"""

import os
import sys

def apply_fix():
    filepath = 'ezgripper_dds_driver.py'
    
    print("🔧 Applying critical fix to get_error_details()...")
    
    # Read current content
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Define the broken function
    old_function = '''    def get_error_details(self):
        """Get current error details from cached sensor data"""
        return self.current_sensor_data.get('error_details', {'errors': []})'''
    
    # Define the fixed function
    new_function = '''    def get_error_details(self):
        """Get current error details from cached sensor data"""
        if not self.current_sensor_data:
            return {'has_error': False, 'errors': []}
        
        # Get error code from sensor data (not error_details)
        error_code = self.current_sensor_data.get('error', 0)
        has_error = error_code != 0
        errors = []
        if has_error:
            errors.append(f"Hardware error code: {error_code}")
        
        return {'has_error': has_error, 'errors': errors}'''
    
    # Check if fix already applied
    if "return {'has_error': has_error, 'errors': errors}" in content:
        print("✅ Fix already applied!")
        return True
    
    # Check if old function exists
    if old_function not in content:
        print("❌ Old function not found - file may have been modified")
        print("Please manually apply the fix from the instructions")
        return False
    
    # Apply the fix
    content = content.replace(old_function, new_function)
    
    # Write back
    with open(filepath, 'w') as f:
        f.write(content)
    
    print("✅ Fix applied successfully!")
    
    # Verify
    with open(filepath, 'r') as f:
        verify_content = f.read()
    
    if "return {'has_error': has_error, 'errors': errors}" in verify_content:
        print("✅ VERIFIED: Fix is persistent in file")
        return True
    else:
        print("❌ VERIFICATION FAILED: Fix not found after write")
        return False

if __name__ == '__main__':
    os.chdir('/home/sokul/CascadeProjects/unitree-dex1-ezgripper-driver')
    
    if apply_fix():
        print("\n📋 Next steps:")
        print("1. Close the file in your IDE if open")
        print("2. Reopen it to see the changes")
        print("3. Commit to git:")
        print("   git add ezgripper_dds_driver.py")
        print('   git commit -m "Fix get_error_details KeyError blocking position updates"')
        print("4. Test the driver:")
        print("   pkill -9 -f ezgripper")
        print("   python3 ezgripper_dds_driver.py --side left --log-level INFO &")
        print("   sleep 5")
        print("   python3 test_gripper_movement.py left")
        sys.exit(0)
    else:
        sys.exit(1)
