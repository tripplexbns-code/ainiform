#!/usr/bin/env python3
"""
Script to update existing violations with new status logic
Run this script to fix all existing violations based on violation count
"""

import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from web_server import update_all_violation_statuses, clear_cache

def main():
    print("🔄 Starting violation status update...")
    print("=" * 50)
    
    try:
        # Update all violation statuses
        updated_count = update_all_violation_statuses()
        
        # Clear cache
        clear_cache()
        
        print("=" * 50)
        print(f"✅ Successfully updated {updated_count} violations!")
        print("📊 Status Logic Applied:")
        print("   • 1 violation → Status: Pending")
        print("   • 2-3 violations → Status: Urgent")
        print("   • 4+ violations → Status: Urgent")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Error updating violations: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
