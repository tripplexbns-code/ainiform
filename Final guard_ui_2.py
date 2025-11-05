# guard_ui_2.py
# Simplified and robust Guard Control Center

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import time
from datetime import datetime
import sys
import os
import traceback
from collections import defaultdict, deque
import platform

# Optional imports with fallbacks
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("WARNING: OpenCV not available - camera features disabled")

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("WARNING: YOLO not available - AI detection disabled")

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("WARNING: Firebase not available - running in offline mode")

# ---------------- UNIFORM DETECTION CONFIG ----------------
# WINDOW_SECONDS removed for no-timeout detection
STAY_DISPLAY_SECONDS = 2     # time to show result
MIN_FRAME_COUNT = 8          # frames required to confirm a class

# --- Confidence per model type ---
CONF_THRESHOLD_BSBA = 0.27
CONF_THRESHOLD_ICT = 0.2
CONF_THRESHOLD_DEFAULT = 0.35  # fallback confidence

REQUIRED_PARTS = {
    # ==== BSBA ====
    "BSBA_MALE": [
        "black shoes",
        "blue long sleeve polo",
        "gray blazer",
        "gray pants",
        "red necktie"
    ],
    "BSBA_MALE_NO_BLAZER": [
        "black shoes",
        "blue long sleeve polo",
        "gray pants",
        "red necktie"
    ],
    "BSBA_FEMALE": [
        "close shoes",
        "blue long sleeve polo",
        "gray blazer",
        "gray skirt",
        "red scarf"
    ],
    "BSBA_FEMALE_NO_BLAZER": [
        "close shoes",
        "blue long sleeve polo",
        "gray skirt",
        "red scarf"
    ],

    # ==== ICT ====
    "ICT_MALE": [
        "black shoes",
        "ict gray pants",
        "ict polo"
    ],

    # ==== BSCPE (fallback uses ICT model currently) ====
    "BSCPE_MALE": [
        "black shoes",
        "ict gray pants",
        "ict polo"
    ]
}

# --- Map course type to model ---
MODELS = {
    "BSBA_MALE": "bsba_male.pt",
    "BSBA_FEMALE": "bsba_female.pt",
    "ICT_MALE": "bsba_male.pt",  # Use BSBA male model for ICT
    "BSCPE_MALE": "bsba_male.pt",  # Use BSBA male model for BSCPE
    "ICT_FEMALE": "bsba_female.pt",  # Use BSBA female model for ICT
    "BSCPE_FEMALE": "bsba_female.pt",  # Use BSBA female model for BSCPE
}

# --- Map course type to confidence ---
CONF_THRESHOLDS = {
    "BSBA_MALE": CONF_THRESHOLD_BSBA,
    "BSBA_FEMALE": CONF_THRESHOLD_BSBA,
    "ICT_MALE": CONF_THRESHOLD_ICT,
    "BSCPE_MALE": CONF_THRESHOLD_ICT,
}

def get_detected_classes(results, conf_threshold, frame_shape, min_box_px=40, min_box_area_ratio=0.002):
    """
    Return list of class names that pass confidence and size filters.
    - conf_threshold: confidence cutoff
    - frame_shape: (height, width, channels)
    - min_box_px: minimum width/height in pixels to accept
    - min_box_area_ratio: min box area ratio of frame area (very small boxes ignored)
    """
    try:
        if not results or len(results) == 0:
            return []

        res = results[0]
        boxes = getattr(res, "boxes", None)
        if boxes is None or len(boxes) == 0:
            return []

        # get arrays
        xyxy = boxes.xyxy.cpu().numpy()        # shape (N,4)
        confs = boxes.conf.cpu().numpy().tolist()
        cls_indices = boxes.cls.cpu().numpy().astype(int).tolist()
        name_map = getattr(res, "names", {})

        frame_h, frame_w = frame_shape[0], frame_shape[1]
        frame_area = max(1, frame_w * frame_h)

        accepted = []
        for idx, (cidx, conf, box) in enumerate(zip(cls_indices, confs, xyxy)):
            if conf < conf_threshold:
                continue

            x1, y1, x2, y2 = box
            w = max(0, x2 - x1)
            h = max(0, y2 - y1)
            area = w * h

            # filter tiny boxes
            if w < min_box_px or h < min_box_px:
                continue
            if (area / frame_area) < min_box_area_ratio:
                continue

            # map class index to name (safely)
            label = name_map.get(int(cidx), str(int(cidx)))
            accepted.append(label)

        # return unique labels (set) but keep as list
        return list(dict.fromkeys(accepted))
    except Exception as e:
        # don't crash on unexpected result layout
        print("Detection filter error:", e)
        return []

# Detection System Class (integrated from detected.py)
class ImprovedUniformTracker:
    """Improved uniform tracking with course-specific requirements and frame counting - no timeout"""
    
    def __init__(self, course_type="BSBA_MALE"):
        self.course_type = course_type
        self.required_parts = REQUIRED_PARTS.get(course_type, [])
        self.detection_history = defaultdict(lambda: deque(maxlen=MIN_FRAME_COUNT))
        self.confirmed_parts = set()
        self.start_time = time.time()
        self.last_update_time = time.time()
        self.stable_detection_threshold = 0.15  # Minimum time between updates for stability
    
    def reset(self, course_type="BSBA_MALE"):
        """Reset tracking for new detection session"""
        self.course_type = course_type
        self.required_parts = REQUIRED_PARTS.get(course_type, [])
        self.detection_history = defaultdict(lambda: deque(maxlen=MIN_FRAME_COUNT))
        self.confirmed_parts = set()
        self.start_time = time.time()
        self.last_update_time = time.time()
    
    def update_detections(self, detected_classes, current_time=None):
        """Update tracking based on detected class names with frame counting"""
        if current_time is None:
            current_time = time.time()
        
        # Only update if enough time has passed for stability
        if current_time - self.last_update_time < self.stable_detection_threshold:
            return self.is_complete(), self.get_status_text()
        
        self.last_update_time = current_time
        
        # Add current detections to history
        for class_name in detected_classes:
            self.detection_history[class_name].append(current_time)
        
        # Update confirmed parts (seen in MIN_FRAME_COUNT frames)
        self.confirmed_parts = {
            part for part, times in self.detection_history.items() 
            if len(times) >= MIN_FRAME_COUNT
        }
        
        return self.is_complete(), self.get_status_text()
    
    def is_complete(self):
        """Check if all required parts are confirmed"""
        return all(part in self.confirmed_parts for part in self.required_parts)
    
    def get_status_text(self):
        """Get current status text"""
        if self.is_complete():
            return "COMPLETE UNIFORM"
        else:
            missing_parts = [part for part in self.required_parts if part not in self.confirmed_parts]
            return f"Missing: {', '.join(missing_parts)}"
    
    def get_missing_components(self):
        """Get list of components not yet confirmed"""
        return [part for part in self.required_parts if part not in self.confirmed_parts]
    
    def get_elapsed_time(self):
        """Get elapsed time since detection started"""
        return time.time() - self.start_time

# Legacy class for backward compatibility
class BSBAUniformTracker(ImprovedUniformTracker):
    """Legacy BSBA uniform tracker - now uses improved system"""
    
    def __init__(self):
        super().__init__("BSBA_MALE")

# Note: All detection functions and variables are defined in this file

# Note: DetectionSystem class is defined below in this file

# Import YOLO if available
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
    print("✅ YOLO imported successfully")
except ImportError:
    YOLO_AVAILABLE = False
    print("⚠️ YOLO not available - using simulation mode")
    # Create a dummy YOLO class for compatibility
    class YOLO:
        def __init__(self, model_path):
            self.model_path = model_path
            print(f"🔧 Dummy YOLO model loaded: {model_path}")
        
        def __call__(self, frame, conf=0.5):
            # Return dummy results
            class DummyResults:
                def __init__(self):
                    self.boxes = None
            return [DummyResults()]

class DetectionSystem:
    def __init__(self, model_path="bsba_female.pt", conf_threshold=0.65, iou_threshold=0.15, cam_index=0):
        print(f"🔧 Initializing DetectionSystem with model: {model_path}")
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.cam_index = cam_index
        
        # Detection state
        self.detection_active = False
        self.detection_thread = None
        self.current_person_id = None
        self.current_person_name = None
        self.current_person_type = None
        
        # UI callback for updating camera feed
        self.ui_callback = None
        
        # Initialize detection service
        try:
            from detection import get_detection_service
            self.detection_service = get_detection_service()
            print(f"✅ DetectionSystem initialized with detection service")
        except Exception as e:
            print(f"❌ Failed to initialize detection service: {e}")
            self.detection_service = None

    def load_model(self):
        """Load detection service with model"""
        if self.detection_service:
            try:
                # Create a new detection service instance with the specified model
                from detection import UniformDetectionService
                self.detection_service = UniformDetectionService(
                    model_path=self.model_path, 
                    conf_threshold=self.conf_threshold
                )
                print(f"✅ Detection service loaded with model: {self.model_path}")
                return True
            except Exception as e:
                print(f"❌ Failed to load detection service: {e}")
                return False
        return False

    def start_live_feed(self, ui_callback=None):
        """Start live camera feed using detection service"""
        self.ui_callback = ui_callback
        
        if not self.detection_service:
            print("❌ Detection service not available")
            return False
            
        # Load model
        if not self.load_model():
            return False
            
        # Start camera
        if not self.detection_service.start_camera():
            print("❌ Failed to start camera")
            return False
            
        # Start detection loop
        self.detection_active = True
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()
        
        print(f"✅ Live camera feed started with clean detection")
        return True

    def start_detection(self, person_id, person_name, person_type, ui_callback=None):
        """Start detection for a person using detection service"""
        self.current_person_id = person_id
        self.current_person_name = person_name
        self.current_person_type = person_type
        self.ui_callback = ui_callback
        
        if not self.detection_service:
            print("❌ Detection service not available")
            return False
        
        # Determine the correct model path based on person type and gender
        if hasattr(self, 'main_ui') and self.main_ui:
            model_path = self.main_ui._get_model_path_for_person(person_id, person_type)
            if model_path != self.model_path:
                self.model_path = model_path
                print(f"🔄 Switching to model: {model_path}")
            
        # Load model
        if not self.load_model():
            return False
            
        # Start camera
        if not self.detection_service.start_camera():
            print("❌ Failed to start camera")
            return False
            
        # Start detection loop
        self.detection_active = True
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()
        
        print(f"✅ Detection started for {person_name} with clean detection")
        return True

    def stop_detection(self):
        """Stop detection"""
        self.detection_active = False
        if self.detection_service:
            self.detection_service.stop_detection()
            self.detection_service.stop_camera()
        print("🛑 Detection stopped")
    
    def reset_detection_history(self):
        """Reset detection history for new detection session"""
        pass
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            self.stop_detection()
            print("✅ DetectionSystem cleanup completed")
        except Exception as e:
            print(f"❌ Error during DetectionSystem cleanup: {e}")

    def _detection_loop(self):
        """Clean detection loop using detection service - only bounding boxes and class names"""
        try:
            print("🔍 Starting clean detection loop - only bounding boxes and class names")
            
            for detection_result in self.detection_service.get_detection_loop():
                if not self.detection_active:
                    break
                    
                # Get clean annotated frame (only bounding boxes and class names)
                annotated_frame = detection_result['annotated_frame']
                detected_classes = detection_result['detected_classes']
                
                # Update UI with clean frame
                if self.ui_callback and annotated_frame is not None:
                    self.ui_callback(annotated_frame)
                
                # Print detected classes to console (not on camera)
                if detected_classes:
                    class_names = [d['class_name'] for d in detected_classes]
                    confidences = [f"{d['confidence']:.2f}" for d in detected_classes]
                    print(f"🔍 Detected: {class_names} (conf: {confidences})")
                    
        except Exception as e:
            print(f"❌ Error in detection loop: {e}")
        finally:
            print("🛑 Clean detection loop ended")

