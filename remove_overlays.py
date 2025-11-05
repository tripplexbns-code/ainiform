#!/usr/bin/env python3
"""
Script to remove all text overlays from Final guard_ui_2.py
"""

import re

def remove_text_overlays():
    """Remove all text overlay code from the file"""
    
    # Read the file
    with open("Final guard_ui_2.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Remove all cv2.putText calls
    content = re.sub(r'cv2\.putText\([^)]+\);?\s*\n?', '', content)
    
    # Remove all cv2.rectangle overlay calls
    content = re.sub(r'cv2\.rectangle\([^)]+overlay[^)]+\);?\s*\n?', '', content)
    
    # Remove all cv2.addWeighted calls
    content = re.sub(r'cv2\.addWeighted\([^)]+\);?\s*\n?', '', content)
    
    # Remove font definitions
    content = re.sub(r'font\s*=\s*cv2\.FONT_HERSHEY_SIMPLEX\s*\n?', '', content)
    
    # Remove overlay variable definitions
    content = re.sub(r'overlay\s*=\s*[^;]+;?\s*\n?', '', content)
    
    # Write the cleaned file
    with open("Final guard_ui_2_clean.py", "w", encoding="utf-8") as f:
        f.write(content)
    
    print("✅ Removed text overlays from Final guard_ui_2.py")
    print("📁 Clean file saved as: Final guard_ui_2_clean.py")

if __name__ == "__main__":
    remove_text_overlays()

