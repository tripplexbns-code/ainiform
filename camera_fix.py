import cv2
import time
import sys

def fix_camera_access():
    """Fix camera access issues by properly releasing and reinitializing"""
    print("🔧 Fixing camera access issues...")
    
    # First, try to release any existing camera captures
    print("1. Releasing any existing camera captures...")
    for i in range(5):  # Try multiple camera indices
        try:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cap.release()
                print(f"   Released camera {i}")
        except:
            pass
    
    # Wait a moment for camera to be fully released
    time.sleep(2)
    
    # Now try to find available cameras
    print("2. Scanning for available cameras...")
    available_cameras = []
    
    for i in range(5):
        print(f"   Testing camera {i}...")
        try:
            # Try different backends
            for backend in [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]:
                cap = cv2.VideoCapture(i, backend)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        print(f"   ✅ Camera {i} (backend {backend}) - WORKING")
                        available_cameras.append((i, backend))
                        cap.release()
                        break
                    else:
                        cap.release()
                else:
                    cap.release()
        except Exception as e:
            print(f"   ❌ Camera {i} - Error: {e}")
    
    if not available_cameras:
        print("❌ No working cameras found!")
        print("💡 Please:")
        print("   - Close all camera applications (Camera app, Zoom, Teams, etc.)")
        print("   - Unplug and replug your external camera")
        print("   - Restart your computer if needed")
        return False
    
    print(f"✅ Found {len(available_cameras)} working camera(s):")
    for cam_id, backend in available_cameras:
        print(f"   Camera {cam_id} (backend {backend})")
    
    # Test the first available camera
    cam_id, backend = available_cameras[0]
    print(f"3. Testing camera {cam_id} with backend {backend}...")
    
    try:
        cap = cv2.VideoCapture(cam_id, backend)
        if cap.isOpened():
            print("   ✅ Camera opened successfully")
            
            # Test frame capture
            for i in range(10):
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"   ✅ Frame {i+1} captured successfully - Shape: {frame.shape}")
                else:
                    print(f"   ❌ Frame {i+1} failed")
                    break
                time.sleep(0.1)
            
            cap.release()
            print("✅ Camera test completed successfully!")
            return True
        else:
            print("❌ Failed to open camera")
            return False
            
    except Exception as e:
        print(f"❌ Camera test failed: {e}")
        return False

if __name__ == "__main__":
    success = fix_camera_access()
    if success:
        print("\n🎉 Camera is ready! You can now run your main application.")
    else:
        print("\n❌ Camera fix failed. Please check the suggestions above.")

