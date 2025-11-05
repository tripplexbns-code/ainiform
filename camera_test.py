#!/usr/bin/env python3
"""
Camera Test Script - Check available cameras
"""
import cv2
import sys

def test_cameras():
    """Test all available camera indices"""
    print("🔍 Testing available cameras...")
    print("=" * 50)
    
    available_cameras = []
    
    # Test camera indices from 0 to 5
    for camera_index in range(6):
        print(f"Testing camera index {camera_index}...")
        try:
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    height, width = frame.shape[:2]
                    print(f"✅ Camera {camera_index}: WORKING - Resolution: {width}x{height}")
                    available_cameras.append(camera_index)
                else:
                    print(f"❌ Camera {camera_index}: Opens but no frame")
                cap.release()
            else:
                print(f"❌ Camera {camera_index}: Cannot open")
        except Exception as e:
            print(f"❌ Camera {camera_index}: Error - {e}")
    
    print("=" * 50)
    if available_cameras:
        print(f"🎯 Available cameras: {available_cameras}")
        print(f"💡 Recommended: Use camera index {available_cameras[0]} for external camera")
    else:
        print("❌ No cameras found!")
        print("💡 Make sure your external camera is connected and not being used by another application")
    
    return available_cameras

if __name__ == "__main__":
    test_cameras()

