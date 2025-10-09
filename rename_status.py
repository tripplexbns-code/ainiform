#!/usr/bin/env python3
"""
Script to rename 'Written Reprimand & Corrective Reinforcement' to 'Corrective Reinforcement'
"""

import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from firebase_config import get_from_firebase, update_in_firebase

def main():
    print("🔄 Renaming status from 'Written Reprimand & Corrective Reinforcement' to 'Corrective Reinforcement'...")
    print("=" * 70)
    
    try:
        # Get all violations
        violations = get_from_firebase("violations") or []
        print(f"📊 Found {len(violations)} total violations")
        
        # Find violations with the old status name
        old_status = "Written Reprimand & Corrective Reinforcement"
        new_status = "Corrective Reinforcement"
        
        violations_to_update = [v for v in violations if v.get('status') == old_status]
        print(f"🔍 Found {len(violations_to_update)} violations with old status name")
        
        if not violations_to_update:
            print("✅ No violations need updating - all already use the new status name!")
            return 0
        
        # Update each violation
        updated_count = 0
        for violation in violations_to_update:
            violation_id = violation.get('id')
            if violation_id:
                try:
                    # Update the status
                    update_data = {'status': new_status}
                    success = update_in_firebase("violations", violation_id, update_data)
                    if success:
                        updated_count += 1
                        print(f"✅ Updated violation {violation_id}: {old_status} → {new_status}")
                    else:
                        print(f"❌ Failed to update violation {violation_id}")
                except Exception as e:
                    print(f"❌ Error updating violation {violation_id}: {e}")
        
        print("=" * 70)
        print(f"✅ Successfully updated {updated_count} violations!")
        print(f"📊 Status renamed: '{old_status}' → '{new_status}'")
        print("=" * 70)
        print("🔄 Please refresh your browser to see the updated statuses.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
