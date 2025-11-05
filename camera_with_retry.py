#!/usr/bin/env python3
"""
Camera with Retry - Handle camera in use scenarios
"""
import cv2
import time
import sys

def test_camera_with_retry():
    """Test camera with retry mechanism for camera in use"""
    print("🔍 Testing Camera with Retry Mechanism...")
    print("=" * 60)
    print("⚠️  Please close your camera app first, then press Enter to continue...")
    input()
    
    # Try different approaches with retry
    for attempt in range(3):
        print(f"\n🔄 Attempt {attempt + 1}/3...")
        
        for camera_index in [0, 1, 2]:
            print(f"  Testing camera index {camera_index}...")
            
            # Try different backends
            backends = [
                (cv2.CAP_MSMF, "Media Foundation"),
                (cv2.CAP_DSHOW, "DirectShow"),
                (cv2.CAP_ANY, "Default")
            ]
            
            for backend, backend_name in backends:
                try:
                    cap = cv2.VideoCapture(camera_index, backend)
                    if cap.isOpened():
                        # Try to read multiple frames
                        success_count = 0
                        for frame_attempt in range(5):
                            ret, frame = cap.read()
                            if ret and frame is not None:
                                success_count += 1
                                if success_count >= 2:  # Need at least 2 successful frames
                                    height, width = frame.shape[:2]
                                    print(f"    ✅ SUCCESS! Camera {camera_index} ({backend_name}): {width}x{height}")
                                    print(f"    📊 Successful frames: {success_count}/5")
                                    
                                    # Test continuous capture
                                    print(f"    🧪 Testing continuous capture...")
                                    for i in range(10):
                                        ret, frame = cap.read()
                                        if ret and frame is not None:
                                            print(f"      Frame {i+1}: ✅")
                                        else:
                                            print(f"      Frame {i+1}: ❌")
                                        time.sleep(0.1)
                                    
                                    cap.release()
                                    return camera_index, backend, backend_name
                            time.sleep(0.1)
                        
                        if success_count > 0:
                            print(f"    ⚠️  Camera {camera_index} ({backend_name}): Partial success ({success_count}/5 frames)")
                        else:
                            print(f"    ❌ Camera {camera_index} ({backend_name}): No frames")
                    
                    cap.release()
                    
                except Exception as e:
                    print(f"    ❌ Camera {camera_index} ({backend_name}): Error - {e}")
        
        if attempt < 2:
            print(f"\n⏳ Waiting 2 seconds before retry...")
            time.sleep(2)
    
    print("\n❌ No working cameras found after all attempts")
    return None, None, None

if __name__ == "__main__":
    camera_index, backend, backend_name = test_camera_with_retry()
    if camera_index is not None:
        print(f"\n🎯 RECOMMENDED SETTINGS:")
        print(f"   Camera Index: {camera_index}")
        print(f"   Backend: {backend_name}")
        print(f"   Backend Code: {backend}")
    else:
        print(f"\n🔧 Please try:")
        print(f"   1. Close all camera applications")
        print(f"   2. Restart your computer")
        print(f"   3. Check camera permissions in Windows Settings")
        print(f"   4. Try a different USB port")

