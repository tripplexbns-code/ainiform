#!/usr/bin/env python3
"""
Quick test script for BSBA Female model detection
"""

import cv2
from ultralytics import YOLO
import time

def test_female_detection():
    """Test the BSBA Female model detection"""
    print("🚀 Testing BSBA Female Model Detection")
    print("=" * 50)
    
    # Load the female model
    model_path = "bsba_female.pt"
    print(f"📦 Loading model: {model_path}")
    
    try:
        model = YOLO(model_path)
        print("✅ Model loaded successfully!")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return False
    
    # Open camera
    print("📷 Opening camera...")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ Cannot open camera")
        return False
    
    print("✅ Camera opened. Press 'q' to quit.")
    print("🔍 Detection will start in 3 seconds...")
    time.sleep(3)
    
    frame_count = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("⚠️ Failed to grab frame")
                continue
            
            frame_count += 1
            
            # Perform detection
            results = model(frame, conf=0.65)
            
            # Draw bounding boxes
            annotated_frame = results[0].plot()
            
            # Get detected classes
            detected_classes = []
            if results and len(results) > 0 and hasattr(results[0], 'boxes') and results[0].boxes is not None:
                boxes = results[0].boxes
                for box in boxes:
                    conf = box.conf[0].cpu().numpy()
                    cls = int(box.cls[0].cpu().numpy())
                    if conf >= 0.65:
                        class_name = results[0].names.get(cls, f"class_{cls}")
                        detected_classes.append(class_name)
            
            # Print detected classes every 30 frames
            if detected_classes and frame_count % 30 == 0:
                print(f"Frame {frame_count}: Detected {detected_classes}")
            
            # Show the frame
            cv2.imshow("BSBA Female Detection Test", annotated_frame)
            
            # Quit with 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"❌ Error during detection: {e}")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("✅ Test completed!")
    
    return True

if __name__ == "__main__":
    test_female_detection()


