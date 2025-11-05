import cv2
from ultralytics import YOLO
import time
import warnings
import os

# Suppress OpenCV warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

class UniformDetectionService:
    """Detection service that can be used by the main UI"""
    
    def __init__(self, model_path="bsba male2.pt", conf_threshold=0.65):
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        self.cap = None
        self.detection_active = False
        print(f"✅ Detection service initialized with model: {model_path}")
    
    def start_camera(self, camera_index=0):
        """Start camera for detection with better backend handling"""
        # Try different camera backends in order of preference
        # Avoid MSMF backend as it causes frame grab errors
        backends = [
            (cv2.CAP_DSHOW, "DirectShow"),
            (cv2.CAP_ANY, "Any available"),
            (cv2.CAP_V4L2, "V4L2")  # Linux alternative
        ]
        
        camera_opened = False
        for backend, name in backends:
            try:
                print(f"🔍 Trying camera with {name} backend...")
                self.cap = cv2.VideoCapture(camera_index, backend)
                
                if self.cap.isOpened():
                    # Test if we can actually read a frame
                    ret, test_frame = self.cap.read()
                    if ret and test_frame is not None:
                        print(f"✅ Camera opened successfully with {name} backend")
                        camera_opened = True
                        break
                    else:
                        print(f"⚠️ Camera opened but can't read frames with {name}")
                        self.cap.release()
                else:
                    print(f"❌ Camera failed to open with {name}")
            except Exception as e:
                print(f"❌ Error with {name}: {e}")
                if self.cap:
                    self.cap.release()
        
        if not camera_opened:
            print("❌ Cannot open any camera for detection")
            return False
        
        print("✅ Camera opened for detection service.")
        return True
    
    def stop_camera(self):
        """Stop camera"""
        if self.cap:
            self.cap.release()
            self.cap = None
        print("✅ Camera stopped.")
    
    def detect_frame(self, frame):
        """Detect uniform components in a single frame - clean output with only bounding boxes and class names"""
        if self.model is None:
            return None, []
        
        # Perform detection
        results = self.model(frame, conf=self.conf_threshold)
        
        # Get detected classes
        detected_classes = []
        if results and len(results) > 0 and hasattr(results[0], 'boxes') and results[0].boxes is not None:
            boxes = results[0].boxes
            for box in boxes:
                conf = box.conf[0].cpu().numpy()
                cls = int(box.cls[0].cpu().numpy())
                if conf >= self.conf_threshold:
                    class_name = results[0].names.get(cls, f"class_{cls}")
                    detected_classes.append({
                        'class_name': class_name,
                        'confidence': float(conf),
                        'class_id': cls
                    })
        
        # Create clean annotated frame with only bounding boxes and class names
        annotated_frame = frame.copy()
        if results and len(results) > 0 and hasattr(results[0], 'boxes') and results[0].boxes is not None:
            boxes = results[0].boxes
            for box in boxes:
                conf = box.conf[0].cpu().numpy()
                if conf >= self.conf_threshold:
                    # Get box coordinates
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    
                    # Get class name
                    cls = int(box.cls[0].cpu().numpy())
                    class_name = results[0].names.get(cls, f"class_{cls}")
                    
                    # Draw bounding box
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    # Draw class name above the box
                    cv2.putText(annotated_frame, class_name, (x1, y1 - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return annotated_frame, detected_classes
    
    def get_detection_loop(self):
        """Generator that yields detection results for each frame"""
        if not self.cap or not self.cap.isOpened():
            print("❌ Camera not available for detection loop.")
            return
        
        self.detection_active = True
        print("🔍 Starting detection loop...")
        
        consecutive_failures = 0
        max_failures = 10  # Stop after 10 consecutive failures
        
        while self.detection_active:
            ret, frame = self.cap.read()
            if not ret:
                consecutive_failures += 1
                if consecutive_failures <= 3:  # Only print first 3 failures
                    print(f"⚠️ Failed to grab frame (attempt {consecutive_failures})")
                elif consecutive_failures == 4:
                    print("⚠️ Multiple frame grab failures - camera may be in use by another app")
                elif consecutive_failures >= max_failures:
                    print("❌ Too many consecutive failures - stopping detection")
                    break
                time.sleep(0.1)  # Wait before retrying
                continue
            else:
                consecutive_failures = 0  # Reset on success
            
            # Perform detection
            annotated_frame, detected_classes = self.detect_frame(frame)
            
            yield {
                'frame': frame,
                'annotated_frame': annotated_frame,
                'detected_classes': detected_classes,
                'timestamp': time.time()
            }
    
    def stop_detection(self):
        """Stop the detection loop"""
        self.detection_active = False
        print("🛑 Detection stopped.")

# Global detection service instance
detection_service = None

def get_detection_service():
    """Get or create the global detection service"""
    global detection_service
    if detection_service is None:
        detection_service = UniformDetectionService()
    return detection_service

def test_model(model_path, model_name="Model"):
    """Test a specific model"""
    print(f"🧪 Testing {model_name} with model: {model_path}")
    print("=" * 50)
    
    try:
        service = UniformDetectionService(model_path=model_path, conf_threshold=0.65)
        
        if not service.start_camera():
            print("❌ Failed to start camera")
            return False
        
        print("✅ Camera opened. Press 'q' to quit.")
        print(f"🔍 Using {model_name}: {model_path}")
        
        frame_count = 0
        for detection_result in service.get_detection_loop():
            frame_count += 1
            
            # Show output
            cv2.imshow(f"AI-Niform Detection - {model_name}", detection_result['annotated_frame'])
            
            # Print detected classes every 30 frames
            if detection_result['detected_classes'] and frame_count % 30 == 0:
                class_names = [d['class_name'] for d in detection_result['detected_classes']]
                confidences = [f"{d['confidence']:.2f}" for d in detection_result['detected_classes']]
                print(f"Frame {frame_count}: Detected {class_names} (conf: {confidences})")
            
            # Quit with 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        return True
        
    except Exception as e:
        print(f"❌ Error testing {model_name}: {e}")
        return False
    finally:
        service.stop_detection()
        service.stop_camera()
        cv2.destroyAllWindows()

def main():
    """Main function with model selection"""
    import sys
    
    print("🚀 AI-Niform Detection Test")
    print("=" * 50)
    
    # Available models
    models = {
        "1": ("bsba male2.pt", "BSBA Male"),
        "2": ("bsba_female.pt", "BSBA Female"),
        "3": ("bsba_male.pt", "BSBA Male (Original)")
    }
    
    print("Available models:")
    for key, (path, name) in models.items():
        print(f"  {key}. {name} ({path})")
    
    # Get user choice
    choice = input("\nSelect model (1-3) or press Enter for default (BSBA Male): ").strip()
    
    if choice in models:
        model_path, model_name = models[choice]
    else:
        model_path, model_name = models["1"]  # Default to male model
    
    # Check if model file exists
    import os
    if not os.path.exists(model_path):
        print(f"❌ Model file not found: {model_path}")
        print("Available files in current directory:")
        for file in os.listdir("."):
            if file.endswith(".pt"):
                print(f"  - {file}")
        return
    
    # Test the selected model
    success = test_model(model_path, model_name)
    
    if success:
        print(f"\n✅ {model_name} test completed successfully!")
    else:
        print(f"\n❌ {model_name} test failed!")

if __name__ == "__main__":
    main()