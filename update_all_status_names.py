#!/usr/bin/env python3
"""
Script to update all existing violations with new status names:
- Verbal Warning → Warning
- Written Reprimand → Advisory  
- Corrective Reinforcement → Guidance
"""

import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from firebase_config import get_from_firebase, update_in_firebase

def main():
    print("🔄 Updating all violation status names...")
    print("=" * 60)
    print("Status Name Changes:")
    print("• Verbal Warning → Warning")
    print("• Written Reprimand → Advisory")
    print("• Corrective Reinforcement → Guidance")
    print("=" * 60)
    
    try:
        # Get all violations
        violations = get_from_firebase("violations") or []
        print(f"📊 Found {len(violations)} total violations")
        
        # Define status mappings
        status_mappings = {
            "Verbal Warning": "Warning",
            "Written Reprimand": "Advisory", 
            "Corrective Reinforcement": "Guidance"
        }
        
        # Find violations that need updating
        violations_to_update = []
        for violation in violations:
            current_status = violation.get('status', '')
            if current_status in status_mappings:
                violations_to_update.append({
                    'id': violation.get('id'),
                    'current_status': current_status,
                    'new_status': status_mappings[current_status]
                })
        
        print(f"🔍 Found {len(violations_to_update)} violations that need updating")
        
        if not violations_to_update:
            print("✅ No violations need updating - all already use the new status names!")
            return 0
        
        # Update each violation
        updated_count = 0
        for violation_info in violations_to_update:
            violation_id = violation_info['id']
            current_status = violation_info['current_status']
            new_status = violation_info['new_status']
            
            if violation_id:
                try:
                    # Update the status
                    update_data = {'status': new_status}
                    success = update_in_firebase("violations", violation_id, update_data)
                    if success:
                        updated_count += 1
                        print(f"✅ Updated violation {violation_id}: {current_status} → {new_status}")
                    else:
                        print(f"❌ Failed to update violation {violation_id}")
                except Exception as e:
                    print(f"❌ Error updating violation {violation_id}: {e}")
        
        print("=" * 60)
        print(f"✅ Successfully updated {updated_count} violations!")
        print("📊 New Status System:")
        print("   • Warning (1st offense)")
        print("   • Advisory (2nd offense)")
        print("   • Guidance (3rd+ offense)")
        print("=" * 60)
        print("🔄 Please refresh your browser to see the updated statuses.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
