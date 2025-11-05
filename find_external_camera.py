#!/usr/bin/env python3
"""
Find External Camera - More comprehensive detection
"""
import cv2
import time

def find_external_camera():
    """Find the external camera that's working in camera app"""
    print("🔍 Finding External Camera...")
    print("=" * 50)
    
    # Try different approaches
    approaches = [
        ("DirectShow Backend", cv2.CAP_DSHOW),
        ("Media Foundation Backend", cv2.CAP_MSMF),
        ("Default Backend", cv2.CAP_ANY),
        ("OpenCV Backend", cv2.CAP_OPENCV_MJPEG)
    ]
    
    found_cameras = []
    
    for approach_name, backend in approaches:
        print(f"\n📹 Testing {approach_name}...")
        
        for camera_index in range(5):  # Try indices 0-4
            try:
                print(f"  Testing camera index {camera_index}...")
                cap = cv2.VideoCapture(camera_index, backend)
                
                if cap.isOpened():
                    # Try to read a frame
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        height, width = frame.shape[:2]
                        print(f"    ✅ FOUND! Camera {camera_index}: {width}x{height}")
                        found_cameras.append({
                            'index': camera_index,
                            'backend': backend,
                            'backend_name': approach_name,
                            'resolution': f"{width}x{height}"
                        })
                    else:
                        print(f"    ⚠️  Camera {camera_index} opens but no frame")
                else:
                    print(f"    ❌ Camera {camera_index} cannot open")
                
                cap.release()
                time.sleep(0.1)  # Small delay
                
            except Exception as e:
                print(f"    ❌ Camera {camera_index} error: {e}")
    
    print("\n" + "=" * 50)
    if found_cameras:
        print(f"🎯 Found {len(found_cameras)} working camera(s):")
        for i, cam in enumerate(found_cameras):
            print(f"  {i+1}. Index {cam['index']} ({cam['backend_name']}) - {cam['resolution']}")
        
        # Recommend the best one
        best_camera = found_cameras[0]
        print(f"\n💡 Recommended: Use camera index {best_camera['index']} with {best_camera['backend_name']}")
        
        # Test the recommended camera
        print(f"\n🧪 Testing recommended camera...")
        try:
            cap = cv2.VideoCapture(best_camera['index'], best_camera['backend'])
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"✅ SUCCESS! Camera is working properly")
                    print(f"   Resolution: {frame.shape[1]}x{frame.shape[0]}")
                    print(f"   Channels: {frame.shape[2] if len(frame.shape) > 2 else 'Grayscale'}")
                else:
                    print("❌ Camera opens but no frame")
            cap.release()
        except Exception as e:
            print(f"❌ Error testing camera: {e}")
            
    else:
        print("❌ No cameras found!")
        print("\n🔧 Troubleshooting:")
        print("1. Make sure no other apps are using the camera")
        print("2. Try closing camera app and running this test")
        print("3. Check Windows Camera Privacy settings")
        print("4. Try running as administrator")
    
    return found_cameras

if __name__ == "__main__":
    find_external_camera()

