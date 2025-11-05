#!/usr/bin/env python3
"""
Test script to verify detection service connection to camera feed
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_detection_connection():
    """Test if detection service properly connects to camera feed"""
    try:
        print("🧪 Testing detection service connection...")
        
        # Import the detection service
        from detection import UniformDetectionService
        
        # Create detection service instance
        detection_service = UniformDetectionService(
            model_path="bsba male2.pt",
            conf_threshold=0.5
        )
        
        print("✅ Detection service created successfully")
        
        # Test camera initialization
        if detection_service.start_camera():
            print("✅ Camera started successfully")
            
            # Test detection loop
            frame_count = 0
            for detection_result in detection_service.get_detection_loop():
                frame_count += 1
                annotated_frame = detection_result['annotated_frame']
                detected_classes = detection_result['detected_classes']
                
                print(f"📹 Frame {frame_count}: {len(detected_classes)} detections")
                
                if detected_classes:
                    for detection in detected_classes:
                        print(f"   🔍 {detection['class_name']} (conf: {detection['confidence']:.2f})")
                
                # Stop after 10 frames for testing
                if frame_count >= 10:
                    break
            
            # Stop camera
            detection_service.stop_camera()
            print("✅ Camera stopped successfully")
            
        else:
            print("❌ Failed to start camera")
            
    except Exception as e:
        print(f"❌ Error testing detection connection: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_detection_connection()

