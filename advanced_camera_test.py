#!/usr/bin/env python3
"""
Advanced Camera Test Script - Multiple detection methods
"""
import cv2
import sys
import time

def test_camera_detection():
    """Test camera detection with multiple methods"""
    print("🔍 Advanced Camera Detection Test")
    print("=" * 60)
    
    # Method 1: Try different backends
    backends = [
        (cv2.CAP_DSHOW, "DirectShow"),
        (cv2.CAP_MSMF, "Media Foundation"),
        (cv2.CAP_ANY, "Any Available")
    ]
    
    available_cameras = []
    
    for backend_id, backend_name in backends:
        print(f"\n📹 Testing with {backend_name} backend...")
        for camera_index in range(3):
            try:
                cap = cv2.VideoCapture(camera_index, backend_id)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        height, width = frame.shape[:2]
                        print(f"✅ Camera {camera_index} ({backend_name}): {width}x{height}")
                        available_cameras.append((camera_index, backend_id, backend_name))
                    cap.release()
            except Exception as e:
                pass
    
    # Method 2: Try with different parameters
    print(f"\n📹 Testing with different parameters...")
    for camera_index in range(3):
        try:
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                # Try to set some properties
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                ret, frame = cap.read()
                if ret and frame is not None:
                    height, width = frame.shape[:2]
                    print(f"✅ Camera {camera_index} (with params): {width}x{height}")
                    available_cameras.append((camera_index, cv2.CAP_ANY, "Default"))
                cap.release()
        except Exception as e:
            pass
    
    print("\n" + "=" * 60)
    if available_cameras:
        print(f"🎯 Found {len(available_cameras)} working camera(s):")
        for i, (cam_idx, backend_id, backend_name) in enumerate(available_cameras):
            print(f"   {i+1}. Camera index {cam_idx} ({backend_name})")
        print(f"\n💡 Recommended: Use camera index {available_cameras[0][0]}")
    else:
        print("❌ No cameras detected!")
        print("\n🔧 Troubleshooting steps:")
        print("1. Make sure your external camera is properly connected")
        print("2. Check if camera is being used by another application (Zoom, Teams, etc.)")
        print("3. Try unplugging and reconnecting the camera")
        print("4. Check Windows Device Manager for camera issues")
        print("5. Restart your computer")
        print("6. Try a different USB port")
    
    return available_cameras

if __name__ == "__main__":
    test_camera_detection()