class GuardMainControl:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🛡️ AI-niform - Guard Control Center")
        
        # Configure Guard window for primary monitor (fullscreen)
        self.root.geometry("1200x900")
        self.root.configure(bg='#ffffff')
        self.root.minsize(1000, 800)  # Set minimum window size
        
        # Position on primary monitor and make fullscreen
        try:
            # Get screen dimensions for fullscreen
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            
            print(f"🖥️ Screen dimensions: {screen_width}x{screen_height}")
            
            # Debug execution environment
            import os
            import sys
            print(f"DEBUG: Python executable: {sys.executable}")
            print(f"DEBUG: Python version: {sys.version}")
            print(f"DEBUG: Current working directory: {os.getcwd()}")
            print(f"DEBUG: Script directory: {os.path.dirname(os.path.abspath(__file__))}")
            print(f"DEBUG: Command line arguments: {sys.argv}")
            
            # Set geometry to fullscreen on primary monitor
            self.root.geometry(f"{screen_width}x{screen_height}+0+0")
            
            # Try fullscreen methods in order of preference
            try:
                # Method 1: Try fullscreen attribute (most reliable on Linux)
                self.root.attributes('-fullscreen', True)
                print("SUCCESS: Fullscreen set using attributes('-fullscreen', True)")
            except Exception as e1:
                print(f"ERROR: Fullscreen attribute failed: {e1}")
                try:
                    # Method 2: Try overrideredirect (removes window decorations)
                    self.root.overrideredirect(True)
                    self.root.geometry(f"{screen_width}x{screen_height}+0+0")
                    print("SUCCESS: Fullscreen set using overrideredirect")
                except Exception as e2:
                    print(f"ERROR: Overrideredirect failed: {e2}")
                    try:
                        # Method 3: Try zoomed attribute
                        self.root.attributes('-zoomed', True)
                        print("SUCCESS: Fullscreen set using attributes('-zoomed', True)")
                    except Exception as e3:
                        print(f"ERROR: Zoomed attribute failed: {e3}")
                        print("SUCCESS: Using geometry-based fullscreen")
                        
        except Exception as e:
            print(f"WARNING: Error setting fullscreen: {e}")
            # Fallback: just set geometry
            try:
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                self.root.geometry(f"{screen_width}x{screen_height}+0+0")
                print("SUCCESS: Fallback: Set geometry to fullscreen")
            except:
                print("WARNING: Could not set fullscreen mode - using normal state")
        
        # Add keyboard shortcuts for fullscreen control
        self.root.bind('<F11>', self.toggle_fullscreen)
        self.root.bind('<Escape>', self.exit_fullscreen)
        
        # Initialize variables
        self.current_guard_id = None
        self.session_id = None
        self.valid_guard_ids = ["0095081841", "0095339862", "GUARD001", "GUARD002", "GUARD003", "ADMIN", "SUPERVISOR"]
        self.guards_loaded = True
        
        # Detection system variables
        self.detection_system = None
        self.detection_active = False
        self.detection_thread = None
        self.model = None
        self.cap = None
        self.violation_count = 0
        self.compliant_count = 0
        self.total_detections = 0
        
        # Model configuration
        self.current_model_path = "bsba_male.pt"
        # Detection parameters - Optimized for visibility
        self.conf_threshold = 0.1  # Very low threshold to show all detections
        self.iou_threshold = 0.1   # Lower threshold for better overlap detection
        self.frame_skip = 1        # Process every frame for better detection
        self.prev_time = time.time()
        self.fps = 0
        
        # Complete uniform detection tracking
        self.detected_components = {}  # Track detected uniform components
        
        # Temporal tracking for improved accuracy
        self.previous_detections = []  # Store previous frame detections
        
        # Multi-monitor setup
        self.screen_info = self.get_screen_info()
        self.required_components = {}  # Required components per course
        self.uniform_complete = False
        self.last_complete_check = 0  # Timestamp of last complete uniform check
        
        # UI variables
        self.guard_id_var = tk.StringVar()
        self.login_status_var = tk.StringVar(value="Not Logged In")
        self.person_id_var = tk.StringVar()
        self.person_type_var = tk.StringVar(value="student")
        
        # Tab control
        self.notebook = None
        self.login_tab = None
        self.dashboard_tab = None
        self.visitor_tab = None
        self.student_forgot_tab = None
        self.main_screen_window = None
        
        # Initialize uniform components requirements
        self.initialize_uniform_requirements()
        
        # Initialize Firebase if available
        self.db = None
        self.firebase_initialized = False
        
        # Initialize Arduino connection for gate control
        self.arduino_connected = False
        self.arduino_serial = None
        self.cleanup_done = False
        
        # Visitor RFID management
        self.visitor_rfid_registry = {}  # RFID -> visitor_info
        self.active_visitors = {}  # RFID -> visitor_info with time_in
        self.available_rfids = ["0095272249", "0095520658"]  # Available RFID cards
        
        # Student forgot ID RFID management
        self.student_forgot_rfids = ["0095272825", "0095277892"]  # Empty RFID cards for student forgot ID
        self.student_rfid_assignments = {}  # RFID -> student_info for temporary assignments
        
        # Activity logs
        self.activity_logs = []
        self.max_logs = 100
        
        # Setup UI first
        self.setup_ui()
        
        # Initialize detection system
        self.init_detection_system()
        
        # Validate startup requirements
        self.validate_startup_requirements()
        
        # Initialize Firebase immediately during startup
        if FIREBASE_AVAILABLE:
            self.init_firebase_async()
            # Ensure Firebase is initialized before proceeding
            if not self.firebase_initialized:
                print("INFO: Retrying Firebase initialization...")
                self.init_firebase()
        
        # Set a flag to detect if Firebase consistently fails
        self.firebase_consistently_failed = False
        self.firebase_init_attempts = 0
        
        # Initialize BSBA uniform tracker
        self.bsba_uniform_tracker = BSBAUniformTracker()
        
        # Initialize Arduino connection after UI is ready
        self.root.after(300, self.init_arduino_connection)
        
        # Start listening for Arduino button presses
        self.root.after(500, self.listen_for_arduino_buttons)
        
        # Ensure fullscreen on primary monitor after UI is ready
        self.root.after(200, self.ensure_fullscreen_on_primary_monitor)
        
        print("SUCCESS: Guard Control Center initialized successfully")
    
    def get_screen_info(self):
        """Get information about available screens"""
        try:
            # Get screen information
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            
            # Try to get multiple monitor information
            try:
                # For Windows
                if platform.system() == "Windows":
                    import win32api
                    monitors = win32api.EnumDisplayMonitors()
                    screen_info = {
                        'primary': {'width': screen_width, 'height': screen_height, 'x': 0, 'y': 0},
                        'secondary': None,
                        'count': len(monitors)
                    }
                    
                    if len(monitors) > 1:
                        # Get secondary monitor info
                        for monitor in monitors[1:]:
                            screen_info['secondary'] = {
                                'width': monitor[2][2] - monitor[2][0],
                                'height': monitor[2][3] - monitor[2][1],
                                'x': monitor[2][0],
                                'y': monitor[2][1]
                            }
                            break
                else:
                    # For Linux/Mac - use tkinter's screen info
                    screen_info = {
                        'primary': {'width': screen_width, 'height': screen_height, 'x': 0, 'y': 0},
                        'secondary': None,
                        'count': 1  # Default to single monitor
                    }
                    
                    # Try to detect secondary monitor using xrandr (Linux)
                    if platform.system() == "Linux":
                        try:
                            import subprocess
                            result = subprocess.run(['xrandr'], capture_output=True, text=True)
                            if 'connected' in result.stdout:
                                lines = result.stdout.split('\n')
                                connected_monitors = [line for line in lines if 'connected' in line and 'disconnected' not in line]
                                if len(connected_monitors) > 1:
                                    screen_info['count'] = len(connected_monitors)
                                    # Parse secondary monitor info
                                    for line in connected_monitors[1:]:
                                        if 'connected' in line:
                                            parts = line.split()
                                            for i, part in enumerate(parts):
                                                if '+' in part and 'x' in part:
                                                    try:
                                                        resolution = part.split('+')[0]
                                                        width, height = map(int, resolution.split('x'))
                                                        x_offset = int(parts[i].split('+')[1]) if '+' in parts[i] else 0
                                                        y_offset = int(parts[i].split('+')[2]) if '+' in parts[i] and len(parts[i].split('+')) > 2 else 0
                                                        screen_info['secondary'] = {
                                                            'width': width,
                                                            'height': height,
                                                            'x': x_offset,
                                                            'y': y_offset
                                                        }
                                                        break
                                                    except:
                                                        continue
                                            break
                        except:
                            pass
                            
            except ImportError:
                # Fallback for systems without win32api
                screen_info = {
                    'primary': {'width': screen_width, 'height': screen_height, 'x': 0, 'y': 0},
                    'secondary': None,
                    'count': 1
                }
            
            print(f"🖥️ Screen Info: {screen_info['count']} monitor(s) detected")
            if screen_info['secondary']:
                print(f"🖥️ Secondary monitor: {screen_info['secondary']['width']}x{screen_info['secondary']['height']} at ({screen_info['secondary']['x']}, {screen_info['secondary']['y']})")
            
            return screen_info
            
        except Exception as e:
            print(f"WARNING: Error getting screen info: {e}")
            return {
                'primary': {'width': 1920, 'height': 1080, 'x': 0, 'y': 0},
                'secondary': None,
                'count': 1
            }
    
    def initialize_uniform_requirements(self):
        """Initialize required uniform components for each course"""
        # Define required uniform components for each course
        self.required_components = {
            'ict': {
                'male': ['shirt', 'pants', 'shoes', 'belt', 'id_card'],
                'female': ['blouse', 'skirt', 'shoes', 'belt', 'id_card']
            },
            'tourism': {
                'male': ['polo_shirt', 'pants', 'shoes', 'belt', 'id_card'],
                'female': ['polo_shirt', 'pants', 'shoes', 'belt', 'id_card']
            },
            'teacher': {
                'male': ['dress_shirt', 'pants', 'shoes', 'belt', 'id_card'],
                'female': ['blouse', 'pants', 'shoes', 'belt', 'id_card']
            },
            'visitor': {
                'male': ['shirt', 'pants', 'shoes'],
                'female': ['shirt', 'pants', 'shoes']
            }
        }
        
        # Initialize detected components tracking
        self.detected_components = {}
        self.uniform_complete = False
        self.last_complete_check = 0
        
        print("SUCCESS: Uniform requirements initialized")
    
    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode"""
        try:
            if self.root.attributes('-fullscreen'):
                self.root.attributes('-fullscreen', False)
                print("🖥️ Exited fullscreen mode")
            else:
                self.root.attributes('-fullscreen', True)
                print("🖥️ Entered fullscreen mode")
        except Exception as e:
            print(f"WARNING: Error toggling fullscreen: {e}")
    
    def exit_fullscreen(self, event=None):
        """Exit fullscreen mode"""
        try:
            self.root.attributes('-fullscreen', False)
            self.root.overrideredirect(False)
            print("🖥️ Exited fullscreen mode")
        except Exception as e:
            print(f"WARNING: Error exiting fullscreen: {e}")
    
    def toggle_main_screen_fullscreen(self, event=None):
        """Toggle Main Screen fullscreen mode"""
        try:
            if hasattr(self, 'main_screen_window') and self.main_screen_window:
                if self.main_screen_window.attributes('-fullscreen'):
                    self.main_screen_window.attributes('-fullscreen', False)
                    self.main_screen_window.overrideredirect(False)
                    print("🖥️ Main Screen exited fullscreen mode")
                else:
                    # Get secondary monitor dimensions
                    if self.screen_info['secondary']:
                        secondary = self.screen_info['secondary']
                        self.main_screen_window.geometry(f"{secondary['width']}x{secondary['height']}+{secondary['x']}+{secondary['y']}")
                        self.main_screen_window.attributes('-fullscreen', True)
                        print(f"🖥️ Main Screen entered fullscreen mode: {secondary['width']}x{secondary['height']}")
                    else:
                        print("WARNING: No secondary monitor available for Main Screen fullscreen")
        except Exception as e:
            print(f"WARNING: Error toggling Main Screen fullscreen: {e}")
    
    def exit_main_screen_fullscreen(self, event=None):
        """Exit Main Screen fullscreen mode"""
        try:
            if hasattr(self, 'main_screen_window') and self.main_screen_window:
                self.main_screen_window.attributes('-fullscreen', False)
                self.main_screen_window.overrideredirect(False)
                print("🖥️ Main Screen exited fullscreen mode")
        except Exception as e:
            print(f"WARNING: Error exiting Main Screen fullscreen: {e}")
    
    def ensure_fullscreen_on_primary_monitor(self):
        """Ensure window is fullscreen on primary monitor"""
        try:
            # Get primary monitor dimensions
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            
            # Set to fullscreen on primary monitor (position 0,0)
            self.root.geometry(f"{screen_width}x{screen_height}+0+0")
            
            # Try to set fullscreen
            try:
                self.root.attributes('-fullscreen', True)
                print(f"SUCCESS: Fullscreen set on primary monitor: {screen_width}x{screen_height}")
            except:
                try:
                    self.root.attributes('-zoomed', True)
                    print(f"SUCCESS: Maximized on primary monitor: {screen_width}x{screen_height}")
                except:
                    print(f"SUCCESS: Positioned on primary monitor: {screen_width}x{screen_height}")
                    
        except Exception as e:
            print(f"WARNING: Error ensuring fullscreen on primary monitor: {e}")
    
    def validate_startup_requirements(self):
        """Validate all startup requirements"""
        try:
            print("🔍 Validating startup requirements...")
            
            # Check for required model files
            model_files = ["bsba_male.pt", "bsba_female.pt"]
            missing_models = []
            
            for model_file in model_files:
                if not os.path.exists(model_file):
                    missing_models.append(model_file)
            
            if missing_models:
                print(f"WARNING: Missing model files: {missing_models}")
            else:
                print("SUCCESS: All model files found")
            
            # Check Firebase configuration
            if FIREBASE_AVAILABLE:
                if os.path.exists("firebase_service_account.json") or os.path.exists("serviceAccountKey.json"):
                    print("SUCCESS: Firebase configuration file found")
                else:
                    print("WARNING: Firebase configuration file not found")
            else:
                print("WARNING: Firebase not available - running in offline mode")
            
            # Check camera availability
            if CV2_AVAILABLE:
                try:
                    # Try different camera indices - prioritize external camera
                    camera_found = False
                    for camera_index in [1, 0, 2]:  # Try external camera (1) first, then built-in (0), then others
                        test_cap = cv2.VideoCapture(camera_index)
                        if test_cap.isOpened():
                            # Use normal camera settings for testing
                            ret, frame = test_cap.read()
                            if ret and frame is not None:
                                camera_type = "External" if camera_index == 1 else "Built-in" if camera_index == 0 else f"Camera {camera_index}"
                                print(f"SUCCESS: {camera_type} camera available on index {camera_index}")
                                camera_found = True
                                test_cap.release()
                                break
                            test_cap.release()
                    
                    if not camera_found:
                        print("WARNING: Camera not accessible - detection features will be limited")
                        print("💡 Try connecting a USB camera or check camera permissions")
                except Exception as e:
                    print(f"WARNING: Camera test failed: {e}")
            else:
                print("WARNING: OpenCV not available - camera features disabled")
            
            # Check YOLO availability
            if YOLO_AVAILABLE:
                print("SUCCESS: YOLO available")
            else:
                print("WARNING: YOLO not available - AI detection disabled")
            
            print("SUCCESS: Startup validation completed")
            
        except Exception as e:
            print(f"ERROR: Error during startup validation: {e}")
    
    def debug_firebase_student(self, student_id):
        """Debug function to check student data in Firebase"""
        try:
            if not self.firebase_initialized or not self.db:
                print("ERROR: Firebase not initialized")
                return None
            
            print(f"🔍 Checking Firebase for student ID: {student_id}")
            
            # Query Firebase students collection
            doc_ref = self.db.collection('students').document(student_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                print(f"SUCCESS: Document found in Firebase:")
                print(f"   Document ID: {student_id}")
                print(f"   Data: {data}")
                print(f"   Name: {data.get('name', 'Not found')}")
                print(f"   Course: {data.get('course', 'Not found')}")
                print(f"   Gender: {data.get('gender', 'Not found')}")
                return data
            else:
                print(f"ERROR: Document '{student_id}' not found in Firebase students collection")
                return None
                
        except Exception as e:
            print(f"ERROR: Error checking Firebase student: {e}")
            return None
    
    def test_firebase_connection(self):
        """Test Firebase connection and students collection access"""
        try:
            if not self.firebase_initialized or not self.db:
                print("ERROR: Firebase not initialized")
                return False
            
            # Test connection by trying to read from students collection
            test_doc = self.db.collection('students').limit(1).get()
            print("SUCCESS: Firebase connection test successful")
            return True
            
        except Exception as e:
            print(f"ERROR: Firebase connection test failed: {e}")
            return False
    
    def test_firebase_connection_with_timeout(self):
        """Test Firebase connection with timeout handling"""
        try:
            import threading
            import time
            
            def test_connection():
                try:
                    if not self.firebase_initialized or not self.db:
                        print("ERROR: Firebase not initialized")
                        return False
                    
                    # Test connection by trying to read from students collection
                    test_doc = self.db.collection('students').limit(1).get()
                    print("SUCCESS: Firebase connection test successful")
                    return True
                    
                except Exception as e:
                    print(f"ERROR: Firebase connection test failed: {e}")
                    return False
            
            # Run connection test in a separate thread with timeout
            result = [False]
            def run_test():
                result[0] = test_connection()
            
            thread = threading.Thread(target=run_test)
            thread.daemon = True
            thread.start()
            thread.join(timeout=10)  # 10 second timeout
            
            if thread.is_alive():
                print("WARNING: Firebase connection test timed out - continuing in offline mode")
            else:
                print("SUCCESS: Firebase connection test completed")
                
        except Exception as e:
            print(f"WARNING: Firebase connection test error: {e}")
    
    def init_firebase_async(self):
        """Initialize Firebase connection asynchronously with robust path handling"""
        try:
            # Get the current working directory and script directory
            import os
            current_dir = os.getcwd()
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
            print(f"DEBUG: Current working directory: {current_dir}")
            print(f"DEBUG: Script directory: {script_dir}")
            
            # Check for Firebase credentials in multiple locations
            cred_files = [
                'serviceAccountKey.json',
                'firebase_service_account.json',
                os.path.join(script_dir, 'serviceAccountKey.json'),
                os.path.join(script_dir, 'firebase_service_account.json'),
                os.path.join(current_dir, 'serviceAccountKey.json'),
                os.path.join(current_dir, 'firebase_service_account.json')
            ]
            
            cred_file = None
            for file_path in cred_files:
                if os.path.exists(file_path):
                    cred_file = file_path
                    print(f"SUCCESS: Found Firebase credentials at: {file_path}")
                    break
            
            if not cred_file:
                print("WARNING: Firebase service account not found - running in offline mode")
                print(f"DEBUG: Searched locations: {cred_files}")
                return
            
            if not firebase_admin._apps:
                print(f"INFO: Initializing Firebase with credentials: {cred_file}")
                cred = credentials.Certificate(cred_file)
                firebase_admin.initialize_app(cred)
                self.db = firestore.client()
                self.firebase_initialized = True
                print("SUCCESS: Firebase initialized successfully")
                print(f"SUCCESS: Connected to project: ainiform-system-c42de")
                
                # Save guards to Firebase
                self.save_guards_to_firebase()
                
                # Save permanent students to Firebase
                self.save_permanent_students_to_firebase()
                
                # Test Firebase connection with timeout
            if hasattr(self, 'root') and self.root.winfo_exists():
                self.root.after(1000, self.test_firebase_connection_with_timeout)
            else:
                print("INFO: Firebase already initialized")
                self.firebase_initialized = True
                
        except Exception as e:
            print(f"ERROR: Firebase initialization failed: {e}")
            print(f"DEBUG: Error type: {type(e).__name__}")
            print(f"DEBUG: Error details: {str(e)}")
            print("INFO: Switching to offline mode")
            self.firebase_initialized = False
    
    def init_firebase(self):
        """Initialize Firebase connection (synchronous fallback) with robust path handling"""
        try:
            # Get the current working directory and script directory
            import os
            current_dir = os.getcwd()
            script_dir = os.path.dirname(os.path.abspath(__file__))
            
            print(f"DEBUG: Current working directory: {current_dir}")
            print(f"DEBUG: Script directory: {script_dir}")
            
            # Check for Firebase credentials in multiple locations
            cred_files = [
                'serviceAccountKey.json',
                'firebase_service_account.json',
                os.path.join(script_dir, 'serviceAccountKey.json'),
                os.path.join(script_dir, 'firebase_service_account.json'),
                os.path.join(current_dir, 'serviceAccountKey.json'),
                os.path.join(current_dir, 'firebase_service_account.json')
            ]
            
            cred_file = None
            for file_path in cred_files:
                if os.path.exists(file_path):
                    cred_file = file_path
                    print(f"SUCCESS: Found Firebase credentials at: {file_path}")
                    break
            
            if not cred_file:
                print("WARNING: Firebase service account not found - running in offline mode")
                print(f"DEBUG: Searched locations: {cred_files}")
                self.firebase_initialized = False
                return False
            
            if not firebase_admin._apps:
                print(f"INFO: Initializing Firebase with credentials: {cred_file}")
                cred = credentials.Certificate(cred_file)
                firebase_admin.initialize_app(cred)
                self.db = firestore.client()
                self.firebase_initialized = True
                print("SUCCESS: Firebase initialized successfully (fallback)")
                
                # Save guards to Firebase
                self.save_guards_to_firebase()
                
                # Save permanent students to Firebase
                self.save_permanent_students_to_firebase()
                
                # Test Firebase connection
                self.test_firebase_connection()
            else:
                print("INFO: Firebase already initialized")
                self.firebase_initialized = True
                
        except Exception as e:
            print(f"ERROR: Firebase initialization failed: {e}")
            print(f"DEBUG: Error type: {type(e).__name__}")
            print(f"DEBUG: Error details: {str(e)}")
            print("INFO: Switching to offline mode")
            self.firebase_initialized = False
    
    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
    
    def setup_ui(self):
        """Setup the main UI"""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create login tab
        self.create_login_tab()
        
        # Initially hide dashboard tab
        self.dashboard_tab = None
    
    def create_login_tab(self):
        """Create the login tab with improved visibility"""
        self.login_tab = tk.Frame(self.notebook, bg='#ffffff')
        self.notebook.add(self.login_tab, text="🔐 Guard Login")
        
        # Set tab as active
        self.notebook.select(self.login_tab)
        
        # Header
        self.create_header(self.login_tab)
        
        # Login content
        self.create_login_content(self.login_tab)
        
        # Footer
        self.create_footer(self.login_tab)
    
    def create_header(self, parent):
        """Create header section with improved visibility"""
        header_frame = tk.Frame(parent, bg='#1e3a8a', height=100)
        header_frame.pack(fill=tk.X, pady=(0, 25))
        header_frame.pack_propagate(False)
        
        # Left side - Title
        title_frame = tk.Frame(header_frame, bg='#1e3a8a')
        title_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        title_label = tk.Label(
            title_frame,
            text="🛡️ AI-niform Guard Control Center",
            font=('Arial', 28, 'bold'),
            fg='white',
            bg='#1e3a8a'
        )
        title_label.pack(expand=True)
        
        subtitle_label = tk.Label(
            title_frame,
            text="Advanced Security Management System",
            font=('Arial', 14),
            fg='#e5e7eb',
            bg='#1e3a8a'
        )
        subtitle_label.pack()
        
        # Right side - Logout button (only on dashboard)
        if parent == self.dashboard_tab:
            logout_frame = tk.Frame(header_frame, bg='#1e3a8a')
            logout_frame.pack(side=tk.RIGHT, padx=25, pady=15)
            
            # Test Main Screen Button
            test_btn = tk.Button(
                logout_frame,
                text="🖥️ Test Main Screen",
                command=self.test_main_screen_display,
                font=('Arial', 10, 'bold'),
                bg='#8b5cf6',
                fg='white',
                relief='raised',
                bd=2,
                padx=10,
                pady=5,
                cursor='hand2',
                activebackground='#7c3aed',
                activeforeground='white'
            )
            test_btn.pack(fill=tk.X, pady=(0, 5))
            
            # Debug Firebase Button
            debug_btn = tk.Button(
                logout_frame,
                text="🔍 Debug Firebase",
                command=self.debug_firebase_student_ui,
                font=('Arial', 10, 'bold'),
                bg='#f59e0b',
                fg='white',
                relief='raised',
                bd=2,
                padx=10,
                pady=5,
                cursor='hand2',
                activebackground='#d97706',
                activeforeground='white'
            )
            debug_btn.pack(fill=tk.X, pady=(0, 5))
            
            logout_btn = tk.Button(
                logout_frame,
                text="🚪 Logout",
                font=('Arial', 12, 'bold'),
                fg='white',
                bg='#dc2626',
                activebackground='#b91c1c',
                activeforeground='white',
                relief='raised',
                bd=3,
                padx=15,
                pady=8,
                command=self.logout_guard
            )
            logout_btn.pack(fill=tk.X)
    
    def create_login_content(self, parent):
        """Create login content with perfectly positioned buttons"""
        # Main login container with centered layout
        login_frame = tk.Frame(parent, bg='#ffffff', relief='solid', bd=2)
        login_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)
        
        # Title section - centered
        title_frame = tk.Frame(login_frame, bg='#ffffff')
        title_frame.pack(fill=tk.X, pady=(30, 25))
        
        login_title = tk.Label(
            title_frame,
            text="🔐 Guard Authentication",
            font=('Arial', 24, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        )
        login_title.pack()
        
        # Subtitle
        subtitle = tk.Label(
            title_frame,
            text="Enter your Guard ID to access the system",
            font=('Arial', 13),
            fg='#6b7280',
            bg='#ffffff'
        )
        subtitle.pack(pady=(8, 0))
        
        # Main form container - centered
        form_container = tk.Frame(login_frame, bg='#ffffff')
        form_container.pack(expand=True, pady=15)
        
        # Guard ID input section - centered
        input_section = tk.Frame(form_container, bg='#ffffff')
        input_section.pack(expand=True)
        
        # Guard ID label
        id_label = tk.Label(
            input_section,
            text="Guard ID:",
            font=('Arial', 16, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        )
        id_label.pack(pady=(0, 15))
        
        # Input field - properly sized
        self.id_entry = tk.Entry(
            input_section,
            textvariable=self.guard_id_var,
            font=('Arial', 18, 'bold'),
            width=12,
            justify=tk.CENTER,
            relief='solid',
            bd=3,
            bg='#f0f9ff',
            fg='#1e3a8a',
            insertbackground='#1e3a8a'
        )
        self.id_entry.pack(pady=(0, 30))
        self.id_entry.bind('<Return>', lambda e: self.login_manual())
        self.id_entry.focus()
        
        # Button container for proper alignment
        button_container = tk.Frame(input_section, bg='#ffffff')
        button_container.pack(expand=True, pady=10)
        
        # LOGIN button - properly sized and positioned
        self.manual_login_btn = tk.Button(
            button_container,
            text="🚀 LOGIN",
            command=self.login_manual,
            font=('Arial', 18, 'bold'),
            bg='#3b82f6',
            fg='white',
            relief='raised',
            bd=4,
            padx=50,
            pady=15,
            cursor='hand2',
            activebackground='#2563eb',
            activeforeground='white'
        )
        self.manual_login_btn.pack(pady=(0, 20))
        
        # Status display section
        status_frame = tk.Frame(login_frame, bg='#ffffff')
        status_frame.pack(fill=tk.X, pady=(20, 15))
        
        self.status_label = tk.Label(
            status_frame,
            textvariable=self.login_status_var,
            font=('Arial', 14, 'bold'),
            fg='#dc2626',
            bg='#ffffff'
        )
        self.status_label.pack()
        
        # Instructions
        instructions = tk.Label(
            status_frame,
            text="Enter your Guard ID to login",
            font=('Arial', 11),
            fg='#6b7280',
            bg='#ffffff'
        )
        instructions.pack(pady=(8, 0))
        
        # QUIT button section - highly visible
        quit_section = tk.Frame(login_frame, bg='#ffffff')
        quit_section.pack(fill=tk.X, pady=(30, 20))
        
        # Add a separator line
        separator = tk.Frame(quit_section, height=2, bg='#e5e7eb')
        separator.pack(fill=tk.X, pady=(0, 20))
        
        # QUIT button - much larger and more visible
        quit_btn_main = tk.Button(
            quit_section,
            text="ERROR: QUIT APPLICATION",
            command=self.quit_application,
            font=('Arial', 20, 'bold'),
            bg='#dc2626',
            fg='white',
            relief='raised',
            bd=5,
            padx=60,
            pady=18,
            cursor='hand2',
            activebackground='#b91c1c',
            activeforeground='white'
        )
        quit_btn_main.pack(pady=10)
        
        # Add instruction text
        quit_instruction = tk.Label(
            quit_section,
            text="Click the button above to exit the application",
            font=('Arial', 12),
            fg='#6b7280',
            bg='#ffffff'
        )
        quit_instruction.pack(pady=(5, 0))
    
    def create_footer(self, parent):
        """Create footer section with highly visible QUIT button"""
        footer_frame = tk.Frame(parent, bg='#e5e7eb', relief='solid', bd=2)
        footer_frame.pack(fill=tk.X, pady=(25, 0))
        
        # Footer content container
        footer_content = tk.Frame(footer_frame, bg='#e5e7eb')
        footer_content.pack(expand=True, pady=20)
        
        # QUIT button - larger and more visible
        quit_btn = tk.Button(
            footer_content,
            text="ERROR: QUIT SYSTEM",
            command=self.quit_application,
            font=('Arial', 18, 'bold'),
            bg='#dc2626',
            fg='white',
            relief='raised',
            bd=5,
            padx=50,
            pady=15,
            cursor='hand2',
            activebackground='#b91c1c',
            activeforeground='white'
        )
        quit_btn.pack()
        
        # Add instruction text
        footer_instruction = tk.Label(
            footer_content,
            text="Alternative exit option",
            font=('Arial', 11),
            fg='#6b7280',
            bg='#e5e7eb'
        )
        footer_instruction.pack(pady=(8, 0))
    
    def login_manual(self):
        """Handle manual login"""
        guard_id = self.guard_id_var.get().strip().upper()
        
        if not guard_id:
            messagebox.showwarning("Warning", "Please enter a Guard ID")
            return
        
        if self.validate_guard_id(guard_id):
            self.authenticate_guard(guard_id)
        else:
            messagebox.showerror("Error", f"Invalid Guard ID: {guard_id}")
    
    def validate_guard_id(self, guard_id):
        """Validate guard ID"""
        return guard_id in self.valid_guard_ids
    
    def authenticate_guard(self, guard_id):
        """Authenticate the guard"""
        self.current_guard_id = guard_id
        self.login_status_var.set("Logged In")
        
        # Generate session ID
        self.session_id = f"{guard_id}_{int(time.time())}"
        
        # Save guard login to Firebase
        self.save_guard_login_to_firebase(guard_id)
        
        # Update guard login info in guards collection
        self.update_guard_login_info(guard_id)
        
        # Disable login button
        self.manual_login_btn.config(state=tk.DISABLED)
        
        # Camera will open when student taps their ID
        self.update_camera_label_for_guard()
        
        self.show_green_success_message("Login Successful", f"Welcome, Guard {guard_id}!")
        
        # Start security system
        self.start_security_system()
    
# Camera method removed - will be replaced with user's detection file

    def update_camera_feed(self, frame):
        """Update camera feed with detection frame"""
        try:
            if hasattr(self, 'camera_label') and self.camera_label and self.root.winfo_exists():
                # Get the camera label dimensions
                label_width = self.camera_label.winfo_width()
                label_height = self.camera_label.winfo_height()
                
                # If label dimensions are not available yet, use default
                if label_width <= 1 or label_height <= 1:
                    label_width = 400
                    label_height = 300
                
                # Calculate aspect ratio preserving resize
                frame_height, frame_width = frame.shape[:2]
                aspect_ratio = frame_width / frame_height
                
                # Calculate new dimensions that fit within the label
                if label_width / label_height > aspect_ratio:
                    # Label is wider than needed, fit to height
                    new_height = label_height - 20  # Leave some padding
                    new_width = int(new_height * aspect_ratio)
                else:
                    # Label is taller than needed, fit to width
                    new_width = label_width - 20  # Leave some padding
                    new_height = int(new_width / aspect_ratio)
                
                # Ensure minimum size
                new_width = max(new_width, 200)
                new_height = max(new_height, 150)
                
                # Resize frame to fit camera label properly
                frame_resized = cv2.resize(frame, (new_width, new_height))
                
                # Convert BGR to RGB for Tkinter
                frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                
                # Convert to PhotoImage
                from PIL import Image, ImageTk
                pil_image = Image.fromarray(frame_rgb)
                photo = ImageTk.PhotoImage(pil_image)
                
                # Update camera label in main thread
                self.root.after(0, self._update_camera_label_with_frame, photo)
                
        except Exception as e:
            print(f"ERROR: Failed to update camera feed: {e}")
            import traceback
            traceback.print_exc()

    def _update_camera_label_with_frame(self, photo):
        """Update camera label with frame in main thread"""
        try:
            if hasattr(self, 'camera_label') and self.camera_label:
                self.camera_label.config(
                    image=photo,
                    text="",  # Remove text when showing image
                    # Remove fixed width/height to allow proper scaling
                    relief="sunken",
                    bd=2
                )
                self.camera_label.image = photo  # Keep a reference
                print("📹 Camera frame updated successfully")
        except Exception as e:
            print(f"ERROR: Failed to update camera label with frame: {e}")
            import traceback
            traceback.print_exc()

    def start_person_detection_integrated(self, person_id, person_name, person_type):
        """Start detection for a person using the integrated detection system"""
        try:
            print(f"🔍 Starting integrated detection for {person_name} ({person_type})")
            self.add_activity_log(f"🔍 Starting integrated detection for {person_name} ({person_type})")
            
            # Initialize detection system
            if not hasattr(self, 'detection_system') or self.detection_system is None:
                try:
                    self.detection_system = DetectionSystem()
                    self.detection_system.main_ui = self  # Pass main UI reference
                    print(f"✅ DetectionSystem initialized successfully")
                    self.add_activity_log(f"✅ DetectionSystem initialized successfully")
                except Exception as e:
                    print(f"❌ Failed to initialize DetectionSystem: {e}")
                    self.add_activity_log(f"❌ Failed to initialize DetectionSystem: {e}")
                    return
            
            # Start detection with UI callback
            success = self.detection_system.start_detection(
                person_id, person_name, person_type, 
                ui_callback=self.update_camera_feed
            )
            
            if success:
                print(f"✅ Integrated detection started successfully for {person_name}")
                self.add_activity_log(f"✅ Integrated detection started successfully for {person_name}")
            else:
                print(f"❌ Failed to start integrated detection for {person_name}")
                self.add_activity_log(f"❌ Failed to start integrated detection for {person_name}")
                
        except Exception as e:
            print(f"❌ Error starting integrated detection: {e}")
            self.add_activity_log(f"❌ Error starting integrated detection: {e}")

    def start_person_detection(self, person_id, person_name, person_type):
        """Start detection for a person using the integrated detection system"""
        try:
            print(f"🔍 Starting detection for {person_name} ({person_type})")
            self.add_activity_log(f"🔍 Starting detection for {person_name} ({person_type})")
            
            # Initialize detection system
            if not hasattr(self, 'detection_system'):
                self.detection_system = DetectionSystem()
                self.detection_system.main_ui = self  # Pass main UI reference
            
            # Start detection with UI callback
            success = self.detection_system.start_detection(
                person_id, person_name, person_type, 
                ui_callback=self.update_camera_feed
            )
            
            if success:
                print(f"✅ Detection started successfully for {person_name}")
                self.add_activity_log(f"✅ Detection started successfully for {person_name}")
            else:
                print(f"❌ Failed to start detection for {person_name}")
                self.add_activity_log(f"❌ Failed to start detection for {person_name}")
                
        except Exception as e:
            print(f"❌ Error starting detection: {e}")
            self.add_activity_log(f"❌ Error starting detection: {e}")

    def stop_detection(self):
        """Stop detection"""
        try:
            if hasattr(self, 'detection_system') and self.detection_system:
                self.detection_system.stop_detection()
                print("🛑 Detection stopped")
                self.add_activity_log("🛑 Detection stopped")
        except Exception as e:
            print(f"❌ Error stopping detection: {e}")
            self.add_activity_log(f"❌ Error stopping detection: {e}")

    def stop_camera_for_guard(self):
        """Stop camera for guard"""
        pass
    
    def update_camera_label_for_guard(self):
        """Update camera label to show guard camera status"""
        pass
    
    def ensure_camera_closed(self):
        """Ensure camera is closed and in standby mode"""
        pass
    
    def initialize_guard_camera_feed(self):
        """Initialize camera feed for guard monitoring (no detection)"""
        try:
            print("🔧 Starting guard camera feed (no detection)")
            self.add_activity_log("🔧 Starting guard camera feed (no detection)")
            
            # Start simple camera feed without detection
            self.start_guard_camera_feed()
            print("✅ Guard camera feed started")
            self.add_activity_log("✅ Guard camera feed started")
            
        except Exception as e:
            print(f"❌ Error initializing guard camera feed: {e}")
            self.add_activity_log(f"❌ Error initializing guard camera feed: {e}")
            # Try fallback method
            self.start_fallback_camera_feed()

    def initialize_live_camera_feed(self):
        """Initialize live camera feed for continuous monitoring"""
        try:
            # Initialize detection system for live feed
            if not hasattr(self, 'detection_system') or self.detection_system is None:
                self.detection_system = DetectionSystem()
                self.detection_system.main_ui = self  # Pass main UI reference
                print("✅ DetectionSystem initialized for live feed")
            
            # Start live camera feed (without specific person detection)
            success = self.detection_system.start_live_feed(ui_callback=self.update_camera_feed)
            if success:
                print("✅ Live camera feed started")
                self.add_activity_log("✅ Live camera feed started")
            else:
                print("❌ Failed to start live camera feed")
                self.add_activity_log("❌ Failed to start live camera feed")
                # Try fallback method
                self.start_fallback_camera_feed()
            
        except Exception as e:
            print(f"❌ Error initializing live camera feed: {e}")
            self.add_activity_log(f"❌ Error initializing live camera feed: {e}")
            # Try fallback method
            self.start_fallback_camera_feed()
    
    def start_guard_camera_feed(self):
        """Start camera feed for guard monitoring (no detection)"""
        try:
            print("🔧 Starting guard camera feed...")
            self.add_activity_log("🔧 Starting guard camera feed...")
            
            # Simple camera feed without detection
            import cv2
            import threading
            
            def guard_camera_loop():
                try:
                    # Use working camera configuration
                    camera_index = 0  # Camera 0 works with DirectShow
                    cap = cv2.VideoCapture(camera_index)
                    if not cap.isOpened():
                        print(f"❌ External camera (index {camera_index}) not found, trying built-in camera")
                        camera_index = 0  # Fallback to built-in camera
                        cap = cv2.VideoCapture(camera_index)
                        if not cap.isOpened():
                            print("❌ Guard camera failed to open")
                            return
                    else:
                        print(f"✅ Using external camera (index {camera_index}) for guard monitoring")
                    
                    # Use camera with default settings - no filters or adjustments
                    
                    frame_count = 0
                    while True:
                        ret, frame = cap.read()
                        if not ret:
                            continue
                        
                        frame_count += 1
                        
                        # Add guard monitoring status
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        cv2.putText(frame, "GUARD MONITORING", (10, 30), font, 0.8, (0, 255, 255), 2)
                        cv2.putText(frame, "Camera Active - No Detection", (10, 60), font, 0.6, (255, 255, 255), 2)
                        cv2.putText(frame, "Waiting for student RFID...", (10, 90), font, 0.5, (0, 255, 0), 2)
                        
                        # Update UI
                        self.update_camera_feed(frame)
                        
                        # Debug: Print every 30 frames
                        if frame_count % 30 == 0:
                            print(f"📹 Guard camera frame {frame_count} - Camera active: {cap.isOpened()}")
                        
                        time.sleep(0.033)
                        
                except Exception as e:
                    print(f"❌ Guard camera error: {e}")
                finally:
                    if 'cap' in locals():
                        cap.release()
                    print("🛑 Guard camera loop ended")
            
            # Start guard camera in separate thread
            self.guard_camera_thread = threading.Thread(target=guard_camera_loop, daemon=True)
            self.guard_camera_thread.start()
            print("✅ Guard camera feed started")
            
        except Exception as e:
            print(f"❌ Guard camera feed failed: {e}")
            self.add_activity_log(f"❌ Guard camera feed failed: {e}")

    def start_fallback_camera_feed(self):
        """Fallback camera feed when main detection system fails"""
        try:
            print("🔄 Starting fallback camera feed...")
            self.add_activity_log("🔄 Starting fallback camera feed...")
            
            # Simple camera feed without detection
            import cv2
            import threading
            
            def fallback_camera_loop():
                try:
                    # Use working camera configuration
                    camera_index = 0  # Camera 0 works with DirectShow
                    cap = cv2.VideoCapture(camera_index)
                    if not cap.isOpened():
                        print(f"❌ External camera (index {camera_index}) not found, trying built-in camera")
                        camera_index = 0  # Fallback to built-in camera
                        cap = cv2.VideoCapture(camera_index)
                        if not cap.isOpened():
                            print("❌ Fallback camera failed to open")
                            return
                    else:
                        print(f"✅ Using external camera (index {camera_index}) for fallback")
                    
                    # Use camera with default settings - no filters or adjustments
                    
                    while True:
                        ret, frame = cap.read()
                        if not ret:
                            continue
                        
                        # Add fallback status
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        cv2.putText(frame, "FALLBACK CAMERA FEED", (10, 30), font, 0.8, (0, 255, 255), 2)
                        cv2.putText(frame, "Basic camera only", (10, 60), font, 0.6, (255, 255, 255), 2)
                        
                        # Update UI
                        self.update_camera_feed(frame)
                        time.sleep(0.033)
                        
                except Exception as e:
                    print(f"❌ Fallback camera error: {e}")
                finally:
                    if 'cap' in locals():
                        cap.release()
            
            # Start fallback camera in separate thread
            fallback_thread = threading.Thread(target=fallback_camera_loop, daemon=True)
            fallback_thread.start()
            print("✅ Fallback camera feed started")
            
        except Exception as e:
            print(f"❌ Fallback camera feed failed: {e}")
            self.add_activity_log(f"❌ Fallback camera feed failed: {e}")
    
    def stop_guard_camera_feed(self):
        """Stop guard camera feed"""
        try:
            if hasattr(self, 'guard_camera_thread') and self.guard_camera_thread:
                # Set flag to stop the camera loop
                self.guard_camera_active = False
                print("🛑 Guard camera feed stopped")
                self.add_activity_log("🛑 Guard camera feed stopped")
        except Exception as e:
            print(f"❌ Error stopping guard camera feed: {e}")

    def switch_to_bsba_student_detection(self, rfid, person_name, course, gender):
        """Switch to BSBA student detection with appropriate model"""
        try:
            print(f"🔍 Switching to BSBA detection for {person_name} ({course}, {gender})")
            self.add_activity_log(f"🔍 Switching to BSBA detection for {person_name} ({course}, {gender})")
            
            # Determine the correct model based on gender
            if gender.upper() in ["MALE", "M"]:
                model_name = "bsba_male.pt"
                model_key = "BSBA_MALE"
            elif gender.upper() in ["FEMALE", "F"]:
                model_name = "bsba_female.pt"
                model_key = "BSBA_FEMALE"
            else:
                # Default to male if gender is unclear
                model_name = "bsba_male.pt"
                model_key = "BSBA_MALE"
                print(f"⚠️ Unknown gender '{gender}', defaulting to male model")
            
            print(f"📦 Selected model: {model_name} for {gender} student")
            self.add_activity_log(f"📦 Selected model: {model_name} for {gender} student")
            
            # Initialize detection system with specific model
            if not hasattr(self, 'detection_system') or self.detection_system is None:
                self.detection_system = DetectionSystem(model_path=model_name)
                self.detection_system.main_ui = self
            else:
                # Update model if different
                if self.detection_system.model_path != model_name:
                    self.detection_system.model_path = model_name
                    self.detection_system.model = YOLO(model_name)
            
            # Set current person info
            self.detection_system.current_person_id = rfid
            self.detection_system.current_person_name = person_name
            
            # Start detection with BSBA model
            success = self.detection_system.start_detection(rfid, person_name, "student", ui_callback=self.update_camera_feed)
            
            if success:
                print(f"✅ BSBA {gender} detection started for {person_name}")
                self.add_activity_log(f"✅ BSBA {gender} detection started for {person_name}")
            else:
                print(f"❌ Failed to start BSBA detection for {person_name}")
                self.add_activity_log(f"❌ Failed to start BSBA detection for {person_name}")
                
        except Exception as e:
            print(f"❌ Error switching to BSBA student detection: {e}")
            self.add_activity_log(f"❌ Error switching to BSBA student detection: {e}")

    def switch_to_student_detection(self, rfid, person_name, course, gender):
        """Switch from live feed to specific student detection"""
        try:
            if hasattr(self, 'detection_system') and self.detection_system:
                # Stop current live feed
                self.detection_system.stop_detection()
                
                # Set current person info for model selection
                self.detection_system.current_person_id = rfid
                self.detection_system.current_person_name = person_name
                
                # Start detection with appropriate model
                self.detection_system.start_detection(rfid, person_name, "student", ui_callback=self.update_camera_feed)
                print(f"✅ Switched to {course} {gender} detection for {person_name}")
                self.add_activity_log(f"✅ Switched to {course} {gender} detection for {person_name}")
            else:
                print("❌ Detection system not available")
                self.add_activity_log("❌ Detection system not available")
                
        except Exception as e:
            print(f"❌ Error switching to student detection: {e}")
            self.add_activity_log(f"❌ Error switching to student detection: {e}")
    
    def start_security_system(self):
        """Start the security dashboard"""
        if not self.current_guard_id:
            messagebox.showerror("Error", "Please login first")
            return
        
        try:
            print(f"🔍 Starting security system for guard: {self.current_guard_id}")
            
            # Create dashboard tab if it doesn't exist
            if self.dashboard_tab is None:
                print("🔍 Creating dashboard tab...")
                self.create_dashboard_tab()
                print("SUCCESS: Dashboard tab created")
            else:
                print("SUCCESS: Dashboard tab already exists")
            
            # Switch to dashboard tab
            print("🔍 Switching to dashboard tab...")
            self.notebook.select(self.dashboard_tab)
            self.notebook.hide(self.login_tab)
            print("SUCCESS: Switched to dashboard tab")
            
            # Initialize camera for guard (no detection, just live feed)
            print("🔍 Initializing camera for guard monitoring...")
            self.initialize_guard_camera_feed()
            print("SUCCESS: Guard camera feed initialized")
            
            # Open main screen for entry/exit monitoring
            print("🔍 Opening main screen...")
            self.open_main_screen()
            print("SUCCESS: Main screen opened")
            
            print("SUCCESS: Security dashboard started successfully")
            
        except Exception as e:
            print(f"ERROR: Error starting security dashboard: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to start security dashboard: {e}")
    
    def open_main_screen(self):
        """Open the main screen for entry/exit monitoring"""
        try:
            if self.main_screen_window is None or not self.main_screen_window.winfo_exists():
                self.create_main_screen()
            else:
                # Bring existing window to front
                self.main_screen_window.lift()
                self.main_screen_window.focus_force()
        except Exception as e:
            print(f"Error opening main screen: {e}")
            # Try to create a simple fallback window
            try:
                self.create_simple_main_screen()
            except Exception as e2:
                print(f"Failed to create fallback main screen: {e2}")
    
    def create_main_screen(self):
        """Create the main screen window for entry/exit monitoring"""
        try:
            # Create new window
            self.main_screen_window = tk.Toplevel(self.root)
            self.main_screen_window.title("AI-niform - Main Screen")
            self.main_screen_window.geometry("1200x800")
            self.main_screen_window.configure(bg='#f0f8ff')
            
            # Position Main Screen on secondary monitor if available
            if self.screen_info['secondary']:
                secondary = self.screen_info['secondary']
                # Set fullscreen on secondary monitor
                self.main_screen_window.geometry(f"{secondary['width']}x{secondary['height']}+{secondary['x']}+{secondary['y']}")
                
                # Try to make fullscreen on secondary monitor
                try:
                    # Method 1: Try fullscreen attribute (most reliable on Linux)
                    self.main_screen_window.attributes('-fullscreen', True)
                    print(f"SUCCESS: Main Screen fullscreen on secondary monitor: {secondary['width']}x{secondary['height']} at ({secondary['x']}, {secondary['y']})")
                except Exception as e1:
                    print(f"ERROR: Main Screen fullscreen attribute failed: {e1}")
                    try:
                        # Method 2: Try overrideredirect (removes window decorations)
                        self.main_screen_window.overrideredirect(True)
                        self.main_screen_window.geometry(f"{secondary['width']}x{secondary['height']}+{secondary['x']}+{secondary['y']}")
                        print(f"SUCCESS: Main Screen fullscreen on secondary monitor using overrideredirect: {secondary['width']}x{secondary['height']}")
                    except Exception as e2:
                        print(f"ERROR: Main Screen overrideredirect failed: {e2}")
                        try:
                            # Method 3: Try zoomed attribute
                            self.main_screen_window.attributes('-zoomed', True)
                            print(f"SUCCESS: Main Screen maximized on secondary monitor: {secondary['width']}x{secondary['height']}")
                        except Exception as e3:
                            print(f"ERROR: Main Screen zoomed failed: {e3}")
                            print(f"🖥️ Main Screen positioned on secondary monitor at ({secondary['x']}, {secondary['y']})")
            else:
                # Fallback: position on primary monitor but offset
                primary = self.screen_info['primary']
                offset_x = primary['width'] // 4
                offset_y = primary['height'] // 4
                self.main_screen_window.geometry(f"1200x800+{offset_x}+{offset_y}")
                print(f"🖥️ Main Screen positioned on primary monitor at ({offset_x}, {offset_y})")
                
        except Exception as e:
            print(f"ERROR: Failed to create main screen window: {e}")
            # Try fallback approach
            try:
                self.create_simple_main_screen()
                return
            except Exception as e2:
                print(f"ERROR: Failed to create fallback main screen: {e2}")
                return
        
        # Add keyboard controls for Main Screen fullscreen
        self.main_screen_window.bind('<F11>', self.toggle_main_screen_fullscreen)
        self.main_screen_window.bind('<Escape>', self.exit_main_screen_fullscreen)
        
        # Prevent window from being closed accidentally
        self.main_screen_window.protocol("WM_DELETE_WINDOW", self.minimize_main_screen)
        
        # Create main screen content
        self.create_main_screen_content()
        
        # Start monitoring loop
        self.start_main_screen_monitoring()
    
    def create_simple_main_screen(self):
        """Create a simple fallback main screen"""
        try:
            self.main_screen_window = tk.Toplevel(self.root)
            self.main_screen_window.title("AI-niform - Main Screen (Simple)")
            self.main_screen_window.geometry("800x600")
            self.main_screen_window.configure(bg='#f0f8ff')
            
            # Simple content
            label = tk.Label(
                self.main_screen_window,
                text="AI-niform Main Screen\n\nSimple fallback mode\n\nSystem is running normally",
                font=('Arial', 16),
                bg='#f0f8ff',
                fg='#1e3a8a'
            )
            label.pack(expand=True)
            
            print("SUCCESS: Simple main screen created")
            
        except Exception as e:
            print(f"ERROR: Failed to create simple main screen: {e}")
    
    def create_main_screen_content(self):
        """Create the main screen content"""
        # Header
        header_frame = tk.Frame(self.main_screen_window, bg='#1e3a8a', height=80)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # Title
        title_label = tk.Label(
            header_frame,
            text="AI-niform Security System - Entry/Exit Monitoring",
            font=('Arial', 24, 'bold'),
            fg='#ffffff',
            bg='#1e3a8a'
        )
        title_label.pack(side=tk.LEFT, padx=20, pady=20)
        
        # Current time
        self.time_label = tk.Label(
            header_frame,
            text="",
            font=('Arial', 16, 'bold'),
            fg='#ffffff',
            bg='#1e3a8a'
        )
        self.time_label.pack(side=tk.RIGHT, padx=20, pady=20)
        
        # Main content area
        main_content = tk.Frame(self.main_screen_window, bg='#f0f8ff')
        main_content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Current person display (large center area)
        current_person_frame = tk.LabelFrame(
            main_content,
            text="Current Person",
            font=('Arial', 18, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='solid',
            bd=2
        )
        current_person_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Person info display
        self.person_display_frame = tk.Frame(current_person_frame, bg='#ffffff')
        self.person_display_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Initialize with standby message
        self.show_standby_message()
        
        # Recent entries list (bottom area)
        recent_frame = tk.LabelFrame(
            main_content,
            text="Recent Entries/Exits",
            font=('Arial', 14, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='solid',
            bd=2
        )
        recent_frame.pack(fill=tk.X, pady=(0, 0))
        
        # Recent entries listbox
        self.recent_entries_listbox = tk.Listbox(
            recent_frame,
            font=('Arial', 12),
            bg='#ffffff',
            fg='#1e3a8a',
            selectbackground='#3b82f6',
            height=6
        )
        self.recent_entries_listbox.pack(fill=tk.X, padx=10, pady=10)
        
        # Add scrollbar for recent entries
        scrollbar = tk.Scrollbar(recent_frame, orient=tk.VERTICAL, command=self.recent_entries_listbox.yview)
        self.recent_entries_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def show_standby_message(self):
        """Show standby message when no one is detected"""
        # Clear previous content
        for widget in self.person_display_frame.winfo_children():
            widget.destroy()
        
        standby_label = tk.Label(
            self.person_display_frame,
            text="🔒 SYSTEM STANDBY\n\nWaiting for person detection...",
            font=('Arial', 32, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            justify=tk.CENTER
        )
        standby_label.pack(expand=True)
    
    def display_person_info(self, person_data):
        """Display person information on main screen"""
        # Clear previous content
        for widget in self.person_display_frame.winfo_children():
            widget.destroy()
        
        # Person type and status
        status_frame = tk.Frame(self.person_display_frame, bg='#ffffff')
        status_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Person type
        person_type_label = tk.Label(
            status_frame,
            text=f"Type: {person_data.get('type', 'Unknown').upper()}",
            font=('Arial', 20, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        )
        person_type_label.pack(side=tk.LEFT)
        
        # Entry/Exit status
        if person_data.get('status') == 'COMPLETE UNIFORM':
            status_color = '#10b981'  # Green for complete uniform
            status_text = "COMPLETE UNIFORM SUCCESS:"
        elif person_data.get('action') == 'ENTRY':
            status_color = '#10b981'  # Green for entry
            status_text = f"Status: {person_data.get('action', 'UNKNOWN')}"
        else:
            status_color = '#f59e0b'  # Orange for exit
            status_text = f"Status: {person_data.get('action', 'UNKNOWN')}"
        
        status_label = tk.Label(
            status_frame,
            text=status_text,
            font=('Arial', 20, 'bold'),
            fg=status_color,
            bg='#ffffff'
        )
        status_label.pack(side=tk.RIGHT)
        
        # Person details
        details_frame = tk.Frame(self.person_display_frame, bg='#ffffff')
        details_frame.pack(fill=tk.BOTH, expand=True)
        
        # Name
        name_label = tk.Label(
            details_frame,
            text=f"Name: {person_data.get('name', 'Unknown')}",
            font=('Arial', 24, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        )
        name_label.pack(pady=(0, 10))
        
        # ID
        id_label = tk.Label(
            details_frame,
            text=f"ID: {person_data.get('id', 'Unknown')}",
            font=('Arial', 18, 'bold'),
            fg='#374151',
            bg='#ffffff'
        )
        id_label.pack(pady=(0, 10))
        
        # Additional info based on type
        if person_data.get('type') == 'student':
            course_label = tk.Label(
                details_frame,
                text=f"Course: {person_data.get('course', 'Unknown')}",
                font=('Arial', 16, 'bold'),
                fg='#3b82f6',
                bg='#ffffff'
            )
            course_label.pack(pady=(0, 5))
            
            gender_label = tk.Label(
                details_frame,
                text=f"Gender: {person_data.get('gender', 'Unknown')}",
                font=('Arial', 16, 'bold'),
                fg='#3b82f6',
                bg='#ffffff'
            )
            gender_label.pack(pady=(0, 5))
        
        elif person_data.get('type') == 'visitor':
            company_label = tk.Label(
                details_frame,
                text=f"Company: {person_data.get('company', 'N/A')}",
                font=('Arial', 16, 'bold'),
                fg='#3b82f6',
                bg='#ffffff'
            )
            company_label.pack(pady=(0, 5))
            
            purpose_label = tk.Label(
                details_frame,
                text=f"Purpose: {person_data.get('purpose', 'General Visit')}",
                font=('Arial', 16, 'bold'),
                fg='#3b82f6',
                bg='#ffffff'
            )
            purpose_label.pack(pady=(0, 5))
        
        # Time
        time_label = tk.Label(
            details_frame,
            text=f"Time: {person_data.get('timestamp', 'Unknown')}",
            font=('Arial', 14, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        )
        time_label.pack(pady=(20, 0))
        
        # Add to recent entries
        self.add_to_recent_entries(person_data)
    
    def add_to_recent_entries(self, person_data):
        """Add person to recent entries list"""
        timestamp = person_data.get('timestamp', 'Unknown')
        name = person_data.get('name', 'Unknown')
        person_type = person_data.get('type', 'Unknown')
        action = person_data.get('action', 'Unknown')
        
        entry_text = f"[{timestamp}] {name} ({person_type.upper()}) - {action}"
        
        # Insert at the beginning
        self.recent_entries_listbox.insert(0, entry_text)
        
        # Keep only last 20 entries
        if self.recent_entries_listbox.size() > 20:
            self.recent_entries_listbox.delete(20, tk.END)
    
    def start_main_screen_monitoring(self):
        """Start monitoring for main screen updates"""
        self.update_main_screen_time()
        # Schedule periodic updates
        self.main_screen_window.after(1000, self.start_main_screen_monitoring)
    
    def update_main_screen_time(self):
        """Update the time display on main screen"""
        if self.main_screen_window and self.main_screen_window.winfo_exists():
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.time_label.config(text=current_time)
    
    def minimize_main_screen(self):
        """Minimize main screen instead of closing"""
        if self.main_screen_window:
            self.main_screen_window.iconify()
    
    def close_main_screen(self):
        """Close the main screen window"""
        if self.main_screen_window:
            self.main_screen_window.destroy()
            self.main_screen_window = None
    
    def update_main_screen_person(self, person_data):
        """Update main screen with new person data"""
        if self.main_screen_window and self.main_screen_window.winfo_exists():
            self.display_person_info(person_data)
    
    def update_main_screen_with_person_info(self, person_id, person_name, person_type):
        """Update main screen when person taps their ID"""
        try:
            if not self.main_screen_window or not self.main_screen_window.winfo_exists():
                return
            
            # Create person data
            person_data = {
                'id': person_id,
                'name': person_name,
                'type': person_type,
                'action': 'ENTRY',  # Default to entry when ID is tapped
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'status': 'DETECTING',
                'confidence': 0.0,
                'class_name': 'initializing'
            }
            
            # Add additional info based on person type
            if person_type.lower() == 'student':
                # Get student info from credentials
                student_info = self.get_student_info(person_id)
                if student_info:
                    person_data.update(student_info)
            
            elif person_type.lower() == 'visitor':
                # Add visitor-specific info
                person_data['company'] = 'N/A'
                person_data['purpose'] = 'General Visit'
            
            # Update main screen immediately
            self.display_person_info(person_data)
            
            print(f"SUCCESS: Main screen updated with {person_type}: {person_name} ({person_id})")
            
        except Exception as e:
            print(f"ERROR: Error updating main screen with person info: {e}")
    
    def update_main_screen_with_exit(self, person_id, person_type):
        """Update main screen when person exits"""
        try:
            if not self.main_screen_window or not self.main_screen_window.winfo_exists():
                return
            
            # Get person name
            person_name = self.get_person_name(person_id, person_type)
            
            # Create person data for exit
            person_data = {
                'id': person_id,
                'name': person_name,
                'type': person_type,
                'action': 'EXIT',
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'status': 'EXITED',
                'confidence': 1.0,
                'class_name': 'exit'
            }
            
            # Add additional info based on person type
            if person_type.lower() == 'student':
                # Get student info from credentials
                student_info = self.get_student_info(person_id)
                if student_info:
                    person_data.update(student_info)
            
            elif person_type.lower() == 'visitor':
                # Add visitor-specific info
                person_data['company'] = 'N/A'
                person_data['purpose'] = 'General Visit'
            
            # Update main screen with exit information
            self.display_person_info(person_data)
            
            print(f"SUCCESS: Main screen updated with {person_type} exit: {person_name} ({person_id})")
            
        except Exception as e:
            print(f"ERROR: Error updating main screen with exit info: {e}")
    
    def test_main_screen_display(self):
        """Test function to display sample data on main screen"""
        try:
            # Sample person data for testing
            test_person_data = {
                'id': '02000289900',
                'name': 'John Doe',
                'type': 'student',
                'action': 'ENTRY',
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'course': 'ICT',
                'gender': 'Male',
                'status': 'COMPLIANT',
                'confidence': 0.95,
                'class_name': 'uniform_detected'
            }
            
            # Update main screen with test data
            self.update_main_screen_person(test_person_data)
            
            print("SUCCESS: Test data displayed on main screen")
            
        except Exception as e:
            print(f"ERROR: Error testing main screen: {e}")
    
    def debug_firebase_student_ui(self):
        """UI function to debug Firebase student data"""
        try:
            # Get student ID from user input
            student_id = tk.simpledialog.askstring(
                "Debug Firebase Student",
                "Enter Student ID to check in Firebase:",
                initialvalue="02000289900"
            )
            
            if student_id:
                # Call debug function
                result = self.debug_firebase_student(student_id)
                
                # Show result in message box
                if result:
                    message = f"Student ID: {student_id}\n\n"
                    message += f"Name: {result.get('name', 'Not found')}\n"
                    message += f"Course: {result.get('course', 'Not found')}\n"
                    message += f"Gender: {result.get('gender', 'Not found')}\n\n"
                    message += f"Full Data: {result}"
                    messagebox.showinfo("Firebase Student Data", message)
                else:
                    messagebox.showerror("Student Not Found", 
                                       f"Student ID '{student_id}' not found in Firebase students collection.")
            
        except Exception as e:
            messagebox.showerror("Debug Error", f"Error checking Firebase student: {e}")
    
    def logout_guard(self):
        """Logout the guard and close camera"""
        try:
            # Save guard logout to Firebase before clearing session data
            if hasattr(self, 'current_guard_id') and self.current_guard_id:
                self.save_guard_logout_to_firebase(self.current_guard_id)
            
            # Stop any active detection and close camera
            if self.detection_active:
                self.stop_detection()
            
            # Reset camera to standby
            self.reset_camera_to_standby()
            
            # Close main screen
            self.close_main_screen()
            
            # Clear session data
            self.current_guard_id = None
            self.session_id = None
            self.login_status_var.set("Not Logged In")
            
            # Re-enable login button
            self.manual_login_btn.config(state=tk.NORMAL)
            
            # Switch back to login tab
            self.notebook.select(self.login_tab)
            self.notebook.hide(self.dashboard_tab)
            
            print("🔓 Guard logged out - Camera closed")
            messagebox.showinfo("Logout", "Guard logged out successfully. Camera is now closed.")
            
        except Exception as e:
            print(f"ERROR: Error during logout: {e}")
            messagebox.showerror("Error", f"Logout failed: {e}")
    
    def create_dashboard_tab(self):
        """Create the dashboard tab"""
        try:
            print("🔍 Creating dashboard tab...")
            self.dashboard_tab = tk.Frame(self.notebook, bg='#ffffff')
            self.notebook.add(self.dashboard_tab, text="📊 AI-niform Dashboard")
            print("SUCCESS: Dashboard tab added to notebook")
            
            # Create dashboard content
            print("🔍 Creating dashboard content...")
            self.create_dashboard_content(self.dashboard_tab)
            print("SUCCESS: Dashboard content created")
            
        except Exception as e:
            print(f"ERROR: Error creating dashboard tab: {e}")
            import traceback
            traceback.print_exc()
            raise e
    
    def create_dashboard_content(self, parent):
        """Create dashboard content"""
        # Main container
        main_container = tk.Frame(parent, bg='#ffffff')
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Header
        self.create_header(main_container)
        
        # Content area
        content_frame = tk.Frame(main_container, bg='#ffffff')
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))
        
        # Left column - Camera Feed
        left_column = tk.Frame(content_frame, bg='#ffffff', width=400)
        left_column.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_column.pack_propagate(False)
        
        self.create_camera_feed_section(left_column)
        
        # Right column - Person ID Entry and Logs
        right_column = tk.Frame(content_frame, bg='#ffffff')
        right_column.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        # Create a container for person entry with fixed width
        person_entry_container = tk.Frame(right_column, bg='#ffffff', width=400)
        person_entry_container.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        person_entry_container.pack_propagate(False)
        
        # Create logs container that takes remaining space
        logs_container = tk.Frame(right_column, bg='#ffffff')
        logs_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.create_person_entry_section(person_entry_container)
        self.create_gate_control_section(person_entry_container)
        self.create_activity_logs_section(logs_container)
    
    def create_person_entry_section(self, parent):
        """Create person ID entry section"""
        entry_frame = tk.LabelFrame(
            parent,
            text="👥 Person ID Entry",
            font=('Arial', 12, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        entry_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Special action buttons
        type_frame = tk.Frame(entry_frame, bg='#ffffff')
        type_frame.pack(fill=tk.X, padx=15, pady=(15, 12))
        
        # Special buttons row
        special_buttons_frame = tk.Frame(type_frame, bg='#ffffff')
        special_buttons_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Student who forgot ID button - much larger
        self.forgot_id_btn = tk.Button(
            special_buttons_frame,
            text="🔑 Student Forgot ID",
            command=self.handle_forgot_id,
            font=('Arial', 12, 'bold'),
            bg='#f59e0b',
            fg='white',
            relief='raised',
            bd=3,
            padx=20,
            pady=12,
            cursor='hand2',
            activebackground='#d97706',
            activeforeground='white'
        )
        self.forgot_id_btn.pack(side=tk.LEFT, padx=(0, 8), fill=tk.X, expand=True)
        
        # Manual visitor entry button - much larger
        self.manual_visitor_btn = tk.Button(
            special_buttons_frame,
            text="📝 Visitor",
            command=self.handle_manual_visitor,
            font=('Arial', 12, 'bold'),
            bg='#10b981',
            fg='white',
            relief='raised',
            bd=3,
            padx=20,
            pady=12,
            cursor='hand2',
            activebackground='#059669',
            activeforeground='white'
        )
        self.manual_visitor_btn.pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)
        
        # Gate control section
        gate_control_frame = tk.LabelFrame(
            entry_frame,
            text="🚪 Gate Control",
            font=('Arial', 16, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='groove',
            bd=3
        )
        gate_control_frame.pack(fill=tk.X, padx=15, pady=(15, 20))
        
        # Gate control buttons
        gate_buttons_frame = tk.Frame(gate_control_frame, bg='#ffffff')
        gate_buttons_frame.pack(fill=tk.X, padx=15, pady=15)
        
        # Approve button - opens gate
        self.approve_btn = tk.Button(
            gate_buttons_frame,
            text="SUCCESS: APPROVE",
            command=self.approve_gate,
            font=('Arial', 12, 'bold'),
            bg='#10b981',
            fg='white',
            relief='raised',
            bd=2,
            padx=15,
            pady=10,
            cursor='hand2',
            activebackground='#059669',
            activeforeground='white'
        )
        self.approve_btn.pack(side=tk.LEFT, padx=(0, 5), fill=tk.X, expand=True)
        
        # Deny button - closes gate
        self.deny_btn = tk.Button(
            gate_buttons_frame,
            text="ERROR: DENY",
            command=self.deny_gate,
            font=('Arial', 12, 'bold'),
            bg='#dc2626',
            fg='white',
            relief='raised',
            bd=2,
            padx=15,
            pady=10,
            cursor='hand2',
            activebackground='#b91c1c',
            activeforeground='white'
        )
        self.deny_btn.pack(side=tk.LEFT, padx=(5, 0), fill=tk.X, expand=True)
        
        # Manual ID input
        input_frame = tk.Frame(entry_frame, bg='#ffffff')
        input_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        id_label = tk.Label(
            input_frame,
            text="Person ID:",
            font=('Arial', 15, 'bold'),
            fg='#374151',
            bg='#ffffff'
        )
        id_label.pack(anchor=tk.W, pady=(0, 8))
        
        self.person_id_entry = tk.Entry(
            input_frame,
            textvariable=self.person_id_var,
            font=('Arial', 20, 'bold'),
            width=20,
            justify=tk.CENTER,
            relief='solid',
            bd=4,
            bg='#e0f2fe',
            fg='#1e3a8a',
            insertbackground='#1e3a8a'
        )
        self.person_id_entry.pack(fill=tk.X, pady=(0, 10), padx=8)
        self.person_id_entry.bind('<Return>', lambda e: self.log_person_entry())
        
        # Log Entry button - much larger and more prominent
        self.manual_entry_btn = tk.Button(
            input_frame,
            text="SUCCESS: Log Entry",
            command=self.log_person_entry,
            font=('Arial', 16, 'bold'),
            bg='#3b82f6',
            fg='white',
            relief='raised',
            bd=4,
            padx=30,
            pady=15,
            cursor='hand2',
            activebackground='#2563eb',
            activeforeground='white'
        )
        self.manual_entry_btn.pack(fill=tk.X, pady=(0, 5))
    
    def handle_forgot_id(self):
        """Handle student who forgot their ID - open student verification tab"""
        try:
            # Create student forgot ID tab
            self.create_student_forgot_tab()
            
            # Switch to student forgot tab
            self.notebook.select(self.student_forgot_tab)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open student verification: {e}")
    
    def create_student_forgot_tab(self):
        """Create student forgot ID verification tab"""
        if self.student_forgot_tab is None:
            self.student_forgot_tab = tk.Frame(self.notebook, bg='#ffffff')
            self.notebook.add(self.student_forgot_tab, text="🔑 Student ID Verification")
            
            # Create student verification form content
            self.create_student_verification_form(self.student_forgot_tab)
    
    def create_student_verification_form(self, parent):
        """Create student ID verification form"""
        # Main container
        main_frame = tk.Frame(parent, bg='#ffffff')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Header with back button
        header_frame = tk.Frame(main_frame, bg='#ffffff')
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Back button at top
        back_btn = tk.Button(
            header_frame,
            text="← Back to Dashboard",
            command=self.back_to_dashboard,
            font=('Arial', 12, 'bold'),
            bg='#6b7280',
            fg='white',
            relief='raised',
            bd=3,
            padx=20,
            pady=8,
            cursor='hand2',
            activebackground='#4b5563',
            activeforeground='white'
        )
        back_btn.pack(anchor=tk.W, pady=(0, 10))
        
        title_label = tk.Label(
            header_frame,
            text="🔑 Student ID Verification",
            font=('Arial', 24, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            header_frame,
            text="Enter student ID number to verify and link with available RFID",
            font=('Arial', 14),
            fg='#6b7280',
            bg='#ffffff'
        )
        subtitle_label.pack(pady=(5, 0))
        
        # Student ID input section
        id_input_frame = tk.LabelFrame(
            main_frame,
            text="Student ID Verification",
            font=('Arial', 14, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        id_input_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Student ID input
        id_input_content = tk.Frame(id_input_frame, bg='#ffffff')
        id_input_content.pack(fill=tk.X, padx=15, pady=15)
        
        id_label = tk.Label(
            id_input_content,
            text="Student ID Number:",
            font=('Arial', 14, 'bold'),
            fg='#374151',
            bg='#ffffff'
        )
        id_label.pack(anchor=tk.W, pady=(0, 10))
        
        self.student_id_entry = tk.Entry(
            id_input_content,
            font=('Arial', 16, 'bold'),
            width=25,
            justify=tk.CENTER,
            relief='solid',
            bd=3,
            bg='#f0f9ff',
            fg='#1e3a8a',
            insertbackground='#1e3a8a'
        )
        self.student_id_entry.pack(fill=tk.X, pady=(0, 15))
        self.student_id_entry.bind('<Return>', lambda e: self.verify_student_id())
        
        # Verify button
        verify_btn = tk.Button(
            id_input_content,
            text="🔍 Verify Student ID",
            command=self.verify_student_id,
            font=('Arial', 12, 'bold'),
            bg='#3b82f6',
            fg='white',
            relief='raised',
            bd=2,
            padx=20,
            pady=8,
            cursor='hand2',
            activebackground='#2563eb',
            activeforeground='white'
        )
        verify_btn.pack(fill=tk.X, pady=(0, 5))
        
        # Student info display (initially hidden)
        self.student_info_frame = tk.LabelFrame(
            main_frame,
            text="Student Information",
            font=('Arial', 14, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        self.student_info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # RFID assignment section (initially hidden)
        self.rfid_assignment_frame = tk.LabelFrame(
            main_frame,
            text="📡 RFID Assignment",
            font=('Arial', 14, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        self.rfid_assignment_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Action buttons - always visible at bottom
        buttons_frame = tk.Frame(main_frame, bg='#ffffff')
        buttons_frame.pack(fill=tk.X, pady=(10, 0), side=tk.BOTTOM)
        
        # Assign RFID button (initially hidden)
        self.assign_rfid_btn = tk.Button(
            buttons_frame,
            text="SUCCESS: Assign RFID",
            command=self.assign_rfid_to_student,
            font=('Arial', 11, 'bold'),
            bg='#10b981',
            fg='white',
            relief='raised',
            bd=2,
            padx=20,
            pady=8,
            cursor='hand2',
            activebackground='#059669',
            activeforeground='white'
        )
        self.assign_rfid_btn.pack(side=tk.RIGHT)
        self.assign_rfid_btn.pack_forget()  # Initially hidden
    
    def verify_student_id(self):
        """Verify student ID in Firebase and student credentials"""
        try:
            student_id = self.student_id_entry.get().strip()
            
            if not student_id:
                messagebox.showerror("Error", "Please enter a student ID number.")
                return
            
            # Check in Firebase students collection
            student_info = self.get_student_info(student_id)
            
            if not student_info or student_info.get('name') == 'Unknown':
                messagebox.showerror("Invalid Number", 
                                   f"Student ID '{student_id}' is invalid.\n\n"
                                   "Please enter a valid student ID number.")
                return
            
            # Display student information
            self.display_student_info(student_info)
            
            # Show RFID assignment section
            self.show_rfid_assignment()
            
            # Add to activity log
            self.add_activity_log(f"Student ID verified: {student_info['name']} ({student_info['course']}) - ID: {student_id}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to verify student ID: {e}")
    
    def display_student_info(self, student_info):
        """Display verified student information"""
        # Clear previous content
        for widget in self.student_info_frame.winfo_children():
            widget.destroy()
        
        info_content = tk.Frame(self.student_info_frame, bg='#ffffff')
        info_content.pack(fill=tk.X, padx=20, pady=20)
        
        # Student details
        name_label = tk.Label(
            info_content,
            text=f"Name: {student_info['name']}",
            font=('Arial', 14, 'bold'),
            fg='#374151',
            bg='#ffffff'
        )
        name_label.pack(anchor=tk.W, pady=(0, 5))
        
        course_label = tk.Label(
            info_content,
            text=f"Course: {student_info['course']}",
            font=('Arial', 14, 'bold'),
            fg='#374151',
            bg='#ffffff'
        )
        course_label.pack(anchor=tk.W, pady=(0, 5))
        
        gender_label = tk.Label(
            info_content,
            text=f"Gender: {student_info['gender']}",
            font=('Arial', 14, 'bold'),
            fg='#374151',
            bg='#ffffff'
        )
        gender_label.pack(anchor=tk.W, pady=(0, 5))
        
        id_label = tk.Label(
            info_content,
            text=f"Student ID: {self.student_id_entry.get()}",
            font=('Arial', 14, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        )
        id_label.pack(anchor=tk.W, pady=(5, 0))
    
    def show_rfid_assignment(self):
        """Show RFID assignment section"""
        # Clear previous content
        for widget in self.rfid_assignment_frame.winfo_children():
            widget.destroy()
        
        rfid_content = tk.Frame(self.rfid_assignment_frame, bg='#ffffff')
        rfid_content.pack(fill=tk.X, padx=20, pady=20)
        
        # Title section
        title_frame = tk.Frame(rfid_content, bg='#ffffff')
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        rfid_title_label = tk.Label(
            title_frame,
            text="📡 RFID Assignment for Student",
            font=('Arial', 16, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        )
        rfid_title_label.pack()
        
        rfid_subtitle_label = tk.Label(
            title_frame,
            text="Select an available empty RFID card to assign to this student",
            font=('Arial', 12),
            fg='#6b7280',
            bg='#ffffff'
        )
        rfid_subtitle_label.pack(pady=(5, 0))
        
        # Available RFID selection with enhanced visibility
        rfid_selection_frame = tk.Frame(rfid_content, bg='#f8fafc', relief='solid', bd=2)
        rfid_selection_frame.pack(fill=tk.X, pady=(0, 15))
        
        rfid_selection_content = tk.Frame(rfid_selection_frame, bg='#f8fafc')
        rfid_selection_content.pack(fill=tk.X, padx=15, pady=15)
        
        rfid_label = tk.Label(
            rfid_selection_content,
            text="Available Empty RFID Cards:",
            font=('Arial', 14, 'bold'),
            fg='#1e3a8a',
            bg='#f8fafc'
        )
        rfid_label.pack(anchor=tk.W, pady=(0, 10))
        
        # RFID dropdown with larger size
        self.student_rfid_var = tk.StringVar()
        self.student_rfid_dropdown = ttk.Combobox(
            rfid_selection_content,
            textvariable=self.student_rfid_var,
            font=('Arial', 16, 'bold'),
            state='readonly',
            width=20
        )
        
        # Generate available RFID list
        self.update_student_rfid_list()
        
        self.student_rfid_dropdown.pack(fill=tk.X, pady=(0, 15))
        
        
        # Refresh button with better visibility
        refresh_btn = tk.Button(
            rfid_selection_content,
            text="INFO: Refresh RFID List",
            command=self.update_student_rfid_list,
            font=('Arial', 12, 'bold'),
            bg='#3b82f6',
            fg='white',
            relief='raised',
            bd=2,
            padx=15,
            pady=8,
            cursor='hand2',
            activebackground='#2563eb',
            activeforeground='white'
        )
        refresh_btn.pack(anchor=tk.W, pady=(5, 0))
        
        # Show assign button
        self.assign_rfid_btn.pack(side=tk.RIGHT)
    
    
    def show_rfid_assignment(self):
        """Show RFID assignment section"""
        # Clear previous content
        for widget in self.rfid_assignment_frame.winfo_children():
            widget.destroy()
        
        rfid_content = tk.Frame(self.rfid_assignment_frame, bg='#ffffff')
        rfid_content.pack(fill=tk.X, padx=15, pady=10)
        
        # Compact RFID selection
        rfid_label = tk.Label(
            rfid_content,
            text="Available Empty RFID Cards:",
            font=('Arial', 12, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        )
        rfid_label.pack(anchor=tk.W, pady=(0, 5))
        
        # RFID dropdown
        self.student_rfid_var = tk.StringVar()
        self.student_rfid_dropdown = ttk.Combobox(
            rfid_content,
            textvariable=self.student_rfid_var,
            font=('Arial', 12, 'bold'),
            state='readonly',
            width=25
        )
        
        # Generate available RFID list
        self.update_student_rfid_list()
        
        self.student_rfid_dropdown.pack(fill=tk.X, pady=(0, 8))
        
        
        # Refresh button
        refresh_btn = tk.Button(
            rfid_content,
            text="INFO: Refresh RFID List",
            command=self.update_student_rfid_list,
            font=('Arial', 10, 'bold'),
            bg='#3b82f6',
            fg='white',
            relief='raised',
            bd=2,
            padx=10,
            pady=5,
            cursor='hand2',
            activebackground='#2563eb',
            activeforeground='white'
        )
        refresh_btn.pack(anchor=tk.W, pady=(0, 5))
        
        # Show assign button
        self.assign_rfid_btn.pack(side=tk.RIGHT)
    
    
    def update_student_rfid_list(self):
        """Update the list of available RFID cards for student forgot ID from Firebase"""
        try:
            available_rfids = []
            
            # Load RFID cards from Firebase Empty RFID collection
            if self.firebase_initialized and self.db:
                print("INFO: Loading RFID cards for student forgot ID from Firebase...")
                empty_rfid_ref = self.db.collection('Empty RFID')
                docs = empty_rfid_ref.get()
                
                for doc in docs:
                    rfid_data = doc.to_dict()
                    rfid_id = doc.id
                    
                    # Since you removed all fields, documents are now empty {}
                    # All RFID documents are available unless they have assignment fields
                    is_available = True
                    
                    # Check if document has any assignment data
                    if rfid_data:  # If document has any fields
                        if 'assigned_to' in rfid_data and rfid_data['assigned_to']:
                            is_available = False
                        elif 'available' in rfid_data and not rfid_data['available']:
                            is_available = False
                    
                    # Since documents are empty {}, they are all available
                    if is_available:
                        available_rfids.append(rfid_id)
                        print(f"INFO: Available RFID for student forgot ID: {rfid_id} - Data: {rfid_data}")
                    else:
                        print(f"INFO: Unavailable RFID: {rfid_id} - Data: {rfid_data}")
                
                print(f"SUCCESS: Loaded {len(available_rfids)} available RFID cards from Firebase")
            else:
                print("WARNING: Firebase not available - using empty list")
                available_rfids = []
            
            # Update the dropdown
            self.student_rfid_dropdown['values'] = available_rfids
            # Leave dropdown blank initially - no pre-selection
            self.student_rfid_var.set("")
            
        except Exception as e:
            print(f"ERROR: Error updating student RFID list: {e}")
            self.student_rfid_dropdown['values'] = []
            self.student_rfid_var.set("")
    
    def assign_rfid_to_student(self):
        """Assign RFID to verified student for forgot ID"""
        try:
            student_id = self.student_id_entry.get().strip()
            selected_rfid = self.student_rfid_var.get()
            
            if not selected_rfid:
                messagebox.showerror("Error", "Please select an available RFID card.")
                return
            
            # Check if RFID is already assigned
            if selected_rfid in self.student_rfid_assignments:
                messagebox.showerror("Error", f"RFID {selected_rfid} is already assigned to another student.")
                return
            
            # Get student info
            student_info = self.get_student_info(student_id)
            
            # Create temporary assignment record
            assignment_info = {
                'student_id': student_id,
                'name': student_info['name'],
                'course': student_info['course'],
                'gender': student_info['gender'],
                'rfid': selected_rfid,
                'assignment_time': self.get_current_timestamp(),
                'status': 'active'  # active, returned
            }
            
            # Link student to RFID
            self.student_rfid_assignments[selected_rfid] = assignment_info
            
            # Remove from available RFID list
            if selected_rfid in self.student_forgot_rfids:
                self.student_forgot_rfids.remove(selected_rfid)
            
            # Save to Firebase
            self.save_student_rfid_assignment_to_firebase(assignment_info)
            
            # Add to activity log
            self.add_activity_log(f"Temporary RFID assigned to student: {student_info['name']} ({student_info['course']}) - Student ID: {student_id} - RFID: {selected_rfid}")
            
            # Show confirmation
            self.show_green_success_message("RFID Assigned Successfully", 
                              f"Student Details:\n"
                              f"Name: {student_info['name']}\n"
                              f"Course: {student_info['course']}\n"
                              f"Gender: {student_info['gender']}\n"
                              f"Student ID: {student_id}\n"
                              f"Assigned RFID: {selected_rfid}\n\n"
                              f"The student can now use the RFID card for entry and exit.")
            
            # Clear form
            self.student_id_entry.delete(0, tk.END)
            self.student_rfid_var.set("")
            
            # Hide sections
            for widget in self.student_info_frame.winfo_children():
                widget.destroy()
            for widget in self.rfid_assignment_frame.winfo_children():
                widget.destroy()
            self.assign_rfid_btn.pack_forget()
            
            # Return to dashboard
            self.back_to_dashboard()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to assign RFID: {e}")
    
    def handle_manual_visitor(self):
        """Handle manual visitor entry - open visitor information tab"""
        try:
            # Create visitor information tab
            self.create_visitor_tab()
            
            # Switch to visitor tab
            self.notebook.select(self.visitor_tab)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open visitor form: {e}")
    
    def create_visitor_tab(self):
        """Create visitor information tab"""
        if self.visitor_tab is None:
            self.visitor_tab = tk.Frame(self.notebook, bg='#ffffff')
            self.notebook.add(self.visitor_tab, text="👤 Visitor Information")
            
            # Create visitor form content
            self.create_visitor_form(self.visitor_tab)
    
    def create_visitor_form(self, parent):
        """Create visitor information form"""
        # Main container
        main_frame = tk.Frame(parent, bg='#ffffff')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)
        
        # Header with back button
        header_frame = tk.Frame(main_frame, bg='#ffffff')
        header_frame.pack(fill=tk.X, pady=(0, 30))
        
        # Back button at top
        back_btn = tk.Button(
            header_frame,
            text="← Back to Dashboard",
            command=self.back_to_dashboard,
            font=('Arial', 12, 'bold'),
            bg='#6b7280',
            fg='white',
            relief='raised',
            bd=3,
            padx=20,
            pady=8,
            cursor='hand2',
            activebackground='#4b5563',
            activeforeground='white'
        )
        back_btn.pack(anchor=tk.W, pady=(0, 15))
        
        title_label = tk.Label(
            header_frame,
            text="👤 Visitor Registration Form",
            font=('Arial', 24, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            header_frame,
            text="Please fill in the visitor information and ID details",
            font=('Arial', 14),
            fg='#6b7280',
            bg='#ffffff'
        )
        subtitle_label.pack(pady=(5, 0))
        
        # Form container
        form_frame = tk.LabelFrame(
            main_frame,
            text="Visitor Details",
            font=('Arial', 16, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        form_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Form fields
        fields_frame = tk.Frame(form_frame, bg='#ffffff')
        fields_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Visitor Name
        name_frame = tk.Frame(fields_frame, bg='#ffffff')
        name_frame.pack(fill=tk.X, pady=(0, 15))
        
        name_label = tk.Label(
            name_frame,
            text="Full Name:",
            font=('Arial', 14, 'bold'),
            fg='#374151',
            bg='#ffffff'
        )
        name_label.pack(anchor=tk.W, pady=(0, 5))
        
        self.visitor_name_entry = tk.Entry(
            name_frame,
            font=('Arial', 14),
            width=40,
            relief='solid',
            bd=2,
            bg='#f9fafb',
            fg='#1f2937'
        )
        self.visitor_name_entry.pack(fill=tk.X)
        
        
        # Purpose of Visit
        purpose_frame = tk.Frame(fields_frame, bg='#ffffff')
        purpose_frame.pack(fill=tk.X, pady=(0, 15))
        
        purpose_label = tk.Label(
            purpose_frame,
            text="Purpose of Visit:",
            font=('Arial', 14, 'bold'),
            fg='#374151',
            bg='#ffffff'
        )
        purpose_label.pack(anchor=tk.W, pady=(0, 5))
        
        self.visitor_purpose_entry = tk.Entry(
            purpose_frame,
            font=('Arial', 14),
            width=40,
            relief='solid',
            bd=2,
            bg='#f9fafb',
            fg='#1f2937'
        )
        self.visitor_purpose_entry.pack(fill=tk.X)
        
        # ID Type Selection
        id_type_frame = tk.Frame(fields_frame, bg='#ffffff')
        id_type_frame.pack(fill=tk.X, pady=(0, 15))
        
        id_type_label = tk.Label(
            id_type_frame,
            text="ID Type Surrendered:",
            font=('Arial', 14, 'bold'),
            fg='#374151',
            bg='#ffffff'
        )
        id_type_label.pack(anchor=tk.W, pady=(0, 5))
        
        id_type_buttons_frame = tk.Frame(id_type_frame, bg='#ffffff')
        id_type_buttons_frame.pack(fill=tk.X)
        
        self.id_type_var = tk.StringVar(value="driver_license")
        
        # Driver's License
        self.driver_license_btn = tk.Radiobutton(
            id_type_buttons_frame,
            text="Driver's License",
            variable=self.id_type_var,
            value="driver_license",
            font=('Arial', 12),
            bg='#ffffff',
            fg='#374151',
            selectcolor='#3b82f6',
            command=self.on_id_type_change
        )
        self.driver_license_btn.pack(side=tk.LEFT, padx=(0, 20))
        
        # National ID
        self.national_id_btn = tk.Radiobutton(
            id_type_buttons_frame,
            text="National ID",
            variable=self.id_type_var,
            value="national_id",
            font=('Arial', 12),
            bg='#ffffff',
            fg='#374151',
            selectcolor='#3b82f6',
            command=self.on_id_type_change
        )
        self.national_id_btn.pack(side=tk.LEFT, padx=(0, 20))
        
        # Passport
        self.passport_btn = tk.Radiobutton(
            id_type_buttons_frame,
            text="Passport",
            variable=self.id_type_var,
            value="passport",
            font=('Arial', 12),
            bg='#ffffff',
            fg='#374151',
            selectcolor='#3b82f6',
            command=self.on_id_type_change
        )
        self.passport_btn.pack(side=tk.LEFT, padx=(0, 20))
        
        # Other
        self.other_id_btn = tk.Radiobutton(
            id_type_buttons_frame,
            text="Other",
            variable=self.id_type_var,
            value="other",
            font=('Arial', 12),
            bg='#ffffff',
            fg='#374151',
            selectcolor='#3b82f6',
            command=self.on_id_type_change
        )
        self.other_id_btn.pack(side=tk.LEFT)
        
        # Custom ID type input field (initially hidden)
        self.custom_id_frame = tk.Frame(id_type_frame, bg='#ffffff')
        self.custom_id_frame.pack(fill=tk.X, pady=(10, 0))
        
        custom_id_label = tk.Label(
            self.custom_id_frame,
            text="Specify ID Type:",
            font=('Arial', 12, 'bold'),
            fg='#374151',
            bg='#ffffff'
        )
        custom_id_label.pack(anchor=tk.W, pady=(0, 5))
        
        self.custom_id_entry = tk.Entry(
            self.custom_id_frame,
            font=('Arial', 12),
            width=30,
            relief='solid',
            bd=2,
            bg='#f9fafb',
            fg='#1f2937'
        )
        self.custom_id_entry.pack(fill=tk.X)
        
        # Initially hide the custom ID input
        self.custom_id_frame.pack_forget()
        
        # Available Empty RFID Section (from Firebase)
        rfid_section = tk.LabelFrame(
            main_frame,
            text="Available Empty RFID",
            font=('Arial', 16, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        rfid_section.pack(fill=tk.X, pady=(0, 20))
        
        rfid_content = tk.Frame(rfid_section, bg='#ffffff')
        rfid_content.pack(fill=tk.X, padx=20, pady=20)
        
        # RFID selection dropdown
        rfid_label = tk.Label(
            rfid_content,
            text="Select Available RFID Card:",
            font=('Arial', 14, 'bold'),
            fg='#374151',
            bg='#ffffff'
        )
        rfid_label.pack(anchor=tk.W, pady=(0, 10))
        
        self.available_rfid_var = tk.StringVar()
        self.rfid_dropdown = ttk.Combobox(
            rfid_content,
            textvariable=self.available_rfid_var,
            font=('Arial', 14),
            state='readonly',
            width=40
        )
        self.rfid_dropdown.pack(fill=tk.X, pady=(0, 10))
        
        # Load RFID list from Firebase
        self.load_rfid_from_firebase()
        
        # Action buttons
        buttons_frame = tk.Frame(main_frame, bg='#ffffff')
        buttons_frame.pack(fill=tk.X, pady=(20, 0))
        
        # Register Visitor button
        register_btn = tk.Button(
            buttons_frame,
            text="SUCCESS: Register Visitor & Assign RFID",
            command=self.register_visitor,
            font=('Arial', 14, 'bold'),
            bg='#10b981',
            fg='white',
            relief='raised',
            bd=3,
            padx=30,
            pady=12,
            cursor='hand2',
            activebackground='#059669',
            activeforeground='white'
        )
        register_btn.pack(side=tk.RIGHT)
    
    def back_to_dashboard(self):
        """Return to dashboard tab"""
        if self.dashboard_tab:
            self.notebook.select(self.dashboard_tab)
    
    def debug_firebase_rfid_collection(self):
        """Debug function to show all RFID data in Firebase"""
        try:
            if self.firebase_initialized and self.db:
                print("INFO: Debugging Firebase Empty RFID collection...")
                empty_rfid_ref = self.db.collection('Empty RFID')
                docs = empty_rfid_ref.get()
                
                print(f"INFO: Found {len(docs)} documents in Empty RFID collection:")
                
                for doc in docs:
                    rfid_data = doc.to_dict()
                    rfid_id = doc.id
                    print(f"  - Document ID: {rfid_id}")
                    print(f"    Data: {rfid_data}")
                    print()
                
                if len(docs) == 0:
                    print("WARNING: Empty RFID collection is empty!")
                    print("INFO: You need to add RFID documents to the Empty RFID collection")
                    print("INFO: Example document structure:")
                    print("  Document ID: RFID001")
                    print("  Data: { 'rfid_number': 'RFID001', 'status': 'available' }")
                
            else:
                print("ERROR: Firebase not initialized")
                
        except Exception as e:
            print(f"ERROR: Failed to debug Firebase collection: {e}")
            import traceback
            traceback.print_exc()
    
    def load_rfid_from_firebase(self):
        """Load all RFID cards from Firebase Empty RFID collection"""
        try:
            available_rfids = []
            
            if self.firebase_initialized and self.db:
                print("INFO: Loading RFID cards from Firebase Empty RFID collection...")
                # Debug the collection first
                self.debug_firebase_rfid_collection()
                
                empty_rfid_ref = self.db.collection('Empty RFID')
                docs = empty_rfid_ref.get()  # Get all documents
                
                for doc in docs:
                    rfid_data = doc.to_dict()
                    rfid_id = doc.id
                    
                    # Since you removed all fields, documents are now empty {}
                    # All RFID documents are available unless they have assignment fields
                    is_available = True
                    
                    # Check if document has any assignment data
                    if rfid_data:  # If document has any fields
                        if 'assigned_to' in rfid_data and rfid_data['assigned_to']:
                            is_available = False
                        elif 'available' in rfid_data and not rfid_data['available']:
                            is_available = False
                    
                    # Since documents are empty {}, they are all available
                    if is_available:
                        available_rfids.append(rfid_id)
                        print(f"INFO: Available RFID: {rfid_id} - Data: {rfid_data}")
                    else:
                        print(f"INFO: Unavailable RFID: {rfid_id} - Data: {rfid_data}")
                
                print(f"SUCCESS: Loaded {len(available_rfids)} RFID cards from Firebase")
            else:
                print("WARNING: Firebase not available - using empty list")
                available_rfids = []
            
            # Update the dropdown
            self.rfid_dropdown['values'] = available_rfids
            # Leave dropdown blank initially - no pre-selection
            self.available_rfid_var.set("")
            
        except Exception as e:
            print(f"ERROR: Failed to load RFID from Firebase: {e}")
            import traceback
            traceback.print_exc()
            self.rfid_dropdown['values'] = []
            self.available_rfid_var.set("")
    
    def update_available_rfid_list(self):
        """Update the list of available empty RFID cards from Firebase"""
        try:
            available_rfids = []
            
            # Try to get RFID list from Firebase first
            if self.firebase_initialized and self.db:
                try:
                    print("INFO: Fetching available RFID list from Firebase...")
                    empty_rfid_ref = self.db.collection('Empty RFID')
                    docs = empty_rfid_ref.where('available', '==', True).get()
                    
                    for doc in docs:
                        rfid_data = doc.to_dict()
                        rfid_id = doc.id
                        if rfid_data.get('available', True):
                            available_rfids.append(rfid_id)
                    
                    print(f"SUCCESS: Found {len(available_rfids)} available RFID cards in Firebase")
                    
                except Exception as e:
                    print(f"WARNING: Failed to fetch RFID from Firebase: {e}")
                    print("INFO: Using fallback RFID list")
            
            # Fallback: Use local available RFID list if Firebase fails
            if not available_rfids:
                available_rfids = self.available_rfids.copy()
            
            # Generate additional random available RFID numbers if needed
            import random
            while len(available_rfids) < 10:
                rfid_num = f"RF{random.randint(100000, 999999)}"
                if rfid_num not in available_rfids:
                    available_rfids.append(rfid_num)
            
            # Update the dropdown
            self.rfid_dropdown['values'] = available_rfids
            if available_rfids:
                self.available_rfid_var.set(available_rfids[0])  # Select first one by default
            
        except Exception as e:
            print(f"ERROR: Error updating RFID list: {e}")
            # Fallback to empty list
            self.rfid_dropdown['values'] = []
            self.available_rfid_var.set("")
    
    def update_rfid_availability_in_firebase(self, rfid_id, available=False):
        """Update RFID availability status in Firebase"""
        try:
            if self.firebase_initialized and self.db:
                # Update the RFID document in Firebase
                rfid_ref = self.db.collection('Empty RFID').document(rfid_id)
                rfid_ref.update({
                    'available': available,
                    'last_updated': firestore.SERVER_TIMESTAMP,
                    'assigned_to': None if available else 'visitor'
                })
                print(f"SUCCESS: RFID {rfid_id} availability updated in Firebase: {available}")
                return True
            else:
                print("WARNING: Firebase not available - RFID availability not updated")
                return False
        except Exception as e:
            print(f"ERROR: Failed to update RFID availability: {e}")
            return False
    
    def on_id_type_change(self):
        """Handle ID type selection change"""
        try:
            if self.id_type_var.get() == "other":
                # Show custom ID input field
                self.custom_id_frame.pack(fill=tk.X, pady=(10, 0))
            else:
                # Hide custom ID input field
                self.custom_id_frame.pack_forget()
        except Exception as e:
            print(f"Error handling ID type change: {e}")
    
    def register_visitor(self):
        """Register visitor and assign RFID"""
        try:
            # Get form data
            visitor_name = self.visitor_name_entry.get().strip()
            visitor_purpose = self.visitor_purpose_entry.get().strip()
            id_type = self.id_type_var.get()
            selected_rfid = self.available_rfid_var.get()
            
            # Handle custom ID type
            if id_type == "other":
                custom_id_type = self.custom_id_entry.get().strip()
                if not custom_id_type:
                    messagebox.showerror("Error", "Please specify the ID type.")
                    return
                id_type = custom_id_type.lower().replace(" ", "_")
            
            # Validate required fields
            if not visitor_name:
                messagebox.showerror("Error", "Please enter visitor's full name.")
                return
            
            if not visitor_purpose:
                visitor_purpose = "General Visit"
            
            if not selected_rfid:
                messagebox.showerror("Error", "Please select an available RFID card.")
                return
            
            # Check if RFID is already assigned
            if selected_rfid in self.visitor_rfid_registry:
                messagebox.showerror("Error", f"RFID {selected_rfid} is already assigned to another visitor.")
                return
            
            # Generate visitor ID
            import random
            visitor_id = f"VIS{random.randint(1000, 9999)}"
            
            # Create visitor info
            visitor_info = {
                'visitor_id': visitor_id,
                'name': visitor_name,
                'purpose': visitor_purpose,
                'id_type': id_type,
                'rfid': selected_rfid,
                'registration_time': self.get_current_timestamp(),
                'status': 'registered'  # registered, active, exited
            }
            
            # Link visitor to RFID
            self.visitor_rfid_registry[selected_rfid] = visitor_info
            
            # Remove from available RFID list
            if selected_rfid in self.available_rfids:
                self.available_rfids.remove(selected_rfid)
            
            # Add to activity log
            self.add_activity_log(f"Visitor registered: {visitor_name} - {visitor_purpose} (ID: {id_type}) - Assigned RFID: {selected_rfid}")
            
            # Save to Firebase
            self.save_visitor_to_firebase(visitor_info)
            
            # Update RFID availability in Firebase
            self.update_rfid_availability_in_firebase(selected_rfid, available=False)
            
            # Show confirmation
            messagebox.showinfo("Visitor Registered Successfully", 
                              f"Visitor Details:\n"
                              f"Name: {visitor_name}\n"
                              f"Purpose: {visitor_purpose}\n"
                              f"ID Type: {id_type.replace('_', ' ').title()}\n"
                              f"Visitor ID: {visitor_id}\n"
                              f"Assigned RFID: {selected_rfid}\n\n"
                              f"The visitor can now use the RFID card for entry and exit.")
            
            # Clear form
            self.visitor_name_entry.delete(0, tk.END)
            self.visitor_purpose_entry.delete(0, tk.END)
            self.id_type_var.set("driver_license")
            self.custom_id_entry.delete(0, tk.END)
            self.custom_id_frame.pack_forget()  # Hide custom ID field
            self.load_rfid_from_firebase()  # Refresh RFID list from Firebase
            
            # Return to dashboard
            self.back_to_dashboard()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to register visitor: {e}")
    
    def get_current_timestamp(self):
        """Get current timestamp in readable format"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def save_visitor_to_firebase(self, visitor_info):
        """Save visitor information to Firebase"""
        try:
            if self.firebase_initialized and self.db:
                # Save visitor registration
                visitor_ref = self.db.collection('visitors').document(visitor_info['visitor_id'])
                visitor_ref.set({
                    'visitor_id': visitor_info['visitor_id'],
                    'name': visitor_info['name'],
                    'purpose': visitor_info['purpose'],
                    'id_type': visitor_info['id_type'],
                    'rfid': visitor_info['rfid'],
                    'registration_time': visitor_info['registration_time'],
                    'status': visitor_info['status']
                })
                print(f"SUCCESS: Visitor {visitor_info['name']} saved to Firebase")
            else:
                print("WARNING: Firebase not available - visitor data not saved to cloud")
        except Exception as e:
            print(f"ERROR: Failed to save visitor to Firebase: {e}")
    
    def handle_visitor_rfid_tap(self, rfid):
        """Handle visitor RFID tap - Simple toggle: 1st tap=ENTRY, 2nd tap=EXIT"""
        try:
            if rfid not in self.visitor_rfid_registry:
                self.add_activity_log(f"Unknown RFID tapped: {rfid}")
                messagebox.showwarning("Unknown RFID", f"RFID {rfid} is not registered to any visitor.")
                return
            
            visitor_info = self.visitor_rfid_registry[rfid]
            
            # Simple toggle system - initialize if not exists
            if not hasattr(self, 'rfid_status_tracker'):
                self.rfid_status_tracker = {}
            
            # Get current status (default to 'EXIT' for first tap)
            current_status = self.rfid_status_tracker.get(rfid, 'EXIT')
            
            if current_status == 'EXIT':
                # This tap is ENTRY
                self.rfid_status_tracker[rfid] = 'ENTRY'
                self.handle_visitor_timein(rfid, visitor_info)
                print(f"SUCCESS: Visitor {visitor_info.get('name', 'Unknown')} - ENTRY")
            else:
                # This tap is EXIT
                self.rfid_status_tracker[rfid] = 'EXIT'
                self.handle_visitor_timeout(rfid, visitor_info)
                print(f"SUCCESS: Visitor {visitor_info.get('name', 'Unknown')} - EXIT")
                
        except Exception as e:
            print(f"ERROR: Error handling visitor RFID tap: {e}")
            self.add_activity_log(f"Error handling RFID {rfid}: {e}")
    
    def handle_visitor_timein(self, rfid, visitor_info):
        """Handle visitor time-in - NO DETECTION"""
        try:
            current_time = self.get_current_timestamp()
            
            # Add to active visitors
            self.active_visitors[rfid] = {
                **visitor_info,
                'time_in': current_time,
                'status': 'active'
            }
            
            # Update visitor registry
            self.visitor_rfid_registry[rfid]['status'] = 'active'
            
            # Log activity
            self.add_activity_log(f"Visitor Time-In: {visitor_info['name']} (RFID: {rfid}) - {current_time}")
            
            # Save to Firebase
            self.save_visitor_activity_to_firebase(rfid, 'time_in', current_time)
            
            # Update main screen
            if self.main_screen_window and self.main_screen_window.winfo_exists():
                self.update_main_screen_with_visitor(visitor_info, 'time_in', current_time)
            
            # Show success message - NO DETECTION for visitors
            self.show_green_success_message("Visitor Time-In", 
                              f"Visitor: {visitor_info['name']}\n"
                              f"Purpose: {visitor_info['purpose']}\n"
                              f"Time-In: {current_time}\n"
                              f"RFID: {rfid}\n\n"
                              f"Note: No uniform detection for visitors")
            
            # Ensure detection is NOT started for visitors
            if self.detection_active:
                self.stop_detection()
                self.add_activity_log("Detection stopped - Visitor entry (no uniform checking required)")
            
        except Exception as e:
            print(f"ERROR: Error handling visitor time-in: {e}")
            self.add_activity_log(f"Error processing time-in for RFID {rfid}: {e}")
    
    def handle_visitor_timeout(self, rfid, visitor_info):
        """Handle visitor time-out - NO DETECTION"""
        try:
            current_time = self.get_current_timestamp()
            time_in = self.active_visitors[rfid]['time_in']
            
            # Calculate duration
            from datetime import datetime
            time_in_dt = datetime.strptime(time_in, "%Y-%m-%d %H:%M:%S")
            time_out_dt = datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")
            duration = time_out_dt - time_in_dt
            
            # Ensure detection is NOT active for visitors
            if self.detection_active:
                self.stop_detection()
                self.add_activity_log("Detection stopped - Visitor exit (no uniform checking required)")
            
            # Log activity
            self.add_activity_log(f"Visitor Time-Out: {visitor_info['name']} (RFID: {rfid}) - {current_time} - Duration: {duration}")
            
            # Save to Firebase
            self.save_visitor_activity_to_firebase(rfid, 'time_out', current_time, duration=str(duration))
            
            # Update main screen
            if self.main_screen_window and self.main_screen_window.winfo_exists():
                self.update_main_screen_with_visitor(visitor_info, 'time_out', current_time, duration=str(duration))
            
            # Reset RFID for reuse
            self.reset_visitor_rfid(rfid)
            
            self.show_green_success_message("Visitor Time-Out", 
                              f"Visitor: {visitor_info['name']}\n"
                              f"Time-In: {time_in}\n"
                              f"Time-Out: {current_time}\n"
                              f"Duration: {duration}\n"
                              f"RFID: {rfid} - Now available for reuse\n\n"
                              f"Note: No uniform detection for visitors")
            
        except Exception as e:
            print(f"ERROR: Error handling visitor time-out: {e}")
            self.add_activity_log(f"Error processing time-out for RFID {rfid}: {e}")
    
    def reset_visitor_rfid(self, rfid):
        """Reset RFID card for reuse after visitor exit"""
        try:
            # Remove from active visitors
            if rfid in self.active_visitors:
                del self.active_visitors[rfid]
            
            # Update visitor registry status
            if rfid in self.visitor_rfid_registry:
                self.visitor_rfid_registry[rfid]['status'] = 'exited'
            
            # Add back to available RFID list
            if rfid not in self.available_rfids:
                self.available_rfids.append(rfid)
            
            # Update RFID availability in Firebase
            self.update_rfid_availability_in_firebase(rfid, available=True)
            
            # Update RFID dropdown
            self.load_rfid_from_firebase()
            
            print(f"SUCCESS: RFID {rfid} reset and available for reuse")
            
        except Exception as e:
            print(f"ERROR: Error resetting RFID {rfid}: {e}")
    
    def save_visitor_activity_to_firebase(self, rfid, activity_type, timestamp, duration=None):
        """Save visitor activity to Firebase"""
        try:
            if self.firebase_initialized and self.db:
                visitor_info = self.visitor_rfid_registry[rfid]
                activity_data = {
                    'visitor_id': visitor_info['visitor_id'],
                    'name': visitor_info['name'],
                    'rfid': rfid,
                    'activity_type': activity_type,  # 'time_in' or 'time_out'
                    'timestamp': timestamp,
                    'purpose': visitor_info['purpose']
                }
                
                if duration:
                    activity_data['duration'] = duration
                
                # Save to visitor_activities collection
                activity_ref = self.db.collection('visitor_activities').document()
                activity_ref.set(activity_data)
                
                print(f"SUCCESS: Visitor activity saved to Firebase: {activity_type} for {visitor_info['name']}")
            else:
                print("WARNING: Firebase not available - visitor activity not saved to cloud")
                
        except Exception as e:
            print(f"ERROR: Failed to save visitor activity to Firebase: {e}")
    
    def update_main_screen_with_visitor(self, visitor_info, activity_type, timestamp, duration=None):
        """Update main screen with visitor information"""
        try:
            if not self.main_screen_window or not self.main_screen_window.winfo_exists():
                return
            
            # This would update the main screen display
            # Implementation depends on your main screen structure
            print(f"📺 Main screen updated with visitor {activity_type}: {visitor_info['name']}")
            
        except Exception as e:
            print(f"ERROR: Error updating main screen with visitor: {e}")
    
    def handle_student_forgot_id_rfid_tap(self, rfid):
        """Handle student forgot ID RFID tap - Simple toggle: 1st tap=ENTRY, 2nd tap=EXIT"""
        try:
            if rfid not in self.student_rfid_assignments:
                self.add_activity_log(f"Unknown student RFID tapped: {rfid}")
                messagebox.showwarning("Unknown RFID", f"RFID {rfid} is not assigned to any student.")
                return
            
            assignment_info = self.student_rfid_assignments[rfid]
            
            # Simple toggle system - initialize if not exists
            if not hasattr(self, 'rfid_status_tracker'):
                self.rfid_status_tracker = {}
            
            # Get current status (default to 'EXIT' for first tap)
            current_status = self.rfid_status_tracker.get(rfid, 'EXIT')
            
            if current_status == 'EXIT':
                # This tap is ENTRY
                self.rfid_status_tracker[rfid] = 'ENTRY'
                self.handle_student_forgot_id_timein(rfid, assignment_info)
                print(f"SUCCESS: Student {assignment_info.get('name', 'Unknown')} - ENTRY")
            else:
                # This tap is EXIT
                self.rfid_status_tracker[rfid] = 'EXIT'
                self.handle_student_forgot_id_timeout(rfid, assignment_info)
                print(f"SUCCESS: Student {assignment_info.get('name', 'Unknown')} - EXIT")
                
        except Exception as e:
            print(f"ERROR: Error handling student forgot ID RFID tap: {e}")
            self.add_activity_log(f"Error handling student RFID {rfid}: {e}")
    
    def handle_student_forgot_id_timein(self, rfid, assignment_info):
        """Handle student forgot ID time-in - WITH DETECTION"""
        try:
            current_time = self.get_current_timestamp()
            
            # Log activity
            self.add_activity_log(f"Student Time-In (Forgot ID): {assignment_info['name']} (RFID: {rfid}) - {current_time}")
            
            # Add automatic violation for forgot ID (using empty RFID)
            self.add_activity_log(f"VIOLATION: Student {assignment_info['name']} forgot school ID - using temporary RFID")
            
            # Save to Firebase
            self.save_student_activity_to_firebase(rfid, 'time_in', current_time, assignment_info)
            
            # Update main screen
            if self.main_screen_window and self.main_screen_window.winfo_exists():
                self.update_main_screen_with_student_forgot_id(assignment_info, 'time_in', current_time)
            
            # Show success message
            self.show_green_success_message("Student Time-In (Forgot ID)", 
                              f"Student: {assignment_info['name']}\n"
                              f"Course: {assignment_info['course']}\n"
                              f"Student ID: {assignment_info['student_id']}\n"
                              f"Temporary RFID: {rfid}\n"
                              f"Time-In: {current_time}\n\n"
                              f"⚠️ VIOLATION: Forgot school ID\n"
                              f"Note: Uniform detection will start")
            
            # Start detection for students (including forgot ID)
            try:
                person_name = assignment_info['name']
                self.start_person_detection(rfid, person_name, "student")
                self.add_activity_log(f"Detection started for student (forgot ID): {person_name}")
            except Exception as e:
                self.add_activity_log(f"Failed to start detection for student (forgot ID): {str(e)}")
                print(f"ERROR: Error starting detection for student forgot ID: {e}")
            
        except Exception as e:
            print(f"ERROR: Error handling student forgot ID time-in: {e}")
            self.add_activity_log(f"Error processing time-in for student RFID {rfid}: {e}")
    
    def handle_student_forgot_id_timeout(self, rfid, assignment_info):
        """Handle student forgot ID time-out - STOP DETECTION"""
        try:
            current_time = self.get_current_timestamp()
            
            # Stop detection for student exit
            if self.detection_active:
                self.stop_detection()
                self.add_activity_log("Detection stopped - Student exit (forgot ID)")
            
            # Log activity
            self.add_activity_log(f"Student Time-Out (Forgot ID): {assignment_info['name']} (RFID: {rfid}) - {current_time}")
            
            # Save to Firebase
            self.save_student_activity_to_firebase(rfid, 'time_out', current_time, assignment_info)
            
            # Update main screen
            if self.main_screen_window and self.main_screen_window.winfo_exists():
                self.update_main_screen_with_student_forgot_id(assignment_info, 'time_out', current_time)
            
            # Reset RFID for reuse (like visitors)
            self.reset_student_forgot_id_rfid(rfid)
            
            # Show success message
            self.show_green_success_message("Student Time-Out (Forgot ID)", 
                              f"Student: {assignment_info['name']}\n"
                              f"Course: {assignment_info['course']}\n"
                              f"Student ID: {assignment_info['student_id']}\n"
                              f"Temporary RFID: {rfid}\n"
                              f"Time-Out: {current_time}\n\n"
                              f"RFID: {rfid} - Now available for reuse\n"
                              f"Note: Detection stopped")
            
        except Exception as e:
            print(f"ERROR: Error handling student forgot ID time-out: {e}")
            self.add_activity_log(f"Error processing time-out for student RFID {rfid}: {e}")
    
    def reset_student_forgot_id_rfid(self, rfid):
        """Reset RFID card for reuse after student forgot ID exit"""
        try:
            # Remove from student RFID assignments
            if rfid in self.student_rfid_assignments:
                del self.student_rfid_assignments[rfid]
            
            # Add back to available RFID list
            if rfid not in self.student_forgot_rfids:
                self.student_forgot_rfids.append(rfid)
            
            # Update RFID availability in Firebase
            self.update_rfid_availability_in_firebase(rfid, available=True)
            
            # Update RFID dropdown
            self.update_student_rfid_list()
            
            print(f"SUCCESS: Student forgot ID RFID {rfid} reset and available for reuse")
            
        except Exception as e:
            print(f"ERROR: Error resetting student forgot ID RFID {rfid}: {e}")
    
    def save_student_activity_to_firebase(self, rfid, activity_type, timestamp, assignment_info):
        """Save student forgot ID activity to Firebase"""
        try:
            if self.firebase_initialized and self.db:
                activity_data = {
                    'student_id': assignment_info['student_id'],
                    'name': assignment_info['name'],
                    'rfid': rfid,
                    'activity_type': activity_type,  # 'time_in' or 'time_out'
                    'timestamp': timestamp,
                    'course': assignment_info['course'],
                    'assignment_type': 'forgot_id'
                }
                
                # Save to student_activities collection
                activity_ref = self.db.collection('student_activities').document()
                activity_ref.set(activity_data)
                
                print(f"SUCCESS: Student activity saved to Firebase: {activity_type} for {assignment_info['name']}")
            else:
                print("WARNING: Firebase not available - student activity not saved to cloud")
                
        except Exception as e:
            print(f"ERROR: Failed to save student activity to Firebase: {e}")
    
    def update_main_screen_with_student_forgot_id(self, assignment_info, activity_type, timestamp):
        """Update main screen with student forgot ID information"""
        try:
            if not self.main_screen_window or not self.main_screen_window.winfo_exists():
                return
            
            # This would update the main screen display
            # Implementation depends on your main screen structure
            print(f"📺 Main screen updated with student {activity_type}: {assignment_info['name']} (Forgot ID)")
            
        except Exception as e:
            print(f"ERROR: Error updating main screen with student forgot ID: {e}")
    
    def is_permanent_student_rfid(self, rfid):
        """Check if RFID belongs to a permanent student"""
        try:
            if self.firebase_initialized and self.db:
                # Query Firebase for student with this RFID
                students_ref = self.db.collection('students')
                query = students_ref.where('rfid', '==', rfid).where('student_type', '==', 'permanent')
                docs = query.get()
                
                return len(docs) > 0
            else:
                # Fallback: check known permanent student RFID
                return rfid == '0095365253'
        except Exception as e:
            print(f"ERROR: Error checking permanent student RFID: {e}")
            return False
    
    def handle_permanent_student_rfid_tap(self, rfid):
        """Handle permanent student RFID tap - Simple toggle: 1st tap=ENTRY, 2nd tap=EXIT"""
        try:
            # Ensure Firebase is ready
            if not self.firebase_initialized:
                print("INFO: Firebase not ready for permanent student RFID tap, initializing...")
                self.init_firebase()
                import time
                time.sleep(1)
                
                if not self.firebase_initialized:
                    print("WARNING: Firebase still not ready, retrying in 2 seconds...")
                    self.root.after(2000, lambda: self.handle_permanent_student_rfid_tap(rfid))
                    return
            
            # Get student info from Firebase
            student_info = self.get_student_info_by_rfid(rfid)
            
            if not student_info:
                self.add_activity_log(f"Unknown permanent student RFID tapped: {rfid}")
                messagebox.showwarning("Unknown RFID", f"RFID {rfid} is not assigned to any permanent student.")
                return
            
            # Simple toggle system - initialize if not exists
            if not hasattr(self, 'rfid_status_tracker'):
                self.rfid_status_tracker = {}
            
            # Get current status (default to 'EXIT' for first tap)
            current_status = self.rfid_status_tracker.get(rfid, 'EXIT')
            
            if current_status == 'EXIT':
                # This tap is ENTRY
                self.rfid_status_tracker[rfid] = 'ENTRY'
                self.handle_permanent_student_timein(rfid, student_info)
                print(f"SUCCESS: Student {student_info.get('name', 'Unknown')} - ENTRY")
            else:
                # This tap is EXIT
                self.rfid_status_tracker[rfid] = 'EXIT'
                self.handle_permanent_student_timeout(rfid, student_info)
                print(f"SUCCESS: Student {student_info.get('name', 'Unknown')} - EXIT")
                
        except Exception as e:
            print(f"ERROR: Error handling permanent student RFID tap: {e}")
            self.add_activity_log(f"Error handling permanent student RFID {rfid}: {e}")
    
    def get_student_info_by_rfid(self, rfid):
        """Get student information by RFID (using document ID) - Enhanced with better error handling"""
        try:
            print(f"DEBUG: Looking up student with RFID: {rfid}")
            
            # Try Firebase first
            if self.firebase_initialized and self.db:
                try:
                    # In your Firebase, RFID is stored as document ID, not as a field
                    students_ref = self.db.collection('students')
                    doc_ref = students_ref.document(rfid)  # Use RFID as document ID
                    doc = doc_ref.get()
                
                    if doc.exists:
                        student_data = doc.to_dict()
                        print(f"SUCCESS: Found student by RFID {rfid}: {student_data.get('Name', 'Unknown')} ({student_data.get('Course', student_data.get('Department', 'Unknown'))})")
                        print(f"DEBUG: Student data fields: {list(student_data.keys())}")
                        
                        # Return properly formatted student info
                        return {
                            'student_id': student_data.get('Student Number', rfid),
                            'name': student_data.get('Name', f'Student {rfid}'),
                            'course': student_data.get('Course', student_data.get('Department', 'Unknown Course')),
                            'gender': student_data.get('Gender', 'Unknown Gender'),
                            'rfid': rfid,
                        }
                    else:
                        print(f"WARNING: No student found with RFID: {rfid}")
                        return None
                except Exception as e:
                    print(f"ERROR: Firebase query failed for RFID {rfid}: {e}")
                    return None
            else:
                print("WARNING: Firebase not available - cannot query student by RFID")
                return None
        except Exception as e:
            print(f"ERROR: Error getting student info by RFID: {e}")
            return None

    def get_guard_info_by_rfid(self, rfid):
        """Get guard information by RFID"""
        try:
            if self.firebase_initialized and self.db:
                guards_ref = self.db.collection('guards')
                query = guards_ref.where('rfid', '==', rfid)
                docs = query.get()
                
                if docs:
                    doc = docs[0]
                    guard_data = doc.to_dict()
                    return {
                        'rfid': guard_data.get('rfid'),
                        'name': guard_data.get('name'),
                        'role': guard_data.get('role'),
                        'department': guard_data.get('department'),
                        'status': guard_data.get('status')
                    }
            else:
                print("WARNING: Firebase not available - cannot query guard by RFID")
            return None
        except Exception as e:
            print(f"ERROR: Error getting guard info by RFID: {e}")
            return None
    
    def handle_permanent_student_timein(self, rfid, student_info):
        """Handle permanent student time-in - WITH DETECTION"""
        try:
            current_time = self.get_current_timestamp()
            
            # Log activity
            self.add_activity_log(f"Student Time-In (Permanent): {student_info['name']} (RFID: {rfid}) - {current_time}")
            
            # Save to Firebase
            self.save_permanent_student_activity_to_firebase(rfid, 'time_in', current_time, student_info)
            
            # Update main screen
            if self.main_screen_window and self.main_screen_window.winfo_exists():
                self.update_main_screen_with_permanent_student(student_info, 'time_in', current_time)
            
            # Show success message
            self.show_green_success_message("Student Time-In", 
                              f"Student: {student_info['name']}\n"
                              f"Course: {student_info['course']}\n"
                              f"Student ID: {student_info['student_id']}\n"
                              f"Permanent RFID: {rfid}\n"
                              f"Time-In: {current_time}\n\n"
                              f"Note: Uniform detection will start")
            
            # Start detection for permanent students with appropriate model
            try:
                person_name = student_info['name']
                course = student_info.get('course', 'Unknown')
                gender = student_info.get('gender', 'Unknown')
                
                # Stop guard camera feed first
                self.stop_guard_camera_feed()
                
                # Switch to appropriate model based on course and gender
                if course.upper() in ["BSBA", "BUSINESS", "BUSINESS AND MANAGEMENT", "BUSINESS MANAGEMENT"]:
                    self.switch_to_bsba_student_detection(rfid, person_name, course, gender)
                else:
                    self.start_person_detection(rfid, person_name, "student")
                
                self.add_activity_log(f"Detection started for permanent student: {person_name} ({course})")
            except Exception as e:
                self.add_activity_log(f"Failed to start detection for permanent student: {str(e)}")
                print(f"ERROR: Error starting detection for permanent student: {e}")
            
        except Exception as e:
            print(f"ERROR: Error handling permanent student time-in: {e}")
            self.add_activity_log(f"Error processing time-in for permanent student RFID {rfid}: {e}")
    
    def handle_permanent_student_timeout(self, rfid, student_info):
        """Handle permanent student time-out - STOP DETECTION"""
        try:
            current_time = self.get_current_timestamp()
            
            # Stop detection for student exit
            if self.detection_active:
                self.stop_detection()
                self.add_activity_log("Detection stopped - Permanent student exit")
            
            # Log activity
            self.add_activity_log(f"Student Time-Out (Permanent): {student_info['name']} (RFID: {rfid}) - {current_time}")
            
            # Save to Firebase
            self.save_permanent_student_activity_to_firebase(rfid, 'time_out', current_time, student_info)
            
            # Update main screen
            if self.main_screen_window and self.main_screen_window.winfo_exists():
                self.update_main_screen_with_permanent_student(student_info, 'time_out', current_time)
            
            # Show success message
            self.show_green_success_message("Student Time-Out", 
                              f"Student: {student_info['name']}\n"
                              f"Course: {student_info['course']}\n"
                              f"Student ID: {student_info['student_id']}\n"
                              f"Permanent RFID: {rfid}\n"
                              f"Time-Out: {current_time}\n\n"
                              f"Note: Detection stopped")
            
        except Exception as e:
            print(f"ERROR: Error handling permanent student time-out: {e}")
            self.add_activity_log(f"Error processing time-out for permanent student RFID {rfid}: {e}")
    
    def save_permanent_student_activity_to_firebase(self, rfid, activity_type, timestamp, student_info):
        """Save permanent student activity to Firebase"""
        try:
            if self.firebase_initialized and self.db:
                activity_data = {
                    'student_id': student_info['student_id'],
                    'name': student_info['name'],
                    'rfid': rfid,
                    'activity_type': activity_type,  # 'time_in' or 'time_out'
                    'timestamp': timestamp,
                    'course': student_info['course'],
                    'student_type': 'permanent'
                }
                
                # Save to student_activities collection
                activity_ref = self.db.collection('student_activities').document()
                activity_ref.set(activity_data)
                
                print(f"SUCCESS: Permanent student activity saved to Firebase: {activity_type} for {student_info['name']}")
            else:
                print("WARNING: Firebase not available - permanent student activity not saved to cloud")
                
        except Exception as e:
            print(f"ERROR: Failed to save permanent student activity to Firebase: {e}")
    
    def update_main_screen_with_permanent_student(self, student_info, activity_type, timestamp):
        """Update main screen with permanent student information - Enhanced to prevent Unknown status"""
        try:
            if not self.main_screen_window or not self.main_screen_window.winfo_exists():
                return
            
            # Ensure we have valid student info
            if not student_info:
                print("ERROR: No student info provided to update_main_screen_with_permanent_student")
                return
            
            # Create person info for main screen with proper fallbacks
            person_info = {
                'id': student_info.get('rfid', 'Unknown RFID'),
                'name': student_info.get('name', 'Unknown Student'),
                'type': 'student',
                'course': student_info.get('course', 'Unknown Course'),
                'gender': student_info.get('gender', 'Unknown Gender'),
                'timestamp': timestamp,
                'status': 'TIME-IN' if activity_type == 'time_in' else 'TIME-OUT',  # This should NEVER be Unknown
                'guard_id': self.current_guard_id or 'Unknown Guard'
            }
            
            # Update main screen
            self.update_main_screen_with_person(person_info)
            print(f"SUCCESS: Main screen updated with permanent student {activity_type}: {student_info['name']} - Status: {person_info['status']}")
            
        except Exception as e:
            print(f"ERROR: Error updating main screen with permanent student: {e}")
    
    def init_arduino_connection(self):
        """Initialize Arduino serial connection for gate control"""
        try:
            import serial
            import serial.tools.list_ports
            
            # Find Arduino port
            arduino_port = None
            ports = serial.tools.list_ports.comports()
            
            for port in ports:
                if 'Arduino' in port.description or 'USB' in port.description:
                    arduino_port = port.device
                    break
            
            if not arduino_port:
                # Try common Arduino ports
                common_ports = ['/dev/ttyUSB0', '/dev/ttyACM0', '/dev/ttyACM1', 'COM3', 'COM4']
                for port in common_ports:
                    try:
                        test_serial = serial.Serial(port, 9600, timeout=1)
                        test_serial.close()
                        arduino_port = port
                        break
                    except:
                        continue
            
            if arduino_port:
                self.arduino_serial = serial.Serial(arduino_port, 9600, timeout=1)
                self.arduino_connected = True
                print(f"SUCCESS: Arduino connected on port: {arduino_port}")
                self.add_activity_log(f"Arduino connected on port: {arduino_port}")
                
                # Update Arduino connection status in UI (only if dashboard exists)
                if hasattr(self, 'arduino_status_label'):
                    self.root.after(0, self.update_arduino_connection_status, True)
                
                return True
            else:
                print("WARNING: Arduino not found - gate control disabled")
                self.arduino_connected = False
                self.add_activity_log("Arduino not found - gate control disabled")
                
                # Update Arduino connection status in UI (only if dashboard exists)
                if hasattr(self, 'arduino_status_label'):
                    self.root.after(0, self.update_arduino_connection_status, False)
                
                return False
                
        except ImportError:
            print("WARNING: PySerial not installed - Arduino communication disabled")
            print("💡 Install with: pip install pyserial")
            self.arduino_connected = False
            return False
        except Exception as e:
            print(f"ERROR: Error initializing Arduino: {e}")
            self.arduino_connected = False
            return False
    
    def send_arduino_command(self, command):
        """Send command to Arduino for gate control"""
        try:
            if self.arduino_connected and hasattr(self, 'arduino_serial'):
                self.arduino_serial.write(command.encode())
                print(f"📤 Sent to Arduino: {command}")
                self.add_activity_log(f"Arduino command sent: {command}")
                return True
            else:
                print("WARNING: Arduino not connected - command not sent")
                return False
        except Exception as e:
            print(f"ERROR: Error sending Arduino command: {e}")
            self.add_activity_log(f"Arduino command failed: {e}")
            return False
    
    def open_gate(self):
        """Open the gate via Arduino"""
        try:
            success = self.send_arduino_command("OPEN")
            if success:
                self.add_activity_log("Gate opened via Arduino")
                print("🚪 Gate opened")
            return success
        except Exception as e:
            print(f"ERROR: Error opening gate: {e}")
            return False
    
    def close_gate(self):
        """Close the gate via Arduino"""
        try:
            success = self.send_arduino_command("CLOSE")
            if success:
                self.add_activity_log("Gate closed via Arduino")
                print("🚪 Gate closed")
            return success
        except Exception as e:
            print(f"ERROR: Error closing gate: {e}")
            return False
    
    def handle_approve_button(self):
        """Handle approve button press from Arduino"""
        try:
            print("SUCCESS: Approve button pressed - Opening gate")
            self.add_activity_log("Approve button pressed - Opening gate")
            
            # Open gate
            self.open_gate()
            
            # Update main screen
            if self.main_screen_window and self.main_screen_window.winfo_exists():
                self.update_main_screen_with_gate_status("OPEN", "APPROVED")
            
            # Show success message
            self.show_green_success_message("Gate Approved", 
                              "SUCCESS: Uniform compliance verified\n"
                              "🚪 Gate is opening\n"
                              "👤 Person may proceed")
            
            return True
            
        except Exception as e:
            print(f"ERROR: Error handling approve button: {e}")
            return False
    
    def handle_deny_button(self):
        """Handle deny button press from Arduino"""
        try:
            print("ERROR: Deny button pressed - Keeping gate closed")
            self.add_activity_log("Deny button pressed - Gate remains closed")
            
            # Keep gate closed
            self.close_gate()
            
            # Update main screen
            if self.main_screen_window and self.main_screen_window.winfo_exists():
                self.update_main_screen_with_gate_status("CLOSED", "DENIED")
            
            # Show warning message
            self.show_red_warning_message("Gate Denied", 
                              "ERROR: Uniform violation detected\n"
                              "🚪 Gate remains closed\n"
                              "👤 Person must correct uniform")
            
            return True
            
        except Exception as e:
            print(f"ERROR: Error handling deny button: {e}")
            return False
    
    def update_main_screen_with_gate_status(self, gate_status, decision):
        """Update main screen with gate status"""
        try:
            if not self.main_screen_window or not self.main_screen_window.winfo_exists():
                return
            
            print(f"📺 Main screen updated - Gate: {gate_status}, Decision: {decision}")
            
        except Exception as e:
            print(f"ERROR: Error updating main screen with gate status: {e}")
    
    def show_red_warning_message(self, title, message):
        """Show a warning message with red color"""
        try:
            # Create a custom messagebox window
            warning_window = tk.Toplevel(self.root)
            warning_window.title(title)
            warning_window.geometry("400x150")
            warning_window.configure(bg='#fef2f2')
            warning_window.resizable(False, False)
            
            # Ensure it's a child of the Guard UI window only
            warning_window.transient(self.root)
            warning_window.grab_set()
            
            # Center on the Guard UI window
            self.root.update_idletasks()
            guard_x = self.root.winfo_x()
            guard_y = self.root.winfo_y()
            guard_width = self.root.winfo_width()
            guard_height = self.root.winfo_height()
            
            x = guard_x + (guard_width // 2) - (400 // 2)
            y = guard_y + (guard_height // 2) - (150 // 2)
            warning_window.geometry(f"400x150+{x}+{y}")
            
            warning_window.lift(self.root)
            warning_window.attributes('-topmost', True)
            
            # Main frame
            main_frame = tk.Frame(warning_window, bg='#fef2f2')
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            # Warning icon (red X)
            icon_label = tk.Label(
                main_frame,
                text="ERROR:",
                font=('Arial', 24),
                bg='#fef2f2',
                fg='#dc2626'
            )
            icon_label.pack(pady=(0, 10))
            
            # Title
            title_label = tk.Label(
                main_frame,
                text=title,
                font=('Arial', 16, 'bold'),
                bg='#fef2f2',
                fg='#dc2626'
            )
            title_label.pack(pady=(0, 5))
            
            # Message
            message_label = tk.Label(
                main_frame,
                text=message,
                font=('Arial', 12),
                bg='#fef2f2',
                fg='#1f2937',
                wraplength=350,
                justify=tk.CENTER
            )
            message_label.pack(pady=(0, 15))
            
            # OK button
            ok_button = tk.Button(
                main_frame,
                text="OK",
                font=('Arial', 12, 'bold'),
                bg='#dc2626',
                fg='white',
                relief='raised',
                bd=2,
                padx=20,
                pady=5,
                cursor='hand2',
                activebackground='#b91c1c',
                activeforeground='white',
                command=warning_window.destroy
            )
            ok_button.pack()
            
            # Auto-close after 5 seconds
            warning_window.after(5000, warning_window.destroy)
            
            # Focus on the window
            warning_window.focus_set()
            
        except Exception as e:
            print(f"ERROR: Error showing red warning message: {e}")
            # Fallback to regular messagebox
            messagebox.showwarning(title, message)
    
    def listen_for_arduino_buttons(self):
        """Listen for button presses from Arduino"""
        try:
            if self.arduino_connected and hasattr(self, 'arduino_serial'):
                # Check for incoming data
                if self.arduino_serial.in_waiting > 0:
                    data = self.arduino_serial.readline().decode().strip()
                    
                    if data == "APPROVE":
                        self.handle_approve_button()
                    elif data == "DENY":
                        self.handle_deny_button()
                    elif data:
                        print(f"📥 Arduino data: {data}")
                        self.add_activity_log(f"Arduino data received: {data}")
                
                # Schedule next check
                self.root.after(100, self.listen_for_arduino_buttons)
                
        except Exception as e:
            print(f"ERROR: Error listening for Arduino buttons: {e}")
            # Retry after delay
            self.root.after(1000, self.listen_for_arduino_buttons)
    
    def process_detection_result_for_gate(self, detection_result):
        """Process detection result and prepare for gate control"""
        try:
            if not detection_result:
                return
            
            # Extract detection information
            compliant = detection_result.get('compliant', False)
            violations = detection_result.get('violations', [])
            confidence = detection_result.get('confidence', 0)
            
            # Log detection result
            if compliant:
                self.add_activity_log(f"SUCCESS: Uniform compliant - Ready for approval (Confidence: {confidence:.2f})")
                print("SUCCESS: Uniform compliant - Waiting for guard approval")
            else:
                violation_text = ", ".join(violations) if violations else "Unknown violation"
                self.add_activity_log(f"ERROR: Uniform violation detected: {violation_text} (Confidence: {confidence:.2f})")
                print(f"ERROR: Uniform violation: {violation_text}")
            
            # Update main screen with detection result
            if self.main_screen_window and self.main_screen_window.winfo_exists():
                self.update_main_screen_with_detection_result(detection_result)
            
            # Show detection result to guard
            if compliant:
                self.show_detection_result_message("Uniform Compliant", 
                                    f"SUCCESS: Uniform compliance verified\n"
                                    f"Confidence: {confidence:.2f}\n\n"
                                    f"Press APPROVE button to open gate\n"
                                    f"Press DENY button to keep gate closed")
            else:
                violation_text = ", ".join(violations) if violations else "Unknown violation"
                self.show_detection_result_message("Uniform Violation", 
                                    f"ERROR: Uniform violation detected\n"
                                    f"Violations: {violation_text}\n"
                                    f"Confidence: {confidence:.2f}\n\n"
                                    f"Press APPROVE button to open gate anyway\n"
                                    f"Press DENY button to keep gate closed")
            
        except Exception as e:
            print(f"ERROR: Error processing detection result for gate: {e}")
    
    def show_detection_result_message(self, title, message):
        """Show detection result message"""
        try:
            # Create a custom messagebox window
            result_window = tk.Toplevel(self.root)
            result_window.title(title)
            result_window.geometry("450x200")
            result_window.configure(bg='#f8fafc')
            result_window.resizable(False, False)
            
            # Ensure it's a child of the Guard UI window only
            result_window.transient(self.root)
            result_window.grab_set()
            
            # Center on the Guard UI window
            self.root.update_idletasks()
            guard_x = self.root.winfo_x()
            guard_y = self.root.winfo_y()
            guard_width = self.root.winfo_width()
            guard_height = self.root.winfo_height()
            
            x = guard_x + (guard_width // 2) - (450 // 2)
            y = guard_y + (guard_height // 2) - (200 // 2)
            result_window.geometry(f"450x200+{x}+{y}")
            
            result_window.lift(self.root)
            result_window.attributes('-topmost', True)
            
            # Main frame
            main_frame = tk.Frame(result_window, bg='#f8fafc')
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            # Title
            title_label = tk.Label(
                main_frame,
                text=title,
                font=('Arial', 16, 'bold'),
                bg='#f8fafc',
                fg='#1f2937'
            )
            title_label.pack(pady=(0, 10))
            
            # Message
            message_label = tk.Label(
                main_frame,
                text=message,
                font=('Arial', 12),
                bg='#f8fafc',
                fg='#374151',
                wraplength=400,
                justify=tk.CENTER
            )
            message_label.pack(pady=(0, 15))
            
            # Instructions
            instruction_label = tk.Label(
                main_frame,
                text="Use Arduino APPROVE/DENY buttons to control gate",
                font=('Arial', 10, 'italic'),
                bg='#f8fafc',
                fg='#6b7280'
            )
            instruction_label.pack(pady=(0, 15))
            
            # OK button
            ok_button = tk.Button(
                main_frame,
                text="OK",
                font=('Arial', 12, 'bold'),
                bg='#3b82f6',
                fg='white',
                relief='raised',
                bd=2,
                padx=20,
                pady=5,
                cursor='hand2',
                activebackground='#2563eb',
                activeforeground='white',
                command=result_window.destroy
            )
            ok_button.pack()
            
            # Auto-close after 10 seconds
            result_window.after(10000, result_window.destroy)
            
            # Focus on the window
            result_window.focus_set()
            
        except Exception as e:
            print(f"ERROR: Error showing detection result message: {e}")
            # Fallback to regular messagebox
            messagebox.showinfo(title, message)
    
    def save_guard_login_to_firebase(self, guard_id):
        """Save guard login activity to Firebase"""
        try:
            if self.firebase_initialized and self.db:
                login_data = {
                    'guard_id': guard_id,
                    'session_id': self.session_id,
                    'login_time': self.get_current_timestamp(),
                    'login_type': 'manual_login',
                    'status': 'active'
                }
                
                # Save to guard_logins collection
                login_ref = self.db.collection('guard_logins').document(self.session_id)
                login_ref.set(login_data)
                
                print(f"SUCCESS: Guard login saved to Firebase: {guard_id}")
                
                # Add to activity log
                self.add_activity_log(f"Guard Login: {guard_id} - {login_data['login_time']}")
                
            else:
                print("WARNING: Firebase not available - guard login not saved to cloud")
                # Still add to activity log for local tracking
                self.add_activity_log(f"Guard Login: {guard_id} - {self.get_current_timestamp()}")
                
        except Exception as e:
            print(f"ERROR: Failed to save guard login to Firebase: {e}")
            # Still add to activity log for local tracking
            self.add_activity_log(f"Guard Login: {guard_id} - {self.get_current_timestamp()}")
    
    def save_guard_logout_to_firebase(self, guard_id):
        """Save guard logout activity to Firebase"""
        try:
            if self.firebase_initialized and self.db and hasattr(self, 'session_id'):
                logout_data = {
                    'guard_id': guard_id,
                    'session_id': self.session_id,
                    'logout_time': self.get_current_timestamp(),
                    'logout_type': 'manual_logout',
                    'status': 'logged_out'
                }
                
                # Update the existing login record with logout info
                login_ref = self.db.collection('guard_logins').document(self.session_id)
                login_ref.update(logout_data)
                
                print(f"SUCCESS: Guard logout saved to Firebase: {guard_id}")
                
                # Add to activity log
                self.add_activity_log(f"Guard Logout: {guard_id} - {logout_data['logout_time']}")
                
            else:
                print("WARNING: Firebase not available - guard logout not saved to cloud")
                # Still add to activity log for local tracking
                self.add_activity_log(f"Guard Logout: {guard_id} - {self.get_current_timestamp()}")
                
        except Exception as e:
            print(f"ERROR: Failed to save guard logout to Firebase: {e}")
            # Still add to activity log for local tracking
            self.add_activity_log(f"Guard Logout: {guard_id} - {self.get_current_timestamp()}")
    
    def save_student_rfid_assignment_to_firebase(self, assignment_info):
        """Save student RFID assignment to Firebase"""
        try:
            if self.firebase_initialized and self.db:
                # Save to student_rfid_assignments collection
                assignment_ref = self.db.collection('student_rfid_assignments').document()
                assignment_ref.set({
                    'student_id': assignment_info['student_id'],
                    'name': assignment_info['name'],
                    'course': assignment_info['course'],
                    'gender': assignment_info['gender'],
                    'rfid': assignment_info['rfid'],
                    'assignment_time': assignment_info['assignment_time'],
                    'status': assignment_info['status'],
                    'assignment_type': 'forgot_id'
                })
                
                print(f"SUCCESS: Student RFID assignment saved to Firebase: {assignment_info['name']} - {assignment_info['rfid']}")
            else:
                print("WARNING: Firebase not available - student RFID assignment not saved to cloud")
                
        except Exception as e:
            print(f"ERROR: Failed to save student RFID assignment to Firebase: {e}")
    
    def save_permanent_students_to_firebase(self):
        """Save permanent student records to Firebase students collection"""
        try:
            if self.firebase_initialized and self.db:
                # Permanent student data
                students_data = [
                    {
                        'student_id': '02000289900',
                        'rfid': '0095365253',
                        'name': 'John Jason Domingo',
                        'course': 'ICT',
                        'gender': 'Male',
                        'status': 'active',
                        'student_type': 'permanent',
                        'created_at': self.get_current_timestamp(),
                        'last_login': None,
                        'total_logins': 0
                    }
                ]
                
                # Save each student to Firebase
                for student_data in students_data:
                    student_ref = self.db.collection('students').document(student_data['student_id'])
                    student_ref.set(student_data)
                    print(f"SUCCESS: Student {student_data['name']} saved to Firebase students collection")
                
                print("SUCCESS: All permanent students saved to Firebase students collection")
                
            else:
                print("WARNING: Firebase not available - permanent students not saved to cloud")
                
        except Exception as e:
            print(f"ERROR: Failed to save permanent students to Firebase: {e}")
    
    def save_guards_to_firebase(self):
        """Save guard RFID numbers to Firebase guards collection"""
        try:
            if self.firebase_initialized and self.db:
                # Guard data to save
                guards_data = [
                    {
                        'guard_id': '0095081841',
                        'rfid': '0095081841',
                        'name': 'Guard 1',
                        'role': 'Security Guard',
                        'status': 'active',
                        'created_at': self.get_current_timestamp(),
                        'last_login': None,
                        'total_logins': 0
                    },
                    {
                        'guard_id': '0095339862',
                        'rfid': '0095339862',
                        'name': 'Guard 2',
                        'role': 'Security Guard',
                        'status': 'active',
                        'created_at': self.get_current_timestamp(),
                        'last_login': None,
                        'total_logins': 0
                    }
                ]
                
                # Save each guard to Firebase
                for guard_data in guards_data:
                    guard_ref = self.db.collection('guards').document(guard_data['guard_id'])
                    guard_ref.set(guard_data)
                    print(f"SUCCESS: Guard {guard_data['guard_id']} saved to Firebase guards collection")
                
                print("SUCCESS: All guards saved to Firebase guards collection")
                
            else:
                print("WARNING: Firebase not available - guards not saved to cloud")
                
        except Exception as e:
            print(f"ERROR: Failed to save guards to Firebase: {e}")
    
    def update_guard_login_info(self, guard_id):
        """Update guard's last login and total logins count in Firebase"""
        try:
            if self.firebase_initialized and self.db:
                guard_ref = self.db.collection('guards').document(guard_id)
                
                # Get current guard data
                guard_doc = guard_ref.get()
                if guard_doc.exists:
                    guard_data = guard_doc.to_dict()
                    current_logins = guard_data.get('total_logins', 0)
                    
                    # Update guard login information
                    guard_ref.update({
                        'last_login': self.get_current_timestamp(),
                        'total_logins': current_logins + 1,
                        'status': 'active'
                    })
                    
                    print(f"SUCCESS: Guard {guard_id} login info updated in Firebase")
                else:
                    print(f"WARNING: Guard {guard_id} not found in Firebase guards collection")
                    
            else:
                print("WARNING: Firebase not available - guard login info not updated")
                
        except Exception as e:
            print(f"ERROR: Failed to update guard login info: {e}")
    
    def approve_gate(self):
        """Approve and open the gate"""
        try:
            # Add to activity log
            self.add_activity_log("GATE APPROVED - Gate opened by guard")
            
            # Show confirmation
            messagebox.showinfo("Gate Approved", 
                              "SUCCESS: Gate has been OPENED\n\n"
                              "Access granted - Gate is now open for entry/exit.\n\n"
                              "Remember to close the gate when appropriate.")
            
            # Update button states to show gate is open
            self.approve_btn.config(
                text="SUCCESS: OPEN",
                bg='#059669',
                state='disabled'
            )
            self.deny_btn.config(
                text="ERROR: DENY",
                bg='#dc2626',
                state='normal'
            )
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open gate: {e}")
    
    def deny_gate(self):
        """Deny and close the gate"""
        try:
            # Add to activity log
            self.add_activity_log("GATE DENIED - Gate closed by guard")
            
            # Show confirmation
            messagebox.showinfo("Gate Denied", 
                              "ERROR: Gate has been CLOSED\n\n"
                              "Access denied - Gate is now closed.\n\n"
                              "No entry/exit allowed until approved.")
            
            # Update button states to show gate is closed
            self.deny_btn.config(
                text="ERROR: CLOSED",
                bg='#b91c1c',
                state='disabled'
            )
            self.approve_btn.config(
                text="SUCCESS: APPROVE",
                bg='#10b981',
                state='normal'
            )
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to close gate: {e}")
    
    def update_button_states(self, selected_type):
        """Update button visual states"""
        # No person type buttons to update since they were removed
        pass
    
    def create_camera_feed_section(self, parent):
        """Create camera feed section in box/portrait orientation"""
        camera_frame = tk.LabelFrame(
            parent,
            text="LIVE CAMERA FEED",
            font=('Arial', 14, 'bold'),
            fg='#374151',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        camera_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Camera feed label with box/portrait orientation - STANDBY MODE
        self.camera_label = tk.Label(
            camera_frame,
            text="📷 CAMERA FEED (STANDBY MODE)\n\n🔒 Camera is CLOSED\n\nCamera will ONLY open when:\n• Student taps their ID\n• Detection process starts\n\nNo camera access during guard login\n\n💡 Camera preview will show here\nwhen detection is active",
            font=('Arial', 12),
            fg='#374151',
            bg='#dbeafe',
            justify=tk.CENTER,
            relief='sunken',
            bd=3
            # Remove fixed width/height to allow proper scaling
        )
        # Use fill=tk.BOTH for square/portrait orientation
        self.camera_label.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)
        
        # Set minimum height for portrait orientation
        camera_frame.configure(height=520)
    
    def create_gate_control_section(self, parent):
        """Create gate control section with interface buttons"""
        gate_frame = tk.LabelFrame(
            parent,
            text="🚪 Gate Control",
            font=('Arial', 12, 'bold'),
            fg='#1f2937',
            bg='#ffffff',
            relief='solid',
            bd=1
        )
        gate_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Gate status display
        status_frame = tk.Frame(gate_frame, bg='#ffffff')
        status_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        self.gate_status_label = tk.Label(
            status_frame,
            text="🔒 Gate: Locked",
            font=('Arial', 11, 'bold'),
            fg='#dc2626',
            bg='#ffffff'
        )
        self.gate_status_label.pack(side=tk.LEFT)
        
        # Arduino connection status
        self.arduino_status_label = tk.Label(
            status_frame,
            text="🔌 Arduino: Disconnected",
            font=('Arial', 10),
            fg='#6b7280',
            bg='#ffffff'
        )
        self.arduino_status_label.pack(side=tk.RIGHT)
        
        # Update Arduino status if already connected
        if hasattr(self, 'arduino_connected') and self.arduino_connected:
            self.update_arduino_connection_status(True)
        
        # Control buttons frame
        buttons_frame = tk.Frame(gate_frame, bg='#ffffff')
        buttons_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
        
        # Approve button
        self.approve_button = tk.Button(
            buttons_frame,
            text="SUCCESS: APPROVE\n(Unlock Gate)",
            font=('Arial', 11, 'bold'),
            bg='#10b981',
            fg='white',
            relief='raised',
            bd=2,
            padx=15,
            pady=8,
            cursor='hand2',
            activebackground='#059669',
            activeforeground='white',
            command=self.handle_interface_approve
        )
        self.approve_button.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        
        # Deny button
        self.deny_button = tk.Button(
            buttons_frame,
            text="ERROR: DENY\n(Keep Locked)",
            font=('Arial', 11, 'bold'),
            bg='#dc2626',
            fg='white',
            relief='raised',
            bd=2,
            padx=15,
            pady=8,
            cursor='hand2',
            activebackground='#b91c1c',
            activeforeground='white',
            command=self.handle_interface_deny
        )
        self.deny_button.pack(side=tk.RIGHT, padx=(10, 0), fill=tk.X, expand=True)
        
        # Instructions
        instructions_label = tk.Label(
            gate_frame,
            text="💡 Use buttons to control gate based on uniform detection results",
            font=('Arial', 9, 'italic'),
            fg='#6b7280',
            bg='#ffffff',
            wraplength=350
        )
        instructions_label.pack(pady=(0, 10))
    
    def handle_interface_approve(self):
        """Handle approve button press from interface"""
        try:
            print("SUCCESS: Interface Approve button pressed - Unlocking gate")
            self.add_activity_log("Interface Approve button pressed - Unlocking gate")
            
            # Send approve command to Arduino
            self.send_arduino_command("APPROVE")
            
            # Update gate status
            self.gate_status_label.config(text="🔓 Gate: Unlocked", fg='#10b981')
            
            # Show success message
            self.show_green_success_message("Gate Approved", 
                              "SUCCESS: Gate is unlocking\n"
                              "🚪 Person may proceed\n"
                              "⏰ Auto-lock in 3 seconds")
            
            # Update main screen
            if self.main_screen_window and self.main_screen_window.winfo_exists():
                self.update_main_screen_with_gate_status("UNLOCKED", "APPROVED")
            
            # Schedule status update after unlock duration
            self.root.after(3500, self.update_gate_status_locked)
            
        except Exception as e:
            print(f"ERROR: Error handling interface approve: {e}")
            self.add_activity_log(f"Error handling interface approve: {e}")
    
    def handle_interface_deny(self):
        """Handle deny button press from interface"""
        try:
            print("ERROR: Interface Deny button pressed - Keeping gate locked")
            self.add_activity_log("Interface Deny button pressed - Keeping gate locked")
            
            # Send deny command to Arduino
            self.send_arduino_command("DENY")
            
            # Update gate status
            self.gate_status_label.config(text="🔒 Gate: Locked", fg='#dc2626')
            
            # Show warning message
            self.show_red_warning_message("Gate Denied", 
                              "ERROR: Gate remains locked\n"
                              "🚪 Person must correct uniform\n"
                              "👤 Check uniform requirements")
            
            # Update main screen
            if self.main_screen_window and self.main_screen_window.winfo_exists():
                self.update_main_screen_with_gate_status("LOCKED", "DENIED")
            
        except Exception as e:
            print(f"ERROR: Error handling interface deny: {e}")
            self.add_activity_log(f"Error handling interface deny: {e}")
    
    def update_gate_status_locked(self):
        """Update gate status to locked after auto-lock"""
        try:
            self.gate_status_label.config(text="🔒 Gate: Locked", fg='#dc2626')
            self.add_activity_log("Gate auto-locked after 3 seconds")
        except Exception as e:
            print(f"ERROR: Error updating gate status: {e}")
    
    def update_arduino_connection_status(self, connected):
        """Update Arduino connection status display"""
        try:
            # Check if the dashboard has been created and arduino_status_label exists
            if hasattr(self, 'arduino_status_label') and self.arduino_status_label and hasattr(self.arduino_status_label, 'config'):
                if connected:
                    self.arduino_status_label.config(text="🔌 Arduino: Connected", fg='#10b981')
                else:
                    self.arduino_status_label.config(text="🔌 Arduino: Disconnected", fg='#dc2626')
            else:
                # Dashboard not created yet, just log the status
                status = "Connected" if connected else "Disconnected"
                print(f"🔌 Arduino: {status} (UI update pending)")
        except Exception as e:
            print(f"ERROR: Error updating Arduino status: {e}")
    
    def create_activity_logs_section(self, parent):
        """Create activity logs section"""
        logs_frame = tk.LabelFrame(
            parent,
            text="Activity Logs",
            font=('Arial', 14, 'bold'),
            fg='#374151',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        logs_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Logs text widget
        self.logs_text = tk.Text(
            logs_frame,
            height=10,
            font=('Consolas', 11),
            bg='#f8fafc',
            fg='#374151',
            relief='flat',
            bd=1,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.logs_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Add initial message
        self.add_activity_log("System initialized successfully")
        self.add_activity_log("Ready for guard operations")
    
    def set_person_type(self, person_type):
        """Set the selected person type"""
        self.person_type_var.set(person_type)
        
        # Reset all buttons
        self.student_btn.config(bg='#dbeafe', fg='#1e3a8a')
        self.teacher_btn.config(bg='#dbeafe', fg='#1e3a8a')
        self.visitor_btn.config(bg='#dbeafe', fg='#1e3a8a')
        
        # Highlight selected button
        if person_type == "student":
            self.student_btn.config(bg='#1e3a8a', fg='white')
        elif person_type == "teacher":
            self.teacher_btn.config(bg='#1e3a8a', fg='white')
        elif person_type == "visitor":
            self.visitor_btn.config(bg='#1e3a8a', fg='white')
    
    def log_person_entry(self):
        """Log person entry and start detection if needed"""
        person_id = self.person_id_var.get().strip().upper()
        person_type = self.person_type_var.get()
        
        if not person_id:
            messagebox.showwarning("Warning", "Please enter a Person ID")
            return
        
        # Ensure Firebase is ready before processing
        if not self.firebase_initialized:
            print("INFO: Firebase not ready, attempting to initialize...")
            # Show status message to user
            self.add_activity_log("INFO: Initializing Firebase connection...")
            
            # Check if we've already tried Firebase initialization multiple times
            if not hasattr(self, 'firebase_init_attempts'):
                self.firebase_init_attempts = 0
            
            self.firebase_init_attempts += 1
            
            # If we've tried too many times, go directly to offline mode
            if self.firebase_init_attempts > 2:
                print("WARNING: Firebase initialization failed multiple times - switching to offline mode")
                self.add_activity_log("WARNING: Firebase initialization failed multiple times - switching to offline mode")
                self.firebase_initialized = False
                self.root.after(1000, lambda: self.process_person_entry_offline())
                return
            
            # Try to initialize Firebase with better error handling
            try:
                success = self.init_firebase()
                import time
                time.sleep(1)  # Shorter wait time
                
                if not success:
                    print("WARNING: Firebase initialization failed, trying alternative method...")
                    self.add_activity_log("WARNING: Firebase initialization failed, trying alternative method...")
                    self.init_firebase_async()
                    time.sleep(2)  # Shorter wait time
                
                # Try again if still not initialized
                if not self.firebase_initialized:
                    print("WARNING: Firebase still not ready, retrying in 3 seconds...")
                    self.add_activity_log("WARNING: Firebase initialization delayed, retrying...")
                    self.root.after(3000, lambda: self.retry_person_entry())
                    return
                else:
                    print("SUCCESS: Firebase initialized successfully on retry")
                    self.add_activity_log("SUCCESS: Firebase initialized successfully on retry")
            except Exception as e:
                print(f"ERROR: Firebase initialization failed: {e}")
                self.add_activity_log(f"ERROR: Firebase initialization failed: {e}")
                print("WARNING: Switching to offline mode...")
                self.add_activity_log("WARNING: Switching to offline mode...")
                self.firebase_initialized = False
                self.root.after(1000, lambda: self.process_person_entry_offline())
            return
        
        # Check if this is a visitor RFID tap
        if person_type == "visitor" and person_id in self.visitor_rfid_registry:
            self.handle_visitor_rfid_tap(person_id)
            self.person_id_var.set("")  # Clear input
            return
        
        # Check if this is a student forgot ID RFID tap
        if person_type == "student" and person_id in self.student_rfid_assignments:
            self.handle_student_forgot_id_rfid_tap(person_id)
            self.person_id_var.set("")  # Clear input
            return
        
        # Check if this is a permanent student RFID tap
        if person_type == "student" and self.is_permanent_student_rfid(person_id):
            self.handle_permanent_student_rfid_tap(person_id)
            self.person_id_var.set("")  # Clear input
            return
        
        # Log the entry
        self.add_activity_log(f"Person Entry: {person_id} ({person_type})")
        
        # Check if this person is already detected (for exit)
        if (hasattr(self, 'current_person_id') and 
            self.current_person_id == person_id and 
            self.detection_active):
            # This is an exit - stop detection and log exit
            self.stop_detection()
            self.add_activity_log(f"Person Exit: {person_id} ({person_type})")
            
            # Update main screen with exit status
            if self.main_screen_window and self.main_screen_window.winfo_exists():
                self.update_main_screen_with_exit(person_id, person_type)
            
            return
        
        # Get person information for main screen display
        if person_type.lower() == 'student':
            # For students, try to get info by RFID first, then by student ID
            student_info = self.get_student_info_by_rfid(person_id)
            if not student_info:
                # Try get_student_info but avoid the offline fallback that creates "Student {person_id}"
                try:
                    if self.firebase_initialized and self.db:
                        # Query Firebase directly to avoid offline fallback
                        doc_ref = self.db.collection('students').document(person_id)
                        doc = doc_ref.get()
                        
                        if doc.exists:
                            data = doc.to_dict()
                            student_info = {
                                'name': data.get('Name', 'Unknown'),
                                'course': data.get('Course', data.get('Department', 'Unknown')),
                                'gender': data.get('Gender', 'Unknown')
                            }
                except Exception as e:
                    print(f"WARNING: Firebase query failed in fallback: {e}")
            
            if student_info:
                from datetime import datetime
                person_info = {
                    'id': person_id,
                    'name': student_info.get('name', 'Unknown Student'),
                    'type': 'student',
                    'course': student_info.get('course', 'Unknown'),
                    'gender': student_info.get('gender', 'Unknown'),
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'status': 'TIME-IN',
                    'guard_id': self.current_guard_id or 'Unknown'
                }
            else:
                # Only use fallback if we really can't find the student
                person_info = self.get_person_info_for_main_screen(person_id, person_type)
        else:
            print("WARNING: No student info found, using fallback")
            person_info = self.get_person_info_for_main_screen(person_id, person_type)
        person_info = self.get_person_info_for_main_screen(person_id, person_type)
        
        # Update main screen with person information
        if self.main_screen_window and self.main_screen_window.winfo_exists():
            self.update_main_screen_with_person(person_info)
        
        # Clear the input
        self.person_id_var.set("")
        
        # Start detection for students and teachers
        if person_type in ["student", "teacher"]:
            try:
                person_name = self.get_person_name(person_id, person_type)
                self.start_person_detection(person_id, person_name, person_type)
                self.add_activity_log(f"Detection started for {person_name} ({person_type})")
                messagebox.showinfo("Success", f"Person entry logged and detection started: {person_id} ({person_type})")
            except Exception as e:
                self.add_activity_log(f"Failed to start detection: {str(e)}")
                messagebox.showwarning("Detection Error", f"Person logged but detection failed: {str(e)}")
        else:
            messagebox.showinfo("Success", f"Person entry logged: {person_id} ({person_type})")
    
    def get_person_info_for_main_screen(self, person_id, person_type):
        """Get person information formatted for main screen display"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if person_type.lower() == 'student':
                # Get student information
                student_info = self.get_student_info(person_id)
                return {
                    'id': person_id,
                    'name': student_info.get('name', 'Unknown Student'),
                    'type': 'student',
                    'course': student_info.get('course', 'Unknown'),
                    'gender': student_info.get('gender', 'Unknown'),
                    'timestamp': current_time,
                    'status': 'TIME-IN',
                    'guard_id': self.current_guard_id or 'Unknown'
                }
            elif person_type.lower() == 'teacher':
                return {
                    'id': person_id,
                    'name': f"Teacher {person_id}",
                    'type': 'teacher',
                    'course': 'Faculty',
                    'gender': 'N/A',
                    'timestamp': current_time,
                    'status': 'TIME-IN',
                    'guard_id': self.current_guard_id or 'Unknown'
                }
            elif person_type.lower() == 'visitor':
                return {
                    'id': person_id,
                    'name': f"Visitor {person_id}",
                    'type': 'visitor',
                    'course': 'N/A',
                    'gender': 'N/A',
                    'timestamp': current_time,
                    'status': 'TIME-IN',
                    'guard_id': self.current_guard_id or 'Unknown'
                }
            else:
                return {
                    'id': person_id,
                    'name': f"Person {person_id}",
                    'type': person_type,
                    'course': 'N/A',
                    'gender': 'N/A',
                    'timestamp': current_time,
                    'status': 'TIME-IN',
                    'guard_id': self.current_guard_id or 'Unknown'
                }
        except Exception as e:
            print(f"ERROR: Error getting person info: {e}")
            return {
                'id': person_id,
                    'name': 'Unknown',
                'type': person_type,
                'course': 'N/A',
                'gender': 'N/A',
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'status': 'TIME-IN',
                'guard_id': 'Unknown'
            }
    
    def update_main_screen_with_person(self, person_info):
        """Update main screen with person information"""
        try:
            if not self.main_screen_window or not self.main_screen_window.winfo_exists():
                print("WARNING: Main screen window not available")
                return
            
            # Clear existing content
            for widget in self.person_display_frame.winfo_children():
                widget.destroy()
            
            # Create main info frame
            main_info_frame = tk.Frame(self.person_display_frame, bg='#ffffff')
            main_info_frame.pack(fill=tk.BOTH, expand=True)
            
            # Status indicator
            status_color = '#10b981' if person_info['status'] == 'TIME-IN' else '#ef4444'
            status_frame = tk.Frame(main_info_frame, bg=status_color, height=60)
            status_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
            status_frame.pack_propagate(False)
            
            status_label = tk.Label(
                status_frame,
                text=f"{person_info['status']}",
                font=('Arial', 24, 'bold'),
                fg='white',
                bg=status_color
            )
            status_label.pack(expand=True)
            
            # Person details
            details_frame = tk.Frame(main_info_frame, bg='#ffffff')
            details_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            # Name
            name_label = tk.Label(
                details_frame,
                text=person_info['name'],
                font=('Arial', 28, 'bold'),
                fg='#1e3a8a',
                bg='#ffffff'
            )
            name_label.pack(pady=(0, 15))
            
            # ID
            id_label = tk.Label(
                details_frame,
                text=f"ID: {person_info['id']}",
                font=('Arial', 20, 'bold'),
                fg='#374151',
                bg='#ffffff'
            )
            id_label.pack(pady=(0, 10))
            
            # Type
            type_label = tk.Label(
                details_frame,
                text=f"Type: {person_info['type'].title()}",
                font=('Arial', 18, 'bold'),
                fg='#3b82f6',
                bg='#ffffff'
            )
            type_label.pack(pady=(0, 5))
            
            # Department (for students)
            if person_info['type'] == 'student':
                course_label = tk.Label(
                    details_frame,
                    text=f"Department: {person_info['course']}",
                    font=('Arial', 18, 'bold'),
                    fg='#3b82f6',
                    bg='#ffffff'
                )
                course_label.pack(pady=(0, 5))
                
                gender_label = tk.Label(
                    details_frame,
                    text=f"Gender: {person_info['gender']}",
                    font=('Arial', 18, 'bold'),
                    fg='#3b82f6',
                    bg='#ffffff'
                )
                gender_label.pack(pady=(0, 5))
            
            # Time
            time_label = tk.Label(
                details_frame,
                text=f"Time: {person_info['timestamp']}",
                font=('Arial', 16, 'bold'),
                fg='#1e3a8a',
                bg='#ffffff'
            )
            time_label.pack(pady=(20, 0))
            
            # Guard
            guard_label = tk.Label(
                details_frame,
                text=f"Processed by: {person_info['guard_id']}",
                font=('Arial', 14, 'bold'),
                fg='#6b7280',
                bg='#ffffff'
            )
            guard_label.pack(pady=(10, 0))
            
            # Add to recent entries
            self.add_to_recent_entries(person_info)
            
            print(f"SUCCESS: Main screen updated with {person_info['name']} ({person_info['status']})")
            
        except Exception as e:
            print(f"ERROR: Error updating main screen: {e}")
    
    def update_main_screen_with_exit(self, person_id, person_type):
        """Update main screen with exit information"""
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Get person name
            person_name = self.get_person_name(person_id, person_type)
            
            exit_info = {
                'id': person_id,
                'name': person_name,
                'type': person_type,
                'course': 'N/A',
                'gender': 'N/A',
                'timestamp': current_time,
                'status': 'TIME-OUT',
                'guard_id': self.current_guard_id or 'Unknown'
            }
            
            # Update main screen
            self.update_main_screen_with_person(exit_info)
            
        except Exception as e:
            print(f"ERROR: Error updating main screen with exit: {e}")
    
    def _update_main_screen_with_detection_result(self, status, complete_components, missing_components):
        """Update main screen with uniform detection results"""
        try:
            if not self.main_screen_window or not self.main_screen_window.winfo_exists():
                return
            
            # Get current person info
            if not hasattr(self, 'current_person_id') or not self.current_person_id:
                return
            
            person_id = self.current_person_id
            person_type = getattr(self, 'current_person_type', 'student')
            
            # Get person information
            person_info = self.get_person_info_for_main_screen(person_id, person_type)
            
            # Add detection results to person info
            person_info['detection_status'] = status
            person_info['complete_components'] = complete_components
            person_info['missing_components'] = missing_components
            
            # Update main screen with enhanced information
            self.update_main_screen_with_detection_details(person_info)
            
        except Exception as e:
            print(f"ERROR: Error updating main screen with detection result: {e}")
    
    def update_main_screen_with_detection_details(self, person_info):
        """Update main screen with detailed detection information"""
        try:
            if not self.main_screen_window or not self.main_screen_window.winfo_exists():
                return
            
            # Clear existing content
            for widget in self.person_display_frame.winfo_children():
                widget.destroy()
            
            # Create main info frame
            main_info_frame = tk.Frame(self.person_display_frame, bg='#ffffff')
            main_info_frame.pack(fill=tk.BOTH, expand=True)
            
            # Status indicator based on detection result
            if person_info.get('detection_status') == 'COMPLETE UNIFORM':
                status_color = '#10b981'  # Green for complete
                status_text = 'UNIFORM COMPLIANT'
            else:
                status_color = '#ef4444'  # Red for incomplete
                status_text = 'UNIFORM VIOLATION'
            
            status_frame = tk.Frame(main_info_frame, bg=status_color, height=60)
            status_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
            status_frame.pack_propagate(False)
            
            status_label = tk.Label(
                status_frame,
                text=status_text,
                font=('Arial', 24, 'bold'),
                fg='white',
                bg=status_color
            )
            status_label.pack(expand=True)
            
            # Person details
            details_frame = tk.Frame(main_info_frame, bg='#ffffff')
            details_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
            
            # Name
            name_label = tk.Label(
                details_frame,
                text=person_info['name'],
                font=('Arial', 28, 'bold'),
                fg='#1e3a8a',
                bg='#ffffff'
            )
            name_label.pack(pady=(0, 15))
            
            # ID
            id_label = tk.Label(
                details_frame,
                text=f"ID: {person_info['id']}",
                font=('Arial', 20, 'bold'),
                fg='#374151',
                bg='#ffffff'
            )
            id_label.pack(pady=(0, 10))
            
            # Detection results
            if person_info.get('detection_status'):
                detection_label = tk.Label(
                    details_frame,
                    text=f"Detection: {person_info['detection_status']}",
                    font=('Arial', 18, 'bold'),
                    fg=status_color,
                    bg='#ffffff'
                )
                detection_label.pack(pady=(0, 10))
                
                # Complete components
                if person_info.get('complete_components'):
                    complete_text = f"SUCCESS: Detected: {', '.join(person_info['complete_components'])}"
                    complete_label = tk.Label(
                        details_frame,
                        text=complete_text,
                        font=('Arial', 14, 'bold'),
                        fg='#10b981',
                        bg='#ffffff'
                    )
                    complete_label.pack(pady=(0, 5))
                
                # Missing components
                if person_info.get('missing_components'):
                    missing_text = f"ERROR: Missing: {', '.join(person_info['missing_components'])}"
                    missing_label = tk.Label(
                        details_frame,
                        text=missing_text,
                        font=('Arial', 14, 'bold'),
                        fg='#ef4444',
                        bg='#ffffff'
                    )
                    missing_label.pack(pady=(0, 5))
            
            # Time
            time_label = tk.Label(
                details_frame,
                text=f"Time: {person_info['timestamp']}",
                font=('Arial', 16, 'bold'),
                fg='#1e3a8a',
                bg='#ffffff'
            )
            time_label.pack(pady=(20, 0))
            
            # Guard
            guard_label = tk.Label(
                details_frame,
                text=f"Processed by: {person_info['guard_id']}",
                font=('Arial', 14, 'bold'),
                fg='#6b7280',
                bg='#ffffff'
            )
            guard_label.pack(pady=(10, 0))
            
            # Add to recent entries
            self.add_to_recent_entries(person_info)
            
            print(f"SUCCESS: Main screen updated with detection results for {person_info['name']}")
            
        except Exception as e:
            print(f"ERROR: Error updating main screen with detection details: {e}")
    
    def get_student_info(self, person_id):
        """Get student information from Firebase or offline data"""
        try:
            # Try Firebase first if available
            if self.firebase_initialized and self.db:
                try:
                    # Query Firebase students collection
                    doc_ref = self.db.collection('students').document(person_id)
                    doc = doc_ref.get()
                    
                    if doc.exists:
                        # Get document data
                        data = doc.to_dict()
                        
                        # Extract student information
                        student_info = {
                            'name': data.get('Name', 'Unknown'),
                            'course': data.get('Course', data.get('Department', 'Unknown')),
                            'gender': data.get('Gender', 'Unknown')
                        }
                        
                        print(f"SUCCESS: Student found in Firebase: {student_info['name']} ({student_info['course']})")
                        return student_info
                except Exception as e:
                    print(f"WARNING: Firebase query failed: {e}")
            
            # Fallback to offline data
            return self.get_offline_student_info(person_id)
                
        except Exception as e:
            print(f"ERROR: Error fetching student info: {e}")
            return self.get_offline_student_info(person_id)
    
    def get_offline_student_info(self, person_id):
        """Get student information from offline data"""
        try:
            import json
            if os.path.exists("offline_students.json"):
                with open("offline_students.json", "r") as f:
                    offline_students = json.load(f)
                
                if person_id in offline_students:
                    student_info = offline_students[person_id]
                    print(f"SUCCESS: Student found in offline data: {student_info['name']} ({student_info['course']})")
                    return student_info
            
            # Default fallback
            print(f"WARNING: Student ID '{person_id}' not found - using default")
            return {
                'name': f'Student {person_id}',
                'course': 'ICT',
                'gender': 'MALE'
            }
                
        except Exception as e:
            print(f"ERROR: Error loading offline student data: {e}")
            return {
                'name': f'Student {person_id}',
                'course': 'ICT',
                'gender': 'MALE'
            }
    
    def retry_person_entry(self):
        """Retry person entry after Firebase initialization"""
        try:
            print("INFO: Retrying person entry after Firebase initialization...")
            self.add_activity_log("INFO: Retrying person entry after Firebase initialization...")
            
            # Try to initialize Firebase again with more detailed error handling
            if not self.firebase_initialized:
                print("INFO: Attempting Firebase initialization in retry...")
                self.add_activity_log("INFO: Attempting Firebase initialization in retry...")
                
                # Try multiple initialization methods
                success = False
                try:
                    success = self.init_firebase()
                except Exception as e:
                    print(f"ERROR: Firebase initialization failed in retry: {e}")
                    self.add_activity_log(f"ERROR: Firebase initialization failed in retry: {e}")
                
                if not success:
                    # Try alternative initialization
                    try:
                        print("INFO: Trying alternative Firebase initialization...")
                        self.init_firebase_async()
                        import time
                        time.sleep(3)  # Wait longer for async initialization
                    except Exception as e:
                        print(f"ERROR: Alternative Firebase initialization failed: {e}")
                        self.add_activity_log(f"ERROR: Alternative Firebase initialization failed: {e}")
            
            if self.firebase_initialized:
                print("SUCCESS: Firebase is now ready, processing person entry...")
                self.add_activity_log("SUCCESS: Firebase is now ready, processing person entry...")
                # Process the person entry directly instead of calling log_person_entry again
                self.process_person_entry_after_retry()
            else:
                print("WARNING: Firebase still not ready, will retry again in 5 seconds...")
                self.add_activity_log("WARNING: Firebase still not ready, will retry again...")
                # Limit retries to prevent infinite loop
                if not hasattr(self, 'firebase_retry_count'):
                    self.firebase_retry_count = 0
                self.firebase_retry_count += 1
                
                if self.firebase_retry_count <= 2:  # Max 2 retries
                    self.root.after(3000, lambda: self.retry_person_entry())
                else:
                    print("ERROR: Firebase initialization failed after multiple retries - switching to offline mode")
                    self.add_activity_log("ERROR: Firebase initialization failed after multiple retries - switching to offline mode")
                    self.firebase_initialized = False
                    # Process with offline data
                    self.process_person_entry_offline()
        except Exception as e:
            print(f"ERROR: Error in retry person entry: {e}")
            self.add_activity_log(f"ERROR: Error in retry person entry: {e}")
    
    def process_person_entry_after_retry(self):
        """Process person entry after successful Firebase retry"""
        try:
            person_id = self.person_id_var.get().strip().upper()
            person_type = self.person_type_var.get()
            
            if not person_id:
                return
            
            print(f"INFO: Processing person entry after retry: {person_id} ({person_type})")
            self.add_activity_log(f"INFO: Processing person entry after retry: {person_id} ({person_type})")
            
            # Check if this is a permanent student RFID tap
            if person_type == "student" and self.is_permanent_student_rfid(person_id):
                self.handle_permanent_student_rfid_tap(person_id)
                self.person_id_var.set("")  # Clear input
                return
            
            # For other types, use the regular processing
            # (This is a simplified version - you might need to add other cases)
            print(f"INFO: Regular processing for {person_id} ({person_type})")
            
        except Exception as e:
            print(f"ERROR: Error processing person entry after retry: {e}")
            self.add_activity_log(f"ERROR: Error processing person entry after retry: {e}")
    
    def process_person_entry_offline(self):
        """Process person entry using offline data when Firebase is unavailable"""
        try:
            person_id = self.person_id_var.get().strip().upper()
            person_type = self.person_type_var.get()
            
            if not person_id:
                return
            
            print(f"INFO: Processing person entry offline: {person_id} ({person_type})")
            self.add_activity_log(f"INFO: Processing person entry offline: {person_id} ({person_type})")
            
            # Create basic person info for offline mode
            from datetime import datetime
            person_info = {
                'id': person_id,
                'name': f'Student {person_id}' if person_type == 'student' else f'{person_type.title()} {person_id}',
                'type': person_type,
                'course': 'Unknown',
                'gender': 'Unknown',
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'status': 'TIME-IN',
                'guard_id': self.current_guard_id or 'Unknown'
            }
            
            # Update main screen with offline person information
            if self.main_screen_window and self.main_screen_window.winfo_exists():
                self.update_main_screen_with_person(person_info)
            
            # Clear the input
            self.person_id_var.set("")
            
            print(f"SUCCESS: Person entry processed offline: {person_info['name']}")
            self.add_activity_log(f"SUCCESS: Person entry processed offline: {person_info['name']}")
            
        except Exception as e:
            print(f"ERROR: Error processing person entry offline: {e}")
            self.add_activity_log(f"ERROR: Error processing person entry offline: {e}")
    
    def get_person_name(self, person_id, person_type):
        """Get person name based on ID and type"""
        if person_type == "student":
            student_info = self.get_student_info(person_id)
            return student_info['name']
        elif person_type == "teacher":
            return f"Teacher {person_id}"
        else:
            return f"Person {person_id}"
    
    def _get_model_path_for_person(self, person_id, person_type):
        """Get the appropriate model path for a person based on their type and gender"""
        try:
            if person_type.lower() == 'student':
                # Get student info to determine gender
                student_info = self.get_student_info(person_id)
                gender = student_info.get('gender', '').lower()
                
                if 'female' in gender:
                    return 'bsba_female.pt'
                elif 'male' in gender:
                    return 'bsba male2.pt'
                else:
                    # Default to male model if gender is unclear
                    return 'bsba male2.pt'
            else:
                # For non-students, default to male model
                return 'bsba male2.pt'
        except Exception as e:
            print(f"WARNING: Could not determine model for person {person_id}: {e}")
            # Default fallback
            return 'bsba male2.pt'
    
    def reset_uniform_tracking(self):
        """Reset uniform tracking for new person"""
        try:
            # Reset any uniform tracking variables if they exist
            if hasattr(self, 'detected_components'):
                self.detected_components = {}
            if hasattr(self, 'uniform_complete'):
                self.uniform_complete = False
            if hasattr(self, 'detection_start_time'):
                self.detection_start_time = None
            print("DEBUG: Uniform tracking reset")
        except Exception as e:
            print(f"WARNING: Could not reset uniform tracking: {e}")
    
    def start_person_detection(self, person_id, person_name, person_type):
        """Start detection for a person"""
        try:
            # Store current person ID for detection context
            self.current_person_id = person_id
            self.last_person_id = person_id
            
            # Determine model based on person type or ID
            model_path = self._get_model_path_for_person(person_id, person_type)
            if model_path != self.current_model_path:
                self.current_model_path = model_path
                print(f"INFO: Switching to model: {model_path}")
                
                # Log model selection with student details
                if person_type.lower() == 'student':
                    student_info = self.get_student_info(person_id)
                    print(f"📋 Student: {student_info['name']} | Course: {student_info['course']} | Gender: {student_info['gender']}")
                    print(f"🤖 Selected Model: {model_path}")
            
            # Update camera label
            self.update_camera_label_for_detection(person_id, person_name, person_type)
            
            # Reset uniform tracking for new person
            self.reset_uniform_tracking()
            
            # Reset detection history for new detection session
            if hasattr(self, 'detection_system') and self.detection_system:
                self.detection_system.reset_detection_history()
            
            # Update main screen with person information
            self.update_main_screen_with_person_info(person_id, person_name, person_type)
            
            # Start detection using detection service
            print(f"DEBUG: CV2_AVAILABLE: {CV2_AVAILABLE}, YOLO_AVAILABLE: {YOLO_AVAILABLE}")
            self.add_activity_log(f"DEBUG: CV2_AVAILABLE: {CV2_AVAILABLE}, YOLO_AVAILABLE: {YOLO_AVAILABLE}")
            if CV2_AVAILABLE and YOLO_AVAILABLE:
                print("DEBUG: Starting real detection with integrated system")
                self.add_activity_log("DEBUG: Starting real detection with integrated system")
                self.start_person_detection_integrated(person_id, person_name, person_type)
            else:
                print("WARNING: CV2 or YOLO not available, detection disabled")
                self.add_activity_log("WARNING: CV2 or YOLO not available, detection disabled")
            
        except Exception as e:
            print(f"ERROR: Failed to start person detection: {e}")
            self.add_activity_log(f"Failed to start detection: {e}")
    
    def update_camera_label_for_detection(self, person_id, person_name, person_type):
        """Update camera label to show detection status"""
        try:
            # Check if camera label exists and UI is ready
            if not hasattr(self, 'camera_label') or not self.camera_label or not self.root.winfo_exists():
                print("WARNING: Camera label not available for detection update")
                return
            
            # Get student information to show course and gender
            if person_type.lower() == 'student':
                student_info = self.get_student_info(person_id)
                course = student_info['course']
                gender = student_info['gender']
                model_info = f"Model: {self.current_model_path}"
            else:
                course = "N/A"
                gender = "N/A"
                model_info = f"Model: {self.current_model_path}"
            
            detection_text = f"""🎥 LIVE CAMERA FEED - DETECTION ACTIVE

👤 Person: {person_name}
🆔 ID: {person_id}
📚 Type: {person_type.title()}
🎓 Course: {course}
👤 Gender: {gender}

📷 Camera Starting...
INFO: AI Detection Initializing...
🤖 {model_info}

💡 Position yourself in front of the camera
for uniform detection

WARNING: Live video preview will appear here
once camera is fully initialized"""
            
            self.camera_label.config(
                text=detection_text,
                fg='#059669',
                font=('Arial', 11, 'bold'),
                bg='#d1fae5',
                relief='sunken',
                bd=3,
                justify=tk.CENTER
            )
            # Maintain portrait orientation
            self.camera_label.pack(expand=True, fill=tk.BOTH, padx=15, pady=15)
            
            print(f"SUCCESS: Camera label updated for {person_name} ({person_id})")
            
        except Exception as e:
            print(f"ERROR: Failed to update camera label: {e}")
    
    def get_detection_performance_stats(self):
        """Get current detection performance statistics"""
        if hasattr(self, 'detection_system') and self.detection_system:
            return {
                'fps': getattr(self.detection_system, 'fps', 0),
                'frame_count': getattr(self.detection_system, 'frame_count', 0),
                'frame_skip': getattr(self.detection_system, 'frame_skip', 2)
            }
        return {}
    def stop_detection(self):
        """Stop the detection system"""
        self.detection_active = False
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=2)
        
        # Stop camera display loop
        self.camera_active = False
        
        # Close camera
        if hasattr(self, 'camera_cap') and self.camera_cap:
            self.camera_cap.release()
            print("INFO: Camera closed")
        
        # Close camera display window
        try:
            print("INFO: Camera display window closed")
        except Exception as e:
            print(f"WARNING: Error closing camera window: {e}")
        
        # Cleanup detection system
        if self.detection_system:
            self.detection_system.cleanup()
            self.detection_system = None
        
        # Reset camera to standby mode
        self.reset_camera_to_standby()
        
        # Reset uniform tracking
        self.reset_uniform_tracking()
        
        # Return main screen to standby
        if self.main_screen_window and self.main_screen_window.winfo_exists():
            self.show_standby_message()
        
        print("🛑 Detection system stopped - Camera closed and returned to standby")
    
    def add_activity_log(self, message):
        """Add message to activity log"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}\n"
            
            # Add to logs list
            self.activity_logs.append(log_entry)
            
            # Keep only the last max_logs entries
            if len(self.activity_logs) > self.max_logs:
                self.activity_logs = self.activity_logs[-self.max_logs:]
            
            # Update logs text widget if it exists
            if hasattr(self, 'logs_text') and self.logs_text and self.logs_text.winfo_exists():
                try:
                    self.logs_text.config(state=tk.NORMAL)
                    self.logs_text.insert(tk.END, log_entry)
                    self.logs_text.see(tk.END)
                    self.logs_text.config(state=tk.DISABLED)
                except Exception as e:
                    print(f"WARNING: Could not update logs text widget: {e}")
            
            print(f"📝 Activity Log: {message}")
            
        except Exception as e:
            print(f"ERROR: Error adding to activity log: {e}")
    
    def show_green_success_message(self, title, message):
        """Show a success message with green color"""
        try:
            # Create a custom messagebox window
            success_window = tk.Toplevel(self.root)
            success_window.title(title)
            success_window.geometry("400x150")
            success_window.configure(bg='#f0f9ff')
            success_window.resizable(False, False)
            
            # Ensure it's a child of the Guard UI window only
            success_window.transient(self.root)
            success_window.grab_set()
            
            # Center on the Guard UI window, not the entire screen
            self.root.update_idletasks()
            guard_x = self.root.winfo_x()
            guard_y = self.root.winfo_y()
            guard_width = self.root.winfo_width()
            guard_height = self.root.winfo_height()
            
            # Calculate center position within the Guard UI window
            x = guard_x + (guard_width // 2) - (400 // 2)
            y = guard_y + (guard_height // 2) - (150 // 2)
            success_window.geometry(f"400x150+{x}+{y}")
            
            # Ensure the window stays on top of Guard UI but not main screen
            success_window.lift(self.root)
            success_window.attributes('-topmost', True)
            
            # Main frame
            main_frame = tk.Frame(success_window, bg='#f0f9ff')
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            
            # Success icon (green checkmark)
            icon_label = tk.Label(
                main_frame,
                text="SUCCESS:",
                font=('Arial', 24),
                bg='#f0f9ff',
                fg='#10b981'
            )
            icon_label.pack(pady=(0, 10))
            
            # Title
            title_label = tk.Label(
                main_frame,
                text=title,
                font=('Arial', 16, 'bold'),
                bg='#f0f9ff',
                fg='#10b981'
            )
            title_label.pack(pady=(0, 5))
            
            # Message
            message_label = tk.Label(
                main_frame,
                text=message,
                font=('Arial', 12),
                bg='#f0f9ff',
                fg='#1f2937',
                wraplength=350,
                justify=tk.CENTER
            )
            message_label.pack(pady=(0, 15))
            
            # OK button
            ok_button = tk.Button(
                main_frame,
                text="OK",
                font=('Arial', 12, 'bold'),
                bg='#10b981',
                fg='white',
                relief='raised',
                bd=2,
                padx=20,
                pady=5,
                cursor='hand2',
                activebackground='#059669',
                activeforeground='white',
                command=success_window.destroy
            )
            ok_button.pack()
            
            # Auto-close after 3 seconds
            success_window.after(3000, success_window.destroy)
            
            # Focus on the window
            success_window.focus_set()
            
            # Ensure it doesn't interfere with main screen
            def cleanup_success_window():
                try:
                    if success_window.winfo_exists():
                        success_window.destroy()
                except:
                    pass
            
            # Store reference for cleanup
            if not hasattr(self, 'success_windows'):
                self.success_windows = []
            self.success_windows.append(success_window)
            
        except Exception as e:
            print(f"ERROR: Error showing green success message: {e}")
            # Fallback to regular messagebox
            messagebox.showinfo(title, message)
    
    def init_detection_system(self):
        """Initialize detection system"""
        try:
            self.current_model_path = "bsba_male.pt"
            self.detection_system = None
            self.detection_active = False
            self.detection_thread = None
            self.violation_count = 0
            self.compliant_count = 0
            self.total_detections = 0
            print("SUCCESS: Detection system initialized")
        except Exception as e:
            print(f"ERROR: Failed to initialize detection system: {e}")
    
    def quit_application(self):
        """Quit the application with proper cleanup"""
        try:
            if messagebox.askyesno("Quit", "Are you sure you want to quit?"):
                self.cleanup_resources()
                self.root.quit()
        except Exception as e:
            print(f"ERROR: Error during quit: {e}")
            self.root.quit()
    
    def cleanup_resources(self):
        """Clean up all resources before exit"""
        if self.cleanup_done:
            return
        
        try:
            print("INFO: Cleaning up resources...")
            
            # Stop detection if active
            if self.detection_active:
                self.stop_detection()
            
            # Cleanup detection system
            if self.detection_system:
                self.detection_system.cleanup()
                self.detection_system = None
            
            # Release camera
            if self.cap:
                self.cap.release()
                self.cap = None
            
            # Close main screen
            if self.main_screen_window and self.main_screen_window.winfo_exists():
                self.main_screen_window.destroy()
                self.main_screen_window = None
            
            # Close any success windows
            if hasattr(self, 'success_windows'):
                for window in self.success_windows:
                    try:
                        if window.winfo_exists():
                            window.destroy()
                    except:
                        pass
                self.success_windows = []
            
            self.cleanup_done = True
            print("SUCCESS: Resources cleaned up successfully")
            
        except Exception as e:
            print(f"WARNING: Error during cleanup: {e}")
    
    def run(self):
        """Start the guard control center"""
        try:
            # Set up proper exit handling
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            # Center the window
            self.center_window()
            
            # Update the window to ensure it's properly rendered
            self.root.update()
            
            # Start the main loop
            print("INFO: Starting main application loop...")
            self.root.mainloop()
            
        except Exception as e:
            print(f"ERROR: Error running application: {e}")
            traceback.print_exc()
    
    def on_closing(self):
        """Handle window closing event"""
        try:
            self.cleanup_resources()
            self.root.destroy()
        except Exception as e:
            print(f"ERROR: Error during window close: {e}")
            self.root.destroy()
    
    def close(self):
        """Close the guard control center (legacy method)"""
        self.cleanup_resources()
        self.root.destroy()

if __name__ == "__main__":
    import signal
    import sys
    
    def signal_handler(signum, frame):
        """Handle system signals gracefully"""
        print(f"\n🛑 Received signal {signum} - shutting down gracefully...")
        try:
            if 'app' in locals():
                app.cleanup_resources()
        except:
            pass
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        print("🚀 Starting AI-niform Guard System...")
        print("=" * 50)
        
        # Initialize the application
        app = GuardMainControl()
        
        # Add some startup delay to ensure everything is ready
        import time
        time.sleep(0.5)
        
        print("SUCCESS: Application initialized successfully")
        print("🖥️ Starting GUI...")
        
        # Run the application
        app.run()
        
    except KeyboardInterrupt:
        print("\n🛑 Application interrupted by user")
    except Exception as e:
        print(f"ERROR: Application error: {e}")
        traceback.print_exc()
        print("\n🔧 Please check the error above and try again")
    finally:
        try:
            if 'app' in locals():
                app.cleanup_resources()
        except:
            pass
        print("👋 Application closed")
