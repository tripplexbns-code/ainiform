#!/usr/bin/env python3
"""
Test script for clean camera output with only bounding boxes
"""

import cv2
from detection import UniformDetectionService
import time

def test_clean_detection():
    """Test detection with clean output (only bounding boxes)"""
    print("🧪 Testing Clean Detection Output")
    print("=" * 50)
    
    # Load the female model
    model_path = "bsba_female.pt"
    print(f"📦 Loading model: {model_path}")
    
    try:
        service = UniformDetectionService(model_path=model_path, conf_threshold=0.65)
        
        if not service.start_camera():
            print("❌ Failed to start camera")
            return False
        
        print("✅ Camera opened. Press 'q' to quit.")
        print("🔍 Clean detection active - only bounding boxes will be shown")
        
        frame_count = 0
        for detection_result in service.get_detection_loop():
            frame_count += 1
            
            # Show clean output (only bounding boxes, no text)
            cv2.imshow("Clean Detection - Only Bounding Boxes", detection_result['annotated_frame'])
            
            # Print detected classes every 30 frames (console only)
            if detection_result['detected_classes'] and frame_count % 30 == 0:
                class_names = [d['class_name'] for d in detection_result['detected_classes']]
                confidences = [f"{d['confidence']:.2f}" for d in detection_result['detected_classes']]
                print(f"Frame {frame_count}: Detected {class_names} (conf: {confidences})")
            
            # Quit with 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        return True
        
    except Exception as e:
        print(f"❌ Error during detection: {e}")
        return False
    finally:
        service.stop_detection()
        service.stop_camera()
        cv2.destroyAllWindows()
        print("✅ Clean detection test completed!")

if __name__ == "__main__":
    test_clean_detection()

