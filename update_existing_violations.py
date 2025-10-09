#!/usr/bin/env python3
"""
Script to update all existing violations with new status system
Run this script to update all existing violations to use the new status names
"""

import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from web_server import update_all_violation_statuses, clear_cache

def main():
    print("🔄 Updating all existing violations with new status system...")
    print("=" * 60)
    print("New Status System:")
    print("• 1st offense → Warning")
    print("• 2nd offense → Advisory")
    print("• 3rd+ offense → Guidance")
    print("=" * 60)
    
    try:
        # Update all violation statuses
        updated_count = update_all_violation_statuses()
        
        # Clear cache
        clear_cache()
        
        print("=" * 60)
        print(f"✅ Successfully updated {updated_count} violations!")
        print("📊 All violations now use the new status system:")
        print("   • Warning (1st offense)")
        print("   • Advisory (2nd offense)")
        print("   • Guidance (3rd+ offense)")
        print("=" * 60)
        print("🔄 Please refresh your browser to see the updated statuses.")
        
    except Exception as e:
        print(f"❌ Error updating violations: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
