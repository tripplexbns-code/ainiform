import cv2
from ultralytics import YOLO
import time

def test_integrated_detection():
    """Test the integrated YOLO detection with your working code"""
    print("🧪 Testing integrated YOLO detection...")
    
    try:
        # Load your trained YOLO model (using bsba_male.pt since shs_male.pt not found)
        model = YOLO("bsba_male.pt")
        print("✅ Model loaded successfully")
        
        # Open camera with working configuration
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Use DirectShow backend
        
        if not cap.isOpened():
            print("❌ Cannot open camera.")
            return False
        
        print("✅ Camera opened successfully. Press 'q' to quit.")
        
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                print("⚠️ Failed to grab frame.")
                break 
            
            frame_count += 1
            print(f"📸 Frame {frame_count} captured - Shape: {frame.shape}")
            
            # Perform detection using your integrated code
            results = model(frame, conf=0.65)
            
            # Draw bounding boxes using your method
            annotated_frame = results[0].plot()
            
            # Show output
            cv2.imshow("Integrated AI Detection Test", annotated_frame)
            
            # Print detection info
            if results and len(results) > 0 and hasattr(results[0], 'boxes') and results[0].boxes is not None:
                boxes = results[0].boxes
                print(f"🔍 Detected {len(boxes)} objects in frame {frame_count}")
                for i, box in enumerate(boxes):
                    conf = box.conf[0].cpu().numpy()
                    cls = int(box.cls[0].cpu().numpy())
                    print(f"   Object {i+1}: Class {cls}, Confidence: {conf:.2f}")
            
            # Quit with 'q' or after 10 frames for testing
            if cv2.waitKey(1) & 0xFF == ord('q') or frame_count >= 10:
                break
        
        cap.release()
        cv2.destroyAllWindows()
        print("✅ Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_integrated_detection()
    if success:
        print("\n🎉 Integrated detection test passed!")
    else:
        print("\n❌ Integrated detection test failed.")

