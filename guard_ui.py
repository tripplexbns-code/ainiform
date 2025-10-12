# guard_ui.py
# Guard Control Center - Login Interface and Main Control

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import time
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from dashboard import SecurityDashboard
import random

# Handle optional dependencies gracefully
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("⚠️ OpenCV not available - camera features will be disabled")

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("⚠️ YOLO not available - AI detection will use simulation mode")

class GuardMainControl:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🛡️ AI-niform - Guard Control Center")
        self.root.state('zoomed')  # Maximize window on Windows
        self.root.configure(bg='#ffffff')  # White background
        
        # Center the window
        self.center_window()
        
        # Firebase initialization
        self.db = None
        self.firebase_initialized = False
        self.init_firebase()
        
        # Guard authentication
        self.current_guard_id = None
        self.dashboard = None
        self.session_id = None
        
        # Valid guard IDs - will be loaded from Firebase
        self.valid_guard_ids = []
        self.guards_loaded = False
        
        # UI variables
        self.guard_id_var = tk.StringVar()
        self.login_status_var = tk.StringVar(value="Not Logged In")
        
        # Person ID tracking
        self.person_id_var = tk.StringVar()
        self.person_type_var = tk.StringVar(value="student")  # Default to student
        
        # Detection system
        self.detection_active = False
        self.detection_thread = None
        self.model = None
        self.cap = None
        
        # Detection results tracking
        self.violation_count = 0
        self.compliant_count = 0
        self.total_detections = 0
        
        # Real detection system attributes
        self.current_model_path = "tourism.pt"  # Default model
        self.conf_threshold = 0.5
        self.iou_threshold = 0.45
        self.frame_skip = 2  # Process every 2nd frame for speed
        self.prev_time = time.time()
        self.fps = 0
        
        # Tab control
        self.notebook = None
        self.login_tab = None
        self.dashboard_tab = None
        
        self.setup_ui()
        
        # Load guards from Firebase after UI setup
        self.load_guards_from_firebase()
        
    def init_firebase(self):
        """Initialize Firebase connection"""
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate("firebase_service_account.json")
                firebase_admin.initialize_app(cred)
            
            self.db = firestore.client()
            self.firebase_initialized = True
            print("✅ Firebase initialized successfully in Guard UI")
        except Exception as e:
            print(f"❌ Firebase initialization failed in Guard UI: {e}")
            self.firebase_initialized = False
    
    def load_guards_from_firebase(self):
        """Load valid guard IDs from Firebase guards collection"""
        if not self.firebase_initialized:
            print("❌ Firebase not initialized, using default guards")
            self.valid_guard_ids = ["GUARD001", "GUARD002", "GUARD003", "ADMIN", "SUPERVISOR"]
            self.guards_loaded = True
            return
        
        try:
            guards_ref = self.db.collection('guards')
            guards_docs = guards_ref.get()
            
            self.valid_guard_ids = []
            for doc in guards_docs:
                guard_data = doc.to_dict()
                guard_id = guard_data.get('guard_id', doc.id)
                self.valid_guard_ids.append(guard_id)
            
            if not self.valid_guard_ids:
                print("⚠️ No guards found in Firebase, using default guards")
                self.valid_guard_ids = ["GUARD001", "GUARD002", "GUARD003", "ADMIN", "SUPERVISOR"]
            
            self.guards_loaded = True
            print(f"✅ Loaded {len(self.valid_guard_ids)} guards from Firebase: {self.valid_guard_ids}")
            
        except Exception as e:
            print(f"❌ Failed to load guards from Firebase: {e}")
            print("Using default guards")
            self.valid_guard_ids = ["GUARD001", "GUARD002", "GUARD003", "ADMIN", "SUPERVISOR"]
            self.guards_loaded = True
        
    def center_window(self):
        """Center the window on screen (skip if maximized)"""
        # Skip centering if window is maximized
        if self.root.state() == 'zoomed':
            return
            
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def setup_ui(self):
        """Setup the tabbed guard control interface"""
        # Main container
        main_container = tk.Frame(self.root, bg='#ffffff')
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create login tab
        self.create_login_tab()
        
        # Initially hide dashboard tab (will be created after login)
        self.dashboard_tab = None
    
    def create_header(self, parent):
        """Create the header section"""
        header_frame = tk.Frame(parent, bg='#1e3a8a', height=100)  # Deep blue
        header_frame.pack(fill=tk.X, pady=(0, 20))
        header_frame.pack_propagate(False)
        
        # Title
        title_label = tk.Label(
            header_frame,
            text="🛡️ Security System",
            font=('Arial', 24, 'bold'),
            fg='white',
            bg='#1e3a8a'
        )
        title_label.pack(pady=20)
        
        # Subtitle
        subtitle_label = tk.Label(
            header_frame,
            text="Guard Control Center",
            font=('Arial', 14),
            fg='#bfdbfe',  # Light blue
            bg='#1e3a8a'
        )
        subtitle_label.pack()
    
    def create_login_tab(self):
        """Create the login tab"""
        # Create login tab frame
        self.login_tab = tk.Frame(self.notebook, bg='#ffffff')
        self.notebook.add(self.login_tab, text="🔐 Guard Login")
        
        # Header
        self.create_header(self.login_tab)
        
        # Login content
        self.create_login_content(self.login_tab)
        
        # Footer
        self.create_footer(self.login_tab)
        
    def create_login_tab(self):
        """Create the login tab"""
        # Create login tab frame
        self.login_tab = tk.Frame(self.notebook, bg='#ffffff')
        self.notebook.add(self.login_tab, text="🔐 Guard Login")
        
        # Header
        self.create_header(self.login_tab)
        
        # Login content
        self.create_login_content(self.login_tab)
        
        # Footer
        self.create_footer(self.login_tab)
    
    def create_login_content(self, parent):
        """Create the login content with proper layout and positioning"""
        # Main login container
        login_frame = tk.Frame(parent, bg='#f8fafc', relief='raised', bd=2)
        login_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Top section - Title
        title_frame = tk.Frame(login_frame, bg='#f8fafc')
        title_frame.pack(fill=tk.X, pady=(25, 20))
        
        # Login title - Centered
        login_title = tk.Label(
            title_frame,
            text="🔐 AI-niform Guard Authentication",
            font=('Arial', 20, 'bold'),
            fg='#1e3a8a',
            bg='#f8fafc'
        )
        login_title.pack()
        
        # Status section - Centered
        status_frame = tk.Frame(login_frame, bg='#f8fafc')
        status_frame.pack(fill=tk.X, pady=(0, 25))
        
        # Login status - Centered
        login_status_container = tk.Frame(status_frame, bg='#f8fafc')
        login_status_container.pack()
        
        tk.Label(
            login_status_container,
            text="Login Status:",
            font=('Arial', 12, 'bold'),
            fg='#1e3a8a',
            bg='#f8fafc'
        ).pack(side=tk.LEFT, padx=(0, 8))
        
        self.status_label = tk.Label(
            login_status_container,
            textvariable=self.login_status_var,
            font=('Arial', 12),
            fg='#dc2626',
            bg='#f8fafc'
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Firebase status - Below login status
        firebase_status_container = tk.Frame(status_frame, bg='#f8fafc')
        firebase_status_container.pack(pady=(8, 0))
        
        firebase_status = "✅ Firebase Connected" if self.firebase_initialized else "❌ Firebase Disconnected"
        firebase_status_color = '#059669' if self.firebase_initialized else '#dc2626'
        
        tk.Label(
            firebase_status_container,
            text="Firebase Status:",
            font=('Arial', 12, 'bold'),
            fg='#1e3a8a',
            bg='#f8fafc'
        ).pack(side=tk.LEFT, padx=(0, 8))
        
        self.firebase_status_label = tk.Label(
            firebase_status_container,
            text=firebase_status,
            font=('Arial', 12),
            fg=firebase_status_color,
            bg='#f8fafc'
        )
        self.firebase_status_label.pack(side=tk.LEFT)
        
        # Middle section - Login form
        form_section = tk.Frame(login_frame, bg='#f8fafc')
        form_section.pack(fill=tk.BOTH, expand=True, pady=(0, 25))
        
        # Manual ID input section - Centered
        manual_frame = tk.LabelFrame(
            form_section,
            text="Guard ID Entry",
            font=('Arial', 14, 'bold'),
            fg='#1e3a8a',
            bg='#f8fafc',
            relief='groove',
            bd=2
        )
        manual_frame.pack(expand=True, padx=40, pady=20)
        
        # Input form - Centered
        form_container = tk.Frame(manual_frame, bg='#f8fafc')
        form_container.pack(expand=True, padx=30, pady=30)
        
        # Guard ID label - Centered
        tk.Label(
            form_container,
            text="Enter Guard ID:",
            font=('Arial', 14, 'bold'),
            fg='#1e3a8a',
            bg='#f8fafc'
        ).pack(pady=(0, 12))
        
        # ID input field - Centered
        self.id_entry = tk.Entry(
            form_container,
            textvariable=self.guard_id_var,
            font=('Arial', 16),
            width=15,
            justify=tk.CENTER,
            relief='flat',
            bd=8,
            bg='white',
            fg='#1e3a8a'
        )
        self.id_entry.pack(pady=(0, 20))
        self.id_entry.bind('<Return>', lambda e: self.login_manual())
        
        # Login button - Centered
        self.manual_login_btn = tk.Button(
            form_container,
            text="🔑 LOGIN",
            command=self.login_manual,
            font=('Arial', 14, 'bold'),
            bg='#3b82f6',
            fg='white',
            relief='flat',
            padx=40,
            pady=12,
            cursor='hand2'
        )
        self.manual_login_btn.pack()
        
        # Bottom section - Action buttons
        bottom_section = tk.Frame(login_frame, bg='#f8fafc')
        bottom_section.pack(fill=tk.X, pady=(0, 15))
        
        # Quit button - Right aligned
        self.quit_btn = tk.Button(
            bottom_section,
            text="🚪 Quit System",
            command=self.quit_system,
            font=('Arial', 12, 'bold'),
            bg='#dc2626',
            fg='white',
            relief='flat',
            padx=25,
            pady=8,
            cursor='hand2'
        )
        self.quit_btn.pack(side=tk.RIGHT, padx=(0, 20))
    
    def create_footer(self, parent):
        """Create the footer section"""
        footer_frame = tk.Frame(parent, bg='#1e40af', height=60)  # Blue footer
        footer_frame.pack(fill=tk.X)
        footer_frame.pack_propagate(False)
        
        # System info
        info_text = "Security System v1.0 | Firebase Integration | YOLO Detection"
        info_label = tk.Label(
            footer_frame,
            text=info_text,
            font=('Arial', 10),
            fg='#bfdbfe',  # Light blue text
            bg='#1e40af'
        )
        info_label.pack(expand=True)
    
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
            self.guard_id_var.set("")
    
    
    
    def validate_guard_id(self, guard_id):
        """Validate guard ID"""
        # If guards not loaded yet, try to load them
        if not self.guards_loaded:
            self.load_guards_from_firebase()
        
        return guard_id in self.valid_guard_ids
    
    def authenticate_guard(self, guard_id):
        """Authenticate the guard"""
        self.current_guard_id = guard_id
        self.login_status_var.set("Logged In")
        self.status_label.config(fg='#059669')  # Green for logged in
        
        # Generate session ID
        self.session_id = f"{guard_id}_{int(time.time())}"
        
        # Log to Firebase
        self._log_guard_login(guard_id)
        
        # Enable/disable buttons
        self.manual_login_btn.config(state=tk.DISABLED)
        
        messagebox.showinfo("Success", f"Welcome, Guard {guard_id}!")
        
        # Automatically go to dashboard
        self.start_security_system()
    
    def _log_guard_login(self, guard_id):
        """Log guard login to Firebase"""
        if not self.firebase_initialized:
            return
        
        try:
            sessions_ref = self.db.collection('guard_sessions')
            sessions_ref.add({
                'guard_id': guard_id,
                'session_id': self.session_id,
                'login_time': datetime.now(),
                'status': 'active',
                'login_type': 'guard_ui',
                'ip_address': 'localhost'  # You can get real IP if needed
            })
            print(f"✅ Guard {guard_id} login logged to Firebase")
        except Exception as e:
            print(f"❌ Failed to log guard login: {e}")
    
    def _log_guard_logout(self, guard_id):
        """Log guard logout to Firebase"""
        if not self.firebase_initialized:
            return
        
        try:
            sessions_ref = self.db.collection('guard_sessions')
            # Update the current session
            sessions_query = sessions_ref.where('session_id', '==', self.session_id)
            sessions = sessions_query.get()
            
            for session in sessions:
                session.reference.update({
                    'logout_time': datetime.now(),
                    'status': 'completed'
                })
            
            print(f"✅ Guard {guard_id} logout logged to Firebase")
        except Exception as e:
            print(f"❌ Failed to log guard logout: {e}")
    
    def _log_system_event(self, event_type, details=None):
        """Log system events to Firebase"""
        if not self.firebase_initialized:
            return
        
        try:
            events_ref = self.db.collection('system_events')
            event_data = {
                'event_type': event_type,
                'timestamp': datetime.now(),
                'guard_id': self.current_guard_id,
                'session_id': self.session_id,
                'source': 'guard_ui'
            }
            
            if details:
                event_data['details'] = details
            
            events_ref.add(event_data)
            print(f"✅ System event '{event_type}' logged to Firebase")
        except Exception as e:
            print(f"❌ Failed to log system event: {e}")
    
    
    def start_security_system(self):
        """Start the security dashboard"""
        if not self.current_guard_id:
            messagebox.showerror("Error", "Please login first")
            return
        
        try:
            # Log system start event
            self._log_system_event("SECURITY_DASHBOARD_START", {
                "guard_id": self.current_guard_id,
                "session_id": self.session_id
            })
            
            # Create dashboard tab if it doesn't exist
            if self.dashboard_tab is None:
                self.create_dashboard_tab()
            
            # Switch to dashboard tab and hide login tab
            self.notebook.select(self.dashboard_tab)
            self.notebook.hide(self.login_tab)
            
            # Start dashboard monitoring
            self.start_dashboard_monitoring()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start security dashboard: {e}")
            self._log_system_event("SECURITY_DASHBOARD_ERROR", {"error": str(e)})
    
    def create_dashboard_tab(self):
        """Create the dashboard tab"""
        # Create dashboard tab frame
        self.dashboard_tab = tk.Frame(self.notebook, bg='#ffffff')
        self.notebook.add(self.dashboard_tab, text="📊 AI-niform Dashboard")
        
        # Create dashboard content
        self.create_dashboard_content(self.dashboard_tab)
    
    def create_dashboard_content(self, parent):
        """Create the dashboard content with camera, ID entry, logs, and detection results"""
        # Dashboard container with optimized padding
        dashboard_frame = tk.Frame(parent, bg='#f8fafc', relief='raised', bd=2)
        dashboard_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Top section - Header and Guard info
        header_section = tk.Frame(dashboard_frame, bg='#f8fafc')
        header_section.pack(fill=tk.X, pady=(0, 15))
        
        # Dashboard title - Centered and prominent
        dashboard_title = tk.Label(
            header_section,
            text="📊 AI-niform Dashboard",
            font=('Arial', 18, 'bold'),
            fg='#1e3a8a',
            bg='#f8fafc'
        )
        dashboard_title.pack(pady=(0, 10))
        
        # Guard info - Better organized
        guard_info_container = tk.Frame(header_section, bg='#f8fafc')
        guard_info_container.pack(fill=tk.X, pady=(0, 0))
        
        # Guard ID - Left side with better styling
        guard_id_frame = tk.Frame(guard_info_container, bg='#f8fafc')
        guard_id_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(
            guard_id_frame,
            text=f"🛡️ Guard: {self.current_guard_id}",
            font=('Arial', 12, 'bold'),
            fg='#1e3a8a',
            bg='#f8fafc'
        ).pack(anchor=tk.W)
        
        # Session ID - Right side with better styling
        session_frame = tk.Frame(guard_info_container, bg='#f8fafc')
        session_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        tk.Label(
            session_frame,
            text=f"🔑 Session: {self.session_id}",
            font=('Arial', 10),
            fg='#6b7280',
            bg='#f8fafc'
        ).pack(anchor=tk.E)
        
        # Main content - Left-Right split layout
        main_content = tk.Frame(dashboard_frame, bg='#f8fafc')
        main_content.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Configure left-right split with camera on left
        main_content.grid_columnconfigure(0, weight=1)  # Left column (camera - box shape)
        main_content.grid_columnconfigure(1, weight=1)  # Right column (functionality - equal space)
        
        # Left column - Camera Feed (bigger)
        left_camera_column = tk.Frame(main_content, bg='#f8fafc')
        left_camera_column.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        
        # Right column - All Other Functionality (smaller)
        right_functionality_column = tk.Frame(main_content, bg='#f8fafc')
        right_functionality_column.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        
        # Activity logs section - RIGHT SIDE (COMPACT)
        logs_frame = tk.LabelFrame(
            right_functionality_column,
            text="📋 Activity Logs",
            font=('Arial', 10, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        logs_frame.pack(fill=tk.X, pady=(0, 4))
        
        # Logs text widget with scrollbar - COMPACT
        logs_container = tk.Frame(logs_frame, bg='#ffffff')
        logs_container.pack(fill=tk.X, padx=4, pady=4)
        
        self.logs_text = tk.Text(
            logs_container,
            height=5,  # Compact height for better button visibility
            font=('Arial', 8),  # Smaller font
            bg='#f8fafc',
            fg='#1e3a8a',
            relief='sunken',
            bd=2,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.logs_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar for logs
        logs_scrollbar = tk.Scrollbar(logs_container)
        logs_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.logs_text.config(yscrollcommand=logs_scrollbar.set)
        logs_scrollbar.config(command=self.logs_text.yview)
        
        # Detection results section - RIGHT SIDE (COMPACT)
        detection_frame = tk.LabelFrame(
            right_functionality_column,
            text="🔍 Detection Results",
            font=('Arial', 10, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        detection_frame.pack(fill=tk.X, pady=(0, 4))
        
        # Detection results display - COMPACT
        self.detection_results = tk.Text(
            detection_frame,
            font=('Arial', 7),  # Smaller font
            bg='#f8fafc',
            fg='#1e3a8a',
            relief='sunken',
            bd=2,
            wrap=tk.WORD,
            state=tk.DISABLED,
            height=4  # Compact height for better button visibility
        )
        self.detection_results.pack(fill=tk.X, padx=4, pady=4)
        
        # Camera preview section - LEFT SIDE (BOX SHAPE)
        camera_frame = tk.LabelFrame(
            left_camera_column,
            text="📷 LIVE CAMERA FEED",
            font=('Arial', 14, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='groove',
            bd=3
        )
        camera_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0))
        
        # Camera placeholder - BOX SHAPE with expanded dimensions
        self.camera_label = tk.Label(
            camera_frame,
            text="📷 CAMERA FEED\n(STANDBY MODE)\n\nCamera will activate\nwhen student taps ID",
            font=('Arial', 16),
            fg='#6b7280',
            bg='#f3f4f6',
            relief='sunken',
            bd=4,
            width=80,  # Increased width for larger display
            height=30  # Increased height for larger display
        )
        self.camera_label.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)
        
        # Camera Control Section
        camera_control_frame = tk.Frame(camera_frame, bg='#ffffff')
        camera_control_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Start Camera Button
        self.start_camera_btn = tk.Button(
            camera_control_frame,
            text="📷 START CAMERA",
            command=self.start_camera_manual,
            font=('Arial', 12, 'bold'),
            bg='#059669',
            fg='white',
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2'
        )
        self.start_camera_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Stop Camera Button
        self.stop_camera_btn = tk.Button(
            camera_control_frame,
            text="⏹️ STOP CAMERA",
            command=self.stop_camera_manual,
            font=('Arial', 12, 'bold'),
            bg='#dc2626',
            fg='white',
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2',
            state=tk.DISABLED
        )
        self.stop_camera_btn.pack(side=tk.LEFT)
        
        # Special Actions Section - RIGHT SIDE
        self.create_special_actions_section(right_functionality_column)
        
        # Person ID Entry section - RIGHT SIDE
        self.create_person_entry_section(right_functionality_column)
        
        # Bottom section - Action buttons
        action_section = tk.Frame(dashboard_frame, bg='#f8fafc')
        action_section.pack(fill=tk.X, pady=(10, 10))
        
        # Logout button - Right aligned
        logout_btn = tk.Button(
            action_section,
            text="🚪 Logout",
            command=self.back_to_login,
            font=('Arial', 11, 'bold'),
            bg='#dc2626',
            fg='white',
            relief='flat',
            padx=20,
            pady=6,
            cursor='hand2'
        )
        logout_btn.pack(side=tk.RIGHT, padx=(0, 15))
    
    def create_special_actions_section(self, parent):
        """Create the special actions section with prominent buttons"""
        # Special Actions section - RIGHT SIDE (COMPACT)
        special_frame = tk.LabelFrame(
            parent,
            text="🚨 SPECIAL ACTIONS",
            font=('Arial', 10, 'bold'),
            fg='#dc2626',
            bg='#ffffff',
            relief='raised',
            bd=2
        )
        special_frame.pack(fill=tk.X, pady=(0, 4))
        
        # Special buttons container
        special_buttons_frame = tk.Frame(special_frame, bg='#ffffff')
        special_buttons_frame.pack(fill=tk.X, padx=6, pady=6)
        
        # Student forgot ID button - COMPACT
        self.forgot_id_btn = tk.Button(
            special_buttons_frame,
            text="❓ STUDENT FORGOT ID",
            command=self.handle_forgot_id,
            font=('Arial', 9, 'bold'),
            bg='#f59e0b',
            fg='white',
            relief='raised',
            bd=2,
            padx=8,
            pady=6,
            cursor='hand2'
        )
        self.forgot_id_btn.pack(fill=tk.X, pady=(0, 3))
        
        # Visitor button - COMPACT
        self.visitor_special_btn = tk.Button(
            special_buttons_frame,
            text="👤 VISITOR ENTRY",
            command=self.handle_visitor_entry,
            font=('Arial', 9, 'bold'),
            bg='#8b5cf6',
            fg='white',
            relief='raised',
            bd=2,
            padx=8,
            pady=6,
            cursor='hand2'
        )
        self.visitor_special_btn.pack(fill=tk.X, pady=(0, 0))
    
    def create_person_entry_section(self, parent):
        """Create the person ID entry section with manual typing and tapping"""
        # Person ID Entry section - RIGHT SIDE (COMPACT)
        entry_frame = tk.LabelFrame(
            parent,
            text="👥 Person ID Entry",
            font=('Arial', 10, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        entry_frame.pack(fill=tk.X, pady=(0, 4))
        
        # Person type selection - COMPACT
        type_frame = tk.Frame(entry_frame, bg='#ffffff')
        type_frame.pack(fill=tk.X, padx=6, pady=(6, 3))
        
        tk.Label(
            type_frame,
            text="Person Type:",
            font=('Arial', 9, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        ).pack(anchor=tk.W, pady=(0, 3))
        
        # Person type buttons - COMPACT
        type_buttons_frame = tk.Frame(type_frame, bg='#ffffff')
        type_buttons_frame.pack(fill=tk.X)
        
        self.student_btn = tk.Button(
            type_buttons_frame,
            text="👨‍🎓 Student",
            command=lambda: self.set_person_type("student"),
            font=('Arial', 8, 'bold'),
            bg='#3b82f6',
            fg='white',
            relief='flat',
            padx=6,
            pady=3,
            cursor='hand2'
        )
        self.student_btn.pack(side=tk.LEFT, padx=(0, 1), fill=tk.X, expand=True)
        
        self.teacher_btn = tk.Button(
            type_buttons_frame,
            text="👨‍🏫 Teacher",
            command=lambda: self.set_person_type("teacher"),
            font=('Arial', 8, 'bold'),
            bg='#6b7280',
            fg='white',
            relief='flat',
            padx=6,
            pady=3,
            cursor='hand2'
        )
        self.teacher_btn.pack(side=tk.LEFT, padx=1, fill=tk.X, expand=True)
        
        self.visitor_btn = tk.Button(
            type_buttons_frame,
            text="👤 Visitor",
            command=lambda: self.set_person_type("visitor"),
            font=('Arial', 8, 'bold'),
            bg='#6b7280',
            fg='white',
            relief='flat',
            padx=6,
            pady=3,
            cursor='hand2'
        )
        self.visitor_btn.pack(side=tk.LEFT, padx=(1, 0), fill=tk.X, expand=True)
        
        # Manual ID input - COMPACT
        input_frame = tk.Frame(entry_frame, bg='#ffffff')
        input_frame.pack(fill=tk.X, padx=6, pady=(3, 6))
        
        tk.Label(
            input_frame,
            text="Person ID:",
            font=('Arial', 9, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        ).pack(anchor=tk.W, pady=(0, 3))
        
        self.person_id_entry = tk.Entry(
            input_frame,
            textvariable=self.person_id_var,
            font=('Arial', 9),
            width=15,
            justify=tk.CENTER,
            relief='flat',
            bd=2,
            bg='white',
            fg='#1e3a8a'
        )
        self.person_id_entry.pack(fill=tk.X, pady=(0, 4))
        self.person_id_entry.bind('<Return>', lambda e: self.log_person_entry())
        
        # Manual entry button - COMPACT
        self.manual_entry_btn = tk.Button(
            input_frame,
            text="✅ Log Entry",
            command=self.log_person_entry,
            font=('Arial', 9, 'bold'),
            bg='#059669',
            fg='white',
            relief='flat',
            padx=8,
            pady=4,
            cursor='hand2'
        )
        self.manual_entry_btn.pack(fill=tk.X, pady=(0, 0))
    
    def set_person_type(self, person_type):
        """Set the selected person type"""
        self.person_type_var.set(person_type)
        
        # Update button colors
        buttons = {
            "student": self.student_btn,
            "teacher": self.teacher_btn,
            "visitor": self.visitor_btn
        }
        
        for ptype, btn in buttons.items():
            if ptype == person_type:
                btn.config(bg='#3b82f6')  # Blue for selected
            else:
                btn.config(bg='#6b7280')  # Gray for unselected
        
        # Switch detection model based on person type
        self.switch_detection_model(person_type)
    
    def switch_detection_model(self, person_type):
        """Switch detection model based on person type"""
        if person_type == "student":
            # For students, we could switch between ICT and Tourism models
            # For now, keep using tourism.pt as default
            new_model = "tourism.pt"
        else:
            # For teachers and visitors, use tourism model
            new_model = "tourism.pt"
        
        if new_model != self.current_model_path:
            self.current_model_path = new_model
            print(f"🔄 Switched to model: {new_model}")
            
            # Restart detection with new model if active
            if self.detection_active:
                self.stop_detection()
                time.sleep(1)  # Brief pause
                self.start_real_detection()
    
    def stop_detection(self):
        """Stop the detection system"""
        self.detection_active = False
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=2)
        if self.cap:
            self.cap.release()
            self.cap = None
        
        # Update camera label to show standby status
        self.camera_label.config(
            text="📷 Camera Feed\n(Standby Mode)\n\nCamera will activate\nwhen student taps ID",
            fg='#6b7280',
            image=""  # Clear any image
        )
        self.camera_label.image = None  # Clear image reference
        
        # Update button states
        self.start_camera_btn.config(state=tk.NORMAL)
        self.stop_camera_btn.config(state=tk.DISABLED)
        
        print("🛑 Detection system stopped - Camera returned to standby")
    
    def start_camera_manual(self):
        """Manually start camera for testing"""
        try:
            if not CV2_AVAILABLE:
                messagebox.showwarning("Camera Unavailable", "OpenCV is not installed. Camera features are disabled.")
                return
            
            # Try to start camera
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                messagebox.showerror("Camera Error", "Could not open camera. Please check:\n- Camera is connected\n- No other application is using the camera\n- Camera permissions are granted")
                return
            
            # Configure camera settings for better quality
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            # Update UI
            self.camera_label.config(
                text="📷 CAMERA FEED\n(ACTIVE)\n\nLIVE VIDEO STREAM\nManual Mode",
                fg='#059669',
                font=('Arial', 14)
            )
            
            # Update button states
            self.start_camera_btn.config(state=tk.DISABLED)
            self.stop_camera_btn.config(state=tk.NORMAL)
            
            # Start camera preview thread
            self.detection_active = True
            self.camera_thread = threading.Thread(target=self._camera_preview_loop, daemon=True)
            self.camera_thread.start()
            
            messagebox.showinfo("Camera Started", "Camera is now active! You should see the live feed.")
            
        except Exception as e:
            messagebox.showerror("Camera Error", f"Failed to start camera: {e}")
            print(f"❌ Camera start error: {e}")
    
    def stop_camera_manual(self):
        """Manually stop camera"""
        try:
            self.detection_active = False
            
            if self.cap:
                self.cap.release()
                self.cap = None
            
            # Update UI
            self.camera_label.config(
                text="📷 Camera Feed\n(Standby Mode)\n\nCamera will activate\nwhen student taps ID",
                fg='#6b7280',
                image="",
                font=('Arial', 16)
            )
            self.camera_label.image = None
            
            # Update button states
            self.start_camera_btn.config(state=tk.NORMAL)
            self.stop_camera_btn.config(state=tk.DISABLED)
            
            messagebox.showinfo("Camera Stopped", "Camera has been stopped.")
            
        except Exception as e:
            messagebox.showerror("Camera Error", f"Failed to stop camera: {e}")
            print(f"❌ Camera stop error: {e}")
    
    def _camera_preview_loop(self):
        """Camera preview loop for manual camera mode"""
        while self.detection_active and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                continue
            
            try:
                # Update camera preview
                self.root.after(0, self._update_camera_preview, frame)
                time.sleep(0.033)  # ~30 FPS
            except Exception as e:
                print(f"❌ Camera preview error: {e}")
                break
        
        print("🛑 Camera preview loop stopped")
    
    def start_student_detection(self, student_id, student_name):
        """Start camera detection specifically for a student"""
        try:
            # Show detection window
            self.show_detection_window(student_id, student_name)
            
            # Load appropriate model based on student course (simulate course detection)
            course = self.get_student_course(student_id)
            model_path = "ict.pt" if course == "ICT" else "tourism.pt"
            
            if model_path != self.current_model_path:
                self.current_model_path = model_path
                print(f"🔄 Switched to {course} model: {model_path}")
                # Reload model if different
                self.model = YOLO(model_path)
            
            # Start camera and real detection
            self.start_real_detection()
            
            # Log student detection start
            self._log_activity_to_firebase('student_detection_started', {
                'student_id': student_id,
                'student_name': student_name,
                'course': course,
                'model_used': model_path,
                'camera_status': 'active'
            })
            
        except Exception as e:
            print(f"❌ Failed to start student detection: {e}")
            messagebox.showerror("Detection Error", f"Failed to start camera detection: {e}")
    
    def get_student_course(self, student_id):
        """Get student course based on ID (simulated)"""
        # Simulate course detection based on student ID
        if "ICT" in student_id.upper() or student_id.startswith("ICT"):
            return "ICT"
        elif "TOUR" in student_id.upper() or student_id.startswith("TOUR"):
            return "TOURISM"
        else:
            # Default to Tourism for demo
            return "TOURISM"
    
    def show_detection_window(self, student_id, student_name):
        """Show a popup window for student detection"""
        detection_window = tk.Toplevel(self.root)
        detection_window.title(f"🎥 Camera Detection - {student_name}")
        detection_window.geometry("600x400")
        detection_window.configure(bg='#f8fafc')
        
        # Center the window
        detection_window.transient(self.root)
        detection_window.grab_set()
        
        # Header
        header_frame = tk.Frame(detection_window, bg='#1e3a8a', height=60)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        header_frame.pack_propagate(False)
        
        tk.Label(
            header_frame,
            text=f"🎥 UNIFORM DETECTION",
            font=('Arial', 16, 'bold'),
            fg='white',
            bg='#1e3a8a'
        ).pack(expand=True)
        
        tk.Label(
            header_frame,
            text=f"Student: {student_name} (ID: {student_id})",
            font=('Arial', 12),
            fg='#e5e7eb',
            bg='#1e3a8a'
        ).pack()
        
        # Camera preview area
        camera_frame = tk.Frame(detection_window, bg='#ffffff', relief='sunken', bd=2)
        camera_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Camera label (placeholder for now)
        self.detection_camera_label = tk.Label(
            camera_frame,
            text="📷 Camera Starting...\n\nPosition yourself in front of the camera\nfor uniform detection",
            font=('Arial', 14),
            fg='#6b7280',
            bg='#f3f4f6',
            relief='sunken',
            bd=2
        )
        self.detection_camera_label.pack(expand=True, padx=20, pady=20)
        
        # Status and controls
        control_frame = tk.Frame(detection_window, bg='#f8fafc')
        control_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Status label
        self.detection_status_label = tk.Label(
            control_frame,
            text="🔄 Initializing detection system...",
            font=('Arial', 12, 'bold'),
            fg='#1e3a8a',
            bg='#f8fafc'
        )
        self.detection_status_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # Close button
        close_btn = tk.Button(
            control_frame,
            text="❌ Close Detection",
            command=detection_window.destroy,
            font=('Arial', 10, 'bold'),
            bg='#dc2626',
            fg='white',
            relief='flat',
            padx=15,
            pady=5,
            cursor='hand2'
        )
        close_btn.pack(side=tk.RIGHT)
        
        # Auto-close after 30 seconds
        detection_window.after(30000, detection_window.destroy)
        
        # Update status after a short delay
        detection_window.after(2000, lambda: self.update_detection_status("✅ Detection system active - Analyzing uniform..."))
        detection_window.after(5000, lambda: self.update_detection_status("🔍 Detection complete - Results logged"))
    
    def update_detection_status(self, status):
        """Update detection status in the popup window"""
        if hasattr(self, 'detection_status_label'):
            self.detection_status_label.config(text=status)
    
    def show_visitor_entry_tab(self):
        """Show visitor entry tab with detailed information form"""
        # Create visitor entry window
        visitor_window = tk.Toplevel(self.root)
        visitor_window.title("👤 Visitor Entry - AI-niform Security System")
        visitor_window.geometry("800x600")
        visitor_window.configure(bg='#f8fafc')
        
        # Center the window
        visitor_window.transient(self.root)
        visitor_window.grab_set()
        
        # Header
        header_frame = tk.Frame(visitor_window, bg='#1e3a8a', height=80)
        header_frame.pack(fill=tk.X, padx=15, pady=15)
        header_frame.pack_propagate(False)
        
        tk.Label(
            header_frame,
            text="👤 VISITOR ENTRY FORM",
            font=('Arial', 18, 'bold'),
            fg='white',
            bg='#1e3a8a'
        ).pack(expand=True)
        
        tk.Label(
            header_frame,
            text="Please fill in all required information",
            font=('Arial', 12),
            fg='#e5e7eb',
            bg='#1e3a8a'
        ).pack()
        
        # Main form container
        form_frame = tk.Frame(visitor_window, bg='#f8fafc')
        form_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # Personal Information Section
        personal_section = tk.LabelFrame(
            form_frame,
            text="📋 Personal Information",
            font=('Arial', 14, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        personal_section.pack(fill=tk.X, pady=(0, 15))
        
        # Personal info fields
        personal_fields = tk.Frame(personal_section, bg='#ffffff')
        personal_fields.pack(fill=tk.X, padx=15, pady=15)
        
        # Full Name
        tk.Label(
            personal_fields,
            text="Full Name *",
            font=('Arial', 12, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        ).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        visitor_name_entry = tk.Entry(
            personal_fields,
            font=('Arial', 12),
            width=30,
            relief='flat',
            bd=3,
            bg='white',
            fg='#1e3a8a'
        )
        visitor_name_entry.grid(row=0, column=1, sticky=tk.W, pady=(0, 5), padx=(10, 0))
        
        # Phone Number
        tk.Label(
            personal_fields,
            text="Phone Number *",
            font=('Arial', 12, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        ).grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        visitor_phone_entry = tk.Entry(
            personal_fields,
            font=('Arial', 12),
            width=30,
            relief='flat',
            bd=3,
            bg='white',
            fg='#1e3a8a'
        )
        visitor_phone_entry.grid(row=1, column=1, sticky=tk.W, pady=(0, 5), padx=(10, 0))
        
        # ID Type
        tk.Label(
            personal_fields,
            text="ID Type *",
            font=('Arial', 12, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        ).grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        
        id_type_var = tk.StringVar(value="National ID")
        id_type_combo = ttk.Combobox(
            personal_fields,
            textvariable=id_type_var,
            font=('Arial', 12),
            width=27,
            state='readonly',
            values=["National ID", "Driver's License", "Passport", "Company ID", "Student ID", "Other"]
        )
        id_type_combo.grid(row=2, column=1, sticky=tk.W, pady=(0, 5), padx=(10, 0))
        
        # ID Number
        tk.Label(
            personal_fields,
            text="ID Number *",
            font=('Arial', 12, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        ).grid(row=3, column=0, sticky=tk.W, pady=(0, 5))
        
        visitor_id_entry = tk.Entry(
            personal_fields,
            font=('Arial', 12),
            width=30,
            relief='flat',
            bd=3,
            bg='white',
            fg='#1e3a8a'
        )
        visitor_id_entry.grid(row=3, column=1, sticky=tk.W, pady=(0, 5), padx=(10, 0))
        
        # Visit Information Section
        visit_section = tk.LabelFrame(
            form_frame,
            text="🏢 Visit Information",
            font=('Arial', 14, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        visit_section.pack(fill=tk.X, pady=(0, 15))
        
        # Visit info fields
        visit_fields = tk.Frame(visit_section, bg='#ffffff')
        visit_fields.pack(fill=tk.X, padx=15, pady=15)
        
        # Purpose of Visit
        tk.Label(
            visit_fields,
            text="Purpose of Visit *",
            font=('Arial', 12, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        ).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        purpose_var = tk.StringVar(value="Meeting")
        purpose_combo = ttk.Combobox(
            visit_fields,
            textvariable=purpose_var,
            font=('Arial', 12),
            width=27,
            state='readonly',
            values=["Meeting", "Interview", "Delivery", "Maintenance", "Official Business", "Other"]
        )
        purpose_combo.grid(row=0, column=1, sticky=tk.W, pady=(0, 5), padx=(10, 0))
        
        # Department/Person to Visit
        tk.Label(
            visit_fields,
            text="Person/Dept to Visit *",
            font=('Arial', 12, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        ).grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        person_to_visit_entry = tk.Entry(
            visit_fields,
            font=('Arial', 12),
            width=30,
            relief='flat',
            bd=3,
            bg='white',
            fg='#1e3a8a'
        )
        person_to_visit_entry.grid(row=1, column=1, sticky=tk.W, pady=(0, 5), padx=(10, 0))
        
        
        # RFID Assignment Section
        rfid_section = tk.LabelFrame(
            form_frame,
            text="📡 RFID Card Assignment",
            font=('Arial', 14, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        rfid_section.pack(fill=tk.X, pady=(0, 15))
        
        # RFID info fields
        rfid_fields = tk.Frame(rfid_section, bg='#ffffff')
        rfid_fields.pack(fill=tk.X, padx=15, pady=15)
        
        # RFID Card Number
        tk.Label(
            rfid_fields,
            text="RFID Card Number:",
            font=('Arial', 12, 'bold'),
            fg='#1e3a8a',
            bg='#ffffff'
        ).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        rfid_card_entry = tk.Entry(
            rfid_fields,
            font=('Arial', 12),
            width=30,
            relief='flat',
            bd=3,
            bg='white',
            fg='#1e3a8a'
        )
        rfid_card_entry.grid(row=0, column=1, sticky=tk.W, pady=(0, 5), padx=(10, 0))
        
        # Assign RFID button
        assign_rfid_btn = tk.Button(
            rfid_fields,
            text="📡 Assign RFID Card",
            command=lambda: self.assign_rfid_card(rfid_card_entry, visitor_name_entry.get()),
            font=('Arial', 11, 'bold'),
            bg='#8b5cf6',
            fg='white',
            relief='flat',
            padx=15,
            pady=5,
            cursor='hand2'
        )
        assign_rfid_btn.grid(row=0, column=2, sticky=tk.W, pady=(0, 5), padx=(10, 0))
        
        # RFID Status
        rfid_status_label = tk.Label(
            rfid_fields,
            text="Status: No RFID assigned",
            font=('Arial', 11),
            fg='#dc2626',
            bg='#ffffff'
        )
        rfid_status_label.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
        
        # Action Buttons
        button_frame = tk.Frame(visitor_window, bg='#f8fafc')
        button_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        # Time Entry buttons
        time_frame = tk.Frame(button_frame, bg='#f8fafc')
        time_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(
            time_frame,
            text="Time Entry:",
            font=('Arial', 12, 'bold'),
            fg='#1e3a8a',
            bg='#f8fafc'
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        time_in_btn = tk.Button(
            time_frame,
            text="🕐 TIME IN",
            command=lambda: self.process_visitor_entry(
                visitor_window, visitor_name_entry.get(), visitor_phone_entry.get(),
                id_type_var.get(), visitor_id_entry.get(), purpose_var.get(),
                person_to_visit_entry.get(), rfid_card_entry.get(), "in"
            ),
            font=('Arial', 12, 'bold'),
            bg='#059669',
            fg='white',
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2'
        )
        time_in_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        time_out_btn = tk.Button(
            time_frame,
            text="🕐 TIME OUT",
            command=lambda: self.process_visitor_entry(
                visitor_window, visitor_name_entry.get(), visitor_phone_entry.get(),
                id_type_var.get(), visitor_id_entry.get(), purpose_var.get(),
                person_to_visit_entry.get(), rfid_card_entry.get(), "out"
            ),
            font=('Arial', 12, 'bold'),
            bg='#dc2626',
            fg='white',
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2'
        )
        time_out_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Close button
        close_btn = tk.Button(
            button_frame,
            text="❌ Close",
            command=visitor_window.destroy,
            font=('Arial', 12, 'bold'),
            bg='#6b7280',
            fg='white',
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2'
        )
        close_btn.pack(side=tk.RIGHT)
        
        # Focus on first field
        visitor_name_entry.focus()
    
    def assign_rfid_card(self, rfid_entry, visitor_name):
        """Assign RFID card to visitor"""
        rfid_number = rfid_entry.get().strip()
        
        if not rfid_number:
            messagebox.showerror("Error", "Please enter RFID card number")
            return
        
        if not visitor_name:
            messagebox.showerror("Error", "Please enter visitor name first")
            return
        
        # Generate RFID card ID
        rfid_id = f"RFID_{rfid_number}_{datetime.now().strftime('%H%M%S')}"
        
        # Log RFID assignment
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] RFID ASSIGNED - Visitor: {visitor_name} (RFID: {rfid_number})\n"
        
        self.logs_text.config(state=tk.NORMAL)
        self.logs_text.insert(tk.END, log_entry)
        self.logs_text.config(state=tk.DISABLED)
        self.logs_text.see(tk.END)
        
        # Log to Firebase
        self._log_rfid_assignment_to_firebase(visitor_name, rfid_number, rfid_id)
        
        # Update status
        messagebox.showinfo("Success", f"RFID Card {rfid_number} assigned to {visitor_name}")
        
        # Update status label (if we had access to it)
        print(f"✅ RFID Card {rfid_number} assigned to visitor {visitor_name}")
    
    def process_visitor_entry(self, window, name, phone, id_type, id_num, purpose, person_to_visit, rfid_card, action_type):
        """Process visitor entry with all information"""
        # Validate required fields
        if not name or not phone or not id_type or not id_num or not purpose or not person_to_visit:
            messagebox.showerror("Validation Error", "Please fill in all required fields (*)")
            return
        
        # Check if RFID card is assigned for TIME IN
        if action_type == "in" and not rfid_card:
            messagebox.showwarning("RFID Required", "Please assign an RFID card before TIME IN")
            return
        
        # Generate visitor ID
        visitor_id = f"VIS_{datetime.now().strftime('%H%M%S')}"
        
        # Add to activity logs
        timestamp = datetime.now().strftime("%H:%M:%S")
        action_text = "TIME IN" if action_type == "in" else "TIME OUT"
        log_entry = f"[{timestamp}] {action_text} - VISITOR: {name} (ID: {visitor_id})\n"
        log_entry += f"    Purpose: {purpose} | Visiting: {person_to_visit} | ID Type: {id_type}\n"
        
        if rfid_card:
            log_entry += f"    RFID Card: {rfid_card} | Temporary Access Granted\n"
        
        self.logs_text.config(state=tk.NORMAL)
        self.logs_text.insert(tk.END, log_entry)
        self.logs_text.config(state=tk.DISABLED)
        self.logs_text.see(tk.END)
        
        # Log detailed visitor information to Firebase
        self._log_visitor_entry_to_firebase(
            visitor_id, name, phone, id_type, id_num, purpose, 
            person_to_visit, rfid_card, action_type
        )
        
        # Close the visitor window
        window.destroy()
        
        action_text = "Time IN" if action_type == "in" else "Time OUT"
        if rfid_card:
            messagebox.showinfo("Success", f"Visitor {name} - {action_text} logged successfully!\nRFID Card {rfid_card} active for temporary access.")
        else:
            messagebox.showinfo("Success", f"Visitor {name} - {action_text} logged successfully!")
    
    def _log_visitor_entry_to_firebase(self, visitor_id, name, phone, id_type, id_num, purpose, person_to_visit, rfid_card, action_type):
        """Log detailed visitor entry to Firebase"""
        if not self.firebase_initialized:
            return
        
        try:
            visitors_ref = self.db.collection('visitor_entries')
            visitors_ref.add({
                'visitor_id': visitor_id,
                'name': name,
                'phone': phone,
                'id_type': id_type,
                'id_number': id_num,
                'purpose': purpose,
                'person_to_visit': person_to_visit,
                'rfid_card': rfid_card,
                'rfid_active': bool(rfid_card),
                'action': action_type,
                'timestamp': datetime.now(),
                'date': datetime.now().strftime("%Y-%m-%d"),
                'time': datetime.now().strftime("%H:%M:%S"),
                'guard_id': self.current_guard_id,
                'session_id': self.session_id
            })
            print(f"✅ Visitor entry logged to Firebase: {name} ({visitor_id})")
        except Exception as e:
            print(f"❌ Failed to log visitor entry: {e}")
    
    def _log_rfid_assignment_to_firebase(self, visitor_name, rfid_number, rfid_id):
        """Log RFID card assignment to Firebase"""
        if not self.firebase_initialized:
            return
        
        try:
            rfid_ref = self.db.collection('rfid_assignments')
            rfid_ref.add({
                'rfid_id': rfid_id,
                'rfid_number': rfid_number,
                'visitor_name': visitor_name,
                'assigned_at': datetime.now(),
                'date': datetime.now().strftime("%Y-%m-%d"),
                'time': datetime.now().strftime("%H:%M:%S"),
                'status': 'active',
                'guard_id': self.current_guard_id,
                'session_id': self.session_id
            })
            print(f"✅ RFID assignment logged to Firebase: {visitor_name} -> {rfid_number}")
        except Exception as e:
            print(f"❌ Failed to log RFID assignment: {e}")
    
    def _log_student_rfid_assignment_to_firebase(self, student_id, rfid_number, rfid_id):
        """Log student RFID card assignment to Firebase"""
        if not self.firebase_initialized:
            return
        
        try:
            rfid_ref = self.db.collection('student_rfid_assignments')
            rfid_ref.add({
                'rfid_id': rfid_id,
                'rfid_number': rfid_number,
                'student_id': student_id,
                'student_name': self.verified_student['name'],
                'course': self.verified_student['course'],
                'assigned_at': datetime.now(),
                'date': datetime.now().strftime("%Y-%m-%d"),
                'time': datetime.now().strftime("%H:%M:%S"),
                'status': 'active',
                'type': 'forgot_id_temporary',
                'guard_id': self.current_guard_id,
                'session_id': self.session_id
            })
            print(f"✅ Student RFID assignment logged to Firebase: {self.verified_student['name']} -> {rfid_number}")
        except Exception as e:
            print(f"❌ Failed to log student RFID assignment: {e}")
    
    def _log_forgot_id_entry_to_firebase(self, temp_id, student_name, original_id, course, rfid_card, action_type):
        """Log forgot ID student entry to Firebase"""
        if not self.firebase_initialized:
            return
        
        try:
            forgot_ref = self.db.collection('forgot_id_entries')
            forgot_ref.add({
                'temp_id': temp_id,
                'student_name': student_name,
                'original_student_id': original_id,
                'course': course,
                'rfid_card': rfid_card,
                'rfid_active': bool(rfid_card),
                'action': action_type,
                'timestamp': datetime.now(),
                'date': datetime.now().strftime("%Y-%m-%d"),
                'time': datetime.now().strftime("%H:%M:%S"),
                'guard_id': self.current_guard_id,
                'session_id': self.session_id
            })
            print(f"✅ Forgot ID entry logged to Firebase: {student_name} ({temp_id})")
        except Exception as e:
            print(f"❌ Failed to log forgot ID entry: {e}")
    
    
    def log_person_entry(self):
        """Log person time in/out entry"""
        person_id = self.person_id_var.get().strip()
        person_type = self.person_type_var.get()
        
        if not person_id:
            messagebox.showerror("Error", "Please enter a Person ID")
            return
        
        # Get person name (simulate lookup)
        person_name = self.get_person_name(person_id, person_type)
        
        # Ask for time in or time out
        action = messagebox.askyesno("Time Entry", f"Time IN for {person_name} (ID: {person_id})?\n\nClick YES for Time IN\nClick NO for Time OUT")
        action_type = "in" if action else "out"
        
        # Add to activity logs
        self.add_time_entry(person_type, person_id, person_name, action_type)
        
        # Log to Firebase
        self._log_time_entry_to_firebase(person_type, person_id, person_name, action_type)
        
        # Clear input
        self.person_id_var.set("")
        
        # If student and time IN, start camera detection
        if person_type == "student" and action_type == "in":
            self.start_student_detection(person_id, person_name)
        
        action_text = "Time IN" if action_type == "in" else "Time OUT"
        messagebox.showinfo("Success", f"{person_name} ({person_id}) - {action_text} logged successfully!")
    
    def handle_forgot_id(self):
        """Handle student who forgot their ID"""
        # Show student ID verification tab
        self.show_student_forgot_id_tab()
    
    def show_student_forgot_id_tab(self):
        """Show student forgot ID verification tab"""
        # Create student forgot ID window
        forgot_window = tk.Toplevel(self.root)
        forgot_window.title("❓ Student Forgot ID - AI-niform Security System")
        forgot_window.geometry("700x500")
        forgot_window.configure(bg='#f8fafc')
        
        # Center the window
        forgot_window.transient(self.root)
        forgot_window.grab_set()
        
        # Header
        header_frame = tk.Frame(forgot_window, bg='#dc2626', height=80)
        header_frame.pack(fill=tk.X, padx=15, pady=15)
        header_frame.pack_propagate(False)
        
        tk.Label(
            header_frame,
            text="❓ STUDENT FORGOT ID",
            font=('Arial', 18, 'bold'),
            fg='white',
            bg='#dc2626'
        ).pack(expand=True)
        
        tk.Label(
            header_frame,
            text="Verify student ID and assign temporary RFID access",
            font=('Arial', 12),
            fg='#fecaca',
            bg='#dc2626'
        ).pack()
        
        # Main form container
        form_frame = tk.Frame(forgot_window, bg='#f8fafc')
        form_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # Student ID Verification Section
        verification_section = tk.LabelFrame(
            form_frame,
            text="🔍 Student ID Verification",
            font=('Arial', 14, 'bold'),
            fg='#dc2626',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        verification_section.pack(fill=tk.X, pady=(0, 15))
        
        # Verification fields
        verification_fields = tk.Frame(verification_section, bg='#ffffff')
        verification_fields.pack(fill=tk.X, padx=15, pady=15)
        
        # Student ID Entry
        tk.Label(
            verification_fields,
            text="Student ID Number *",
            font=('Arial', 12, 'bold'),
            fg='#dc2626',
            bg='#ffffff'
        ).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        student_id_entry = tk.Entry(
            verification_fields,
            font=('Arial', 12),
            width=30,
            relief='flat',
            bd=3,
            bg='white',
            fg='#dc2626'
        )
        student_id_entry.grid(row=0, column=1, sticky=tk.W, pady=(0, 5), padx=(10, 0))
        
        # Verify Student button
        verify_btn = tk.Button(
            verification_fields,
            text="🔍 Verify Student",
            command=lambda: self.verify_student_id(student_id_entry.get(), verification_fields),
            font=('Arial', 11, 'bold'),
            bg='#dc2626',
            fg='white',
            relief='flat',
            padx=15,
            pady=5,
            cursor='hand2'
        )
        verify_btn.grid(row=0, column=2, sticky=tk.W, pady=(0, 5), padx=(10, 0))
        
        # Student Info Display
        self.student_info_label = tk.Label(
            verification_fields,
            text="Status: No student verified",
            font=('Arial', 11),
            fg='#dc2626',
            bg='#ffffff'
        )
        self.student_info_label.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
        
        # RFID Assignment Section
        rfid_section = tk.LabelFrame(
            form_frame,
            text="📡 Temporary RFID Assignment",
            font=('Arial', 14, 'bold'),
            fg='#dc2626',
            bg='#ffffff',
            relief='groove',
            bd=2
        )
        rfid_section.pack(fill=tk.X, pady=(0, 15))
        
        # RFID fields
        rfid_fields = tk.Frame(rfid_section, bg='#ffffff')
        rfid_fields.pack(fill=tk.X, padx=15, pady=15)
        
        # RFID Card Number
        tk.Label(
            rfid_fields,
            text="Empty RFID Card Number:",
            font=('Arial', 12, 'bold'),
            fg='#dc2626',
            bg='#ffffff'
        ).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        rfid_card_entry = tk.Entry(
            rfid_fields,
            font=('Arial', 12),
            width=30,
            relief='flat',
            bd=3,
            bg='white',
            fg='#dc2626'
        )
        rfid_card_entry.grid(row=0, column=1, sticky=tk.W, pady=(0, 5), padx=(10, 0))
        
        # Assign RFID button
        assign_rfid_btn = tk.Button(
            rfid_fields,
            text="📡 Link RFID to Student",
            command=lambda: self.assign_rfid_to_student(student_id_entry.get(), rfid_card_entry.get()),
            font=('Arial', 11, 'bold'),
            bg='#8b5cf6',
            fg='white',
            relief='flat',
            padx=15,
            pady=5,
            cursor='hand2'
        )
        assign_rfid_btn.grid(row=0, column=2, sticky=tk.W, pady=(0, 5), padx=(10, 0))
        
        # RFID Status
        self.rfid_status_label = tk.Label(
            rfid_fields,
            text="Status: No RFID linked",
            font=('Arial', 11),
            fg='#dc2626',
            bg='#ffffff'
        )
        self.rfid_status_label.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))
        
        # Action Buttons
        button_frame = tk.Frame(forgot_window, bg='#f8fafc')
        button_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        # Close button
        close_btn = tk.Button(
            button_frame,
            text="❌ Close",
            command=forgot_window.destroy,
            font=('Arial', 12, 'bold'),
            bg='#6b7280',
            fg='white',
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2'
        )
        close_btn.pack(side=tk.RIGHT)
        
        # Store references for later use
        self.forgot_window = forgot_window
        self.student_id_entry = student_id_entry
        self.rfid_card_entry = rfid_card_entry
        self.verified_student = None
        
        # Focus on student ID field
        student_id_entry.focus()
    
    def verify_student_id(self, student_id, parent_frame):
        """Verify student ID exists in Firebase"""
        if not student_id:
            messagebox.showerror("Error", "Please enter student ID number")
            return
        
        try:
            # Check if student exists in Firebase
            students_ref = self.db.collection('students')
            query = students_ref.where('student_id', '==', student_id).limit(1)
            docs = query.get()
            
            if docs:
                # Student found
                student_data = docs[0].to_dict()
                student_name = student_data.get('name', 'Unknown')
                course = student_data.get('course', 'Unknown')
                
                self.verified_student = {
                    'student_id': student_id,
                    'name': student_name,
                    'course': course,
                    'document_id': docs[0].id
                }
                
                # Update status
                self.student_info_label.config(
                    text=f"✅ Verified: {student_name} (ID: {student_id}) - Course: {course}",
                    fg='#059669'
                )
                
                messagebox.showinfo("Student Verified", f"Student {student_name} verified successfully!")
                
            else:
                # Student not found
                self.verified_student = None
                self.student_info_label.config(
                    text="❌ Student ID not found in database",
                    fg='#dc2626'
                )
                messagebox.showerror("Student Not Found", f"Student ID {student_id} not found in database")
                
        except Exception as e:
            print(f"❌ Error verifying student: {e}")
            messagebox.showerror("Verification Error", f"Failed to verify student: {e}")
    
    def assign_rfid_to_student(self, student_id, rfid_number):
        """Assign RFID card to verified student"""
        if not self.verified_student:
            messagebox.showerror("Error", "Please verify student ID first")
            return
        
        if not rfid_number:
            messagebox.showerror("Error", "Please enter RFID card number")
            return
        
        try:
            # Generate RFID assignment ID
            rfid_id = f"STUDENT_RFID_{rfid_number}_{datetime.now().strftime('%H%M%S')}"
            
            # Log RFID assignment
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] RFID ASSIGNED TO STUDENT - {self.verified_student['name']} (ID: {student_id}) -> RFID: {rfid_number}\n"
            
            self.logs_text.config(state=tk.NORMAL)
            self.logs_text.insert(tk.END, log_entry)
            self.logs_text.config(state=tk.DISABLED)
            self.logs_text.see(tk.END)
            
            # Log to Firebase
            self._log_student_rfid_assignment_to_firebase(student_id, rfid_number, rfid_id)
            
            # Update status
            self.rfid_status_label.config(
                text=f"✅ RFID {rfid_number} linked to {self.verified_student['name']}",
                fg='#059669'
            )
            
            messagebox.showinfo("RFID Linked", f"RFID Card {rfid_number} linked to {self.verified_student['name']}\n\nStudent can now use this RFID card for TIME IN/TIME OUT at the main dashboard.")
            
        except Exception as e:
            print(f"❌ Error assigning RFID: {e}")
            messagebox.showerror("Assignment Error", f"Failed to assign RFID: {e}")
    
    def handle_visitor_entry(self):
        """Handle visitor entry - Open visitor information tab"""
        self.show_visitor_entry_tab()
    
    def get_person_name(self, person_id, person_type):
        """Get person name based on ID and type (simulated)"""
        # Sample names for demonstration
        sample_names = {
            "student": {
                "STU001": "John Smith",
                "STU002": "Sarah Johnson", 
                "STU003": "Mike Wilson",
                "STU004": "Emma Davis",
                "STU005": "James Wilson",
                "STU006": "Lisa Brown",
                "STU007": "David Garcia",
                "STU008": "Maria Rodriguez",
                "STU009": "Alex Thompson",
                "STU010": "Sophie Lee"
            },
            "teacher": {
                "TCH001": "Dr. Emily Davis",
                "TCH002": "Prof. Robert Brown",
                "TCH003": "Ms. Lisa Garcia",
                "TCH004": "Dr. Michael Johnson",
                "TCH005": "Prof. Sarah Wilson",
                "TCH006": "Mr. David Smith",
                "TCH007": "Dr. Maria Rodriguez",
                "TCH008": "Prof. Alex Thompson",
                "TCH009": "Ms. Sophie Lee",
                "TCH010": "Dr. James Garcia"
            },
            "visitor": {
                "VIS001": "Alex Thompson",
                "VIS002": "Maria Rodriguez",
                "VIS003": "David Lee",
                "VIS004": "Sarah Johnson",
                "VIS005": "Mike Wilson",
                "VIS006": "Emma Davis",
                "VIS007": "James Brown",
                "VIS008": "Lisa Garcia",
                "VIS009": "Sophie Smith",
                "VIS010": "Robert Johnson"
            }
        }
        
        return sample_names.get(person_type, {}).get(person_id, f"Unknown {person_type.title()}")
    
    def add_time_entry(self, person_type, person_id, person_name, action):
        """Add time in/out entry to activity logs"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        date = datetime.now().strftime("%Y-%m-%d")
        
        # Format the log entry
        action_text = "TIME IN" if action == "in" else "TIME OUT"
        log_entry = f"[{timestamp}] {action_text} - {person_type.upper()}: {person_name} (ID: {person_id})\n"
        
        self.logs_text.config(state=tk.NORMAL)
        self.logs_text.insert(tk.END, log_entry)
        self.logs_text.config(state=tk.DISABLED)
        self.logs_text.see(tk.END)
    
    def add_to_logs(self, message):
        """Add message to activity logs (legacy method)"""
        self.logs_text.config(state=tk.NORMAL)
        self.logs_text.insert(tk.END, message)
        self.logs_text.see(tk.END)
        self.logs_text.config(state=tk.DISABLED)
    
    def add_detection_result(self, result):
        """Add detection result to the results display"""
        self.detection_results.config(state=tk.NORMAL)
        self.detection_results.insert(tk.END, result)
        self.detection_results.see(tk.END)
        self.detection_results.config(state=tk.DISABLED)
    
    def _log_time_entry_to_firebase(self, person_type, person_id, person_name, action):
        """Log time in/out entry to Firebase"""
        if not self.firebase_initialized:
            return
        
        try:
            entries_ref = self.db.collection('time_entries')
            entries_ref.add({
                'person_id': person_id,
                'person_name': person_name,
                'person_type': person_type,
                'action': action,  # 'in' or 'out'
                'timestamp': datetime.now(),
                'date': datetime.now().strftime("%Y-%m-%d"),
                'time': datetime.now().strftime("%H:%M:%S"),
                'guard_id': self.current_guard_id,
                'session_id': self.session_id,
                'entry_method': 'manual'
            })
            action_text = "TIME IN" if action == "in" else "TIME OUT"
            print(f"✅ Time entry logged to Firebase: {action_text} - {person_name} ({person_id})")
        except Exception as e:
            print(f"❌ Failed to log time entry: {e}")
    
    def _log_person_entry_to_firebase(self, person_id, person_type):
        """Log person entry to Firebase (legacy method)"""
        if not self.firebase_initialized:
            return
        
        try:
            entries_ref = self.db.collection('person_entries')
            entries_ref.add({
                'person_id': person_id,
                'person_type': person_type,
                'entry_time': datetime.now(),
                'guard_id': self.current_guard_id,
                'session_id': self.session_id,
                'entry_method': 'manual'
            })
            print(f"✅ Person entry logged to Firebase: {person_type} {person_id}")
        except Exception as e:
            print(f"❌ Failed to log person entry: {e}")
    
    def _log_detection_result_to_firebase(self, detection_data):
        """Log detection result to Firebase"""
        if not self.firebase_initialized:
            return
        
        try:
            detections_ref = self.db.collection('detection_results')
            detections_ref.add({
                'detection_type': detection_data.get('type', 'uniform_check'),
                'result': detection_data.get('result', 'unknown'),
                'confidence': detection_data.get('confidence', 0.0),
                'person_type': detection_data.get('person_type', 'unknown'),
                'violation_type': detection_data.get('violation_type', 'none'),
                'timestamp': datetime.now(),
                'guard_id': self.current_guard_id,
                'session_id': self.session_id,
                'camera_id': detection_data.get('camera_id', 'default'),
                'image_path': detection_data.get('image_path', ''),
                'bbox': detection_data.get('bbox', [])
            })
            print(f"✅ Detection result logged to Firebase: {detection_data.get('result', 'unknown')}")
        except Exception as e:
            print(f"❌ Failed to log detection result: {e}")
    
    def _log_activity_to_firebase(self, activity_type, details):
        """Log activity to Firebase"""
        if not self.firebase_initialized:
            return
        
        try:
            activities_ref = self.db.collection('activity_logs')
            activities_ref.add({
                'activity_type': activity_type,
                'details': details,
                'timestamp': datetime.now(),
                'guard_id': self.current_guard_id,
                'session_id': self.session_id,
                'source': 'guard_dashboard'
            })
            print(f"✅ Activity logged to Firebase: {activity_type}")
        except Exception as e:
            print(f"❌ Failed to log activity: {e}")
    
    def _log_dashboard_event_to_firebase(self, event_type, event_data):
        """Log dashboard events to Firebase"""
        if not self.firebase_initialized:
            return
        
        try:
            events_ref = self.db.collection('dashboard_events')
            events_ref.add({
                'event_type': event_type,
                'event_data': event_data,
                'timestamp': datetime.now(),
                'guard_id': self.current_guard_id,
                'session_id': self.session_id,
                'dashboard_version': '1.0'
            })
            print(f"✅ Dashboard event logged to Firebase: {event_type}")
        except Exception as e:
            print(f"❌ Failed to log dashboard event: {e}")
    
    def _update_detection_statistics(self, violation_type):
        """Update detection statistics and log to Firebase"""
        self.total_detections += 1
        
        if violation_type == "VIOLATION":
            self.violation_count += 1
        elif violation_type == "COMPLIANT":
            self.compliant_count += 1
        
        # Log statistics to Firebase
        try:
            stats_ref = self.db.collection('detection_statistics')
            stats_ref.add({
                'session_id': self.session_id,
                'guard_id': self.current_guard_id,
                'total_detections': self.total_detections,
                'violation_count': self.violation_count,
                'compliant_count': self.compliant_count,
                'violation_rate': self.violation_count / self.total_detections if self.total_detections > 0 else 0,
                'timestamp': datetime.now()
            })
        except Exception as e:
            print(f"❌ Failed to log detection statistics: {e}")
    
    def start_real_detection(self):
        """Start real YOLO detection system"""
        try:
            # Check if dependencies are available
            if not YOLO_AVAILABLE:
                print("⚠️ YOLO not available, using simulation mode")
                self.simulate_detection_results()
                return
                
            if not CV2_AVAILABLE:
                print("⚠️ OpenCV not available, using simulation mode")
                self.simulate_detection_results()
                return
            
            # Load YOLO model
            print(f"📦 Loading YOLO model: {self.current_model_path}")
            self.model = YOLO(self.current_model_path)
            print("✅ YOLO model loaded successfully")
            
            # Initialize camera
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                print("⚠️ Camera not available, using simulation mode")
                self.simulate_detection_results()
                return
            
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1024)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 768)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            # Update camera label to show active status
            self.camera_label.config(
                text="📷 CAMERA FEED\n(ACTIVE)\n\nLIVE VIDEO STREAM\nAI DETECTION RUNNING",
                fg='#059669',
                font=('Arial', 14)  # Box shape font when active
            )
            
            print("🚀 Real detection system started")
            
            # Start detection thread
            self.detection_active = True
            self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
            self.detection_thread.start()
            print("🚀 Real detection system started")
            
        except Exception as e:
            print(f"❌ Failed to start real detection: {e}")
            print("🔄 Falling back to simulation mode")
            self.simulate_detection_results()
    
    def _detection_loop(self):
        """Real detection loop using YOLO"""
        frame_count = 0
        
        while self.detection_active and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                continue
            
            # Resize to smaller resolution for faster detection
            small_frame = cv2.resize(frame, (320, 240))
            
            frame_count += 1
            if frame_count % self.frame_skip != 0:
                continue  # Skip frames for speed
            
            try:
                # Run YOLO detection
                results = self.model.predict(
                    small_frame,
                    conf=self.conf_threshold,
                    iou=self.iou_threshold,
                    verbose=False,
                    imgsz=320
                )
                
                # Process detections
                for result in results:
                    for box in result.boxes:
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        class_name = self.model.names[cls]
                        
                        # Determine if it's a violation based on class
                        is_violation = "violation" in class_name.lower() or "non" in class_name.lower()
                        result_type = "VIOLATION" if is_violation else "COMPLIANT"
                        person_type = "student"  # Default, could be enhanced
                        
                        # Update UI in main thread
                        self.root.after(0, self._process_detection_result, {
                            'result': result_type,
                            'confidence': conf,
                            'person_type': person_type,
                            'class_name': class_name
                        })
                
                # Calculate FPS
                current_time = time.time()
                self.fps = 1 / (current_time - self.prev_time)
                self.prev_time = current_time
                
                # Update camera preview with current frame
                self.root.after(0, self._update_camera_preview, frame)
                
            except Exception as e:
                print(f"❌ Detection error: {e}")
                continue
        
        # Cleanup
        if self.cap:
            self.cap.release()
        print("🛑 Detection loop stopped")
    
    def _update_camera_preview(self, frame):
        """Update camera preview with current frame"""
        try:
            if not CV2_AVAILABLE:
                return  # Skip camera preview if cv2 not available
            
            # Get the current size of the camera label
            label_width = self.camera_label.winfo_width()
            label_height = self.camera_label.winfo_height()
            
            # Use default size if label hasn't been rendered yet
            if label_width <= 1 or label_height <= 1:
                label_width = 800
                label_height = 600
            
            # Calculate aspect ratio preserving resize
            frame_height, frame_width = frame.shape[:2]
            aspect_ratio = frame_width / frame_height
            
            # Calculate new dimensions maintaining aspect ratio
            if label_width / label_height > aspect_ratio:
                # Label is wider than frame aspect ratio
                new_height = label_height
                new_width = int(label_height * aspect_ratio)
            else:
                # Label is taller than frame aspect ratio
                new_width = label_width
                new_height = int(label_width / aspect_ratio)
            
            # Resize frame for display
            display_frame = cv2.resize(frame, (new_width, new_height))
            
            # Convert BGR to RGB for tkinter
            rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            
            # Convert to PIL Image
            from PIL import Image, ImageTk
            pil_image = Image.fromarray(rgb_frame)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(pil_image)
            
            # Update camera label with actual frame
            self.camera_label.config(image=photo, text="")
            self.camera_label.image = photo  # Keep a reference
            
        except Exception as e:
            print(f"❌ Camera preview update error: {e}")
    
    def _process_detection_result(self, detection_data):
        """Process detection result in main thread"""
        if not hasattr(self, 'detection_results'):
            return
        
        result = detection_data['result']
        confidence = detection_data['confidence']
        person_type = detection_data['person_type']
        class_name = detection_data['class_name']
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        detection_text = f"[{timestamp}] {person_type.upper()}: {result} (Conf: {confidence:.2f}, Class: {class_name})\n"
        
        # Add to detection results display
        self.add_detection_result(detection_text)
        
        # Log to Firebase
        firebase_data = {
            'type': 'uniform_check',
            'result': result,
            'confidence': confidence,
            'person_type': person_type,
            'violation_type': result,
            'camera_id': 'default',
            'bbox': [100, 100, 200, 200],
            'class_name': class_name
        }
        self._log_detection_result_to_firebase(firebase_data)
        
        # Update statistics
        self._update_detection_statistics(result)
        
        # Log activity
        self._log_activity_to_firebase('detection', {
            'person_type': person_type,
            'result': result,
            'confidence': confidence,
            'class_name': class_name
        })
    
    def simulate_detection_results(self):
        """Simulate detection results for demonstration (fallback)"""
        def add_detection():
            if self.dashboard_tab and hasattr(self, 'detection_results'):
                person_type = random.choice(["student", "teacher"])
                result = random.choice(["COMPLIANT", "VIOLATION"])
                confidence = round(random.uniform(0.7, 0.95), 2)
                
                timestamp = datetime.now().strftime("%H:%M:%S")
                detection_text = f"[{timestamp}] {person_type.upper()}: {result} (Confidence: {confidence}) [SIMULATED]\n"
                
                # Add to detection results display
                self.add_detection_result(detection_text)
                
                # Log to Firebase
                detection_data = {
                    'type': 'uniform_check',
                    'result': result,
                    'confidence': confidence,
                    'person_type': person_type,
                    'violation_type': result,
                    'camera_id': 'simulation',
                    'bbox': [100, 100, 200, 200]
                }
                self._log_detection_result_to_firebase(detection_data)
                
                # Update statistics
                self._update_detection_statistics(result)
                
                # Log detection activity to Firebase
                self._log_activity_to_firebase('detection', {
                    'person_type': person_type,
                    'result': result,
                    'confidence': confidence
                })
                
                # Schedule next detection
                self.root.after(5000, add_detection)  # Every 5 seconds
        
        # Start simulation
        add_detection()
    
    def start_dashboard_monitoring(self):
        """Start dashboard monitoring and logging"""
        # Log dashboard start event
        self._log_dashboard_event_to_firebase('dashboard_started', {
            'guard_id': self.current_guard_id,
            'session_id': self.session_id,
            'timestamp': datetime.now().isoformat()
        })
        
        # Add initial log entries for time tracking
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.add_to_logs("🕐 TIME TRACKING SYSTEM ACTIVE\n")
        self.add_to_logs("📋 Logging Time IN/OUT entries only\n")
        self.add_to_logs("📷 Camera will activate when student taps ID\n")
        self.add_to_logs("=" * 50 + "\n")
        
        # Initialize detection system but don't start camera yet
        self.init_detection_system()
        
        # Log dashboard initialization
        self._log_activity_to_firebase('dashboard_initialized', {
            'features': ['camera_preview', 'person_entry', 'activity_logs', 'detection_results'],
            'firebase_connected': self.firebase_initialized,
            'camera_status': 'standby'
        })
    
    def init_detection_system(self):
        """Initialize detection system without starting camera"""
        try:
            # Check if YOLO is available
            if not YOLO_AVAILABLE:
                print("⚠️ YOLO not available - detection system will use simulation mode")
                self.model = None
                self.cap = None
                self.detection_active = False
                self.detection_thread = None
                
                # Initialize detection statistics
                self.violation_count = 0
                self.compliant_count = 0
                self.total_detections = 0
                
                print("✅ Detection system initialized (simulation mode)")
                return
            
            # Load YOLO model
            self.current_model_path = "tourism.pt"  # Default model
            print(f"📦 Loading YOLO model: {self.current_model_path}")
            self.model = YOLO(self.current_model_path)
            print("✅ YOLO model loaded successfully")
            
            # Initialize camera variables but don't start camera
            self.cap = None
            self.detection_active = False
            self.detection_thread = None
            
            # Initialize detection statistics
            self.violation_count = 0
            self.compliant_count = 0
            self.total_detections = 0
            
            print("✅ Detection system initialized (camera standby)")
            
        except Exception as e:
            print(f"❌ Failed to initialize detection system: {e}")
            self.model = None
            self.cap = None
    
    def back_to_login(self):
        """Switch back to login tab and logout"""
        # Logout the current guard
        self.logout()
        
        # Show login tab and hide dashboard tab
        self.notebook.select(self.login_tab)
        self.notebook.hide(self.dashboard_tab)
    
    
    def logout(self):
        """Logout the current guard"""
        if self.current_guard_id:
            # Log logout to Firebase
            self._log_guard_logout(self.current_guard_id)
            self._log_system_event("GUARD_LOGOUT", {
                "guard_id": self.current_guard_id,
                "session_id": self.session_id
            })
        
        self.current_guard_id = None
        self.guard_id_var.set("")
        self.login_status_var.set("Not Logged In")
        self.status_label.config(fg='#dc2626')  # Red for not logged in
        self.session_id = None
        
        # Enable/disable buttons
        self.manual_login_btn.config(state=tk.NORMAL)
        
        # Switch back to login tab
        self.notebook.select(self.login_tab)
        
        messagebox.showinfo("Logout", "You have been logged out successfully")
    
    def quit_system(self):
        """Quit the entire system"""
        try:
            if messagebox.askyesno("Quit AI-niform", "Are you sure you want to quit AI-niform?"):
                if self.current_guard_id:
                    # Log logout to Firebase before quitting
                    self._log_guard_logout(self.current_guard_id)
                    self._log_system_event("SYSTEM_QUIT", {
                        "guard_id": self.current_guard_id,
                        "session_id": self.session_id
                    })
                
                self.root.destroy()
        except Exception as e:
            # If dialog fails, just quit directly
            print(f"Dialog error: {e}")
            self.root.destroy()
    
    
    def run(self):
        """Start the guard control center"""
        self.root.mainloop()
    
    def close(self):
        """Close the guard control center"""
        if self.current_guard_id:
            self.logout()
        
        self.root.destroy()

if __name__ == "__main__":
    # Test the guard control center
    app = GuardMainControl()
    app.run()
