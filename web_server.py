from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import timedelta
import hashlib
from firebase_config import (
    get_from_firebase,
    search_in_firebase,
    add_to_firebase,
    update_in_firebase,
    delete_from_firebase,
    firebase_manager,
)
from cloudinary_config import upload_image_to_cloudinary
import tempfile
import os
import time
import random
import json
from functools import lru_cache
from threading import Lock

# Feature flags
AUTO_CREATE_APPEALS = False  # Set to False to disable automatic appeal creation
AUTO_DELETE_VIOLATIONS_ON_APPEAL_APPROVAL = True  # Set to False to disable automatic violation deletion when appeal is approved

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# Cache for Firebase data to improve performance
_cache = {}
_cache_lock = Lock()
CACHE_DURATION = 10  # seconds (reduced for faster updates)


def get_cached_data(collection_name, limit=20):
    """Get data from cache or Firebase with caching and timeout"""
    current_time = time.time()
    cache_key = f"{collection_name}_{limit}"
    
    with _cache_lock:
        if cache_key in _cache:
            data, timestamp = _cache[cache_key]
            if current_time - timestamp < CACHE_DURATION:
                print(f"[CACHE] Using cached data for {collection_name}")
                return data
    
    # Cache miss or expired - try Firebase with fallback to sample data
    print(f"[REFRESH] Fetching fresh data for {collection_name}")
    
    # Try Firebase query with fallback to sample data
    try:
        print(f"[SEARCH] Attempting Firebase query for {collection_name}...")
        
        # Use the original get_from_firebase function which works better
        data = get_from_firebase(collection_name, limit) or []
        
        if data:
            with _cache_lock:
                _cache[cache_key] = (data, current_time)
            print(f"[OK] Firebase query successful for {collection_name}: {len(data)} items")
            return data
        else:
            print(f"[WARN] No data found in {collection_name}, using sample data")
            return get_sample_data(collection_name)
            
    except Exception as e:
        print(f"[ERROR] Firebase query failed for {collection_name}: {e}")
        print(f"[REFRESH] Using sample data for {collection_name}")
        return get_sample_data(collection_name)


def get_sample_data(collection_name):
    """Get sample data for demonstration purposes"""
    sample_data = {
        'violations': [],
        'appeals': [],
        'uniform_designs': [],
    }
    
    return sample_data.get(collection_name, [])


def get_student_violations_from_firebase():
    """Fetch student violations from Firebase and format them for display"""
    try:
        # Fetch from student_violations collection
        student_violations = get_from_firebase("student_violations") or []
        
        # Format the data to match violations table structure
        formatted_violations = []
        for sv in student_violations:
            # Extract name and student_id from student_violations
            formatted_violation = {
                'id': sv.get('id', ''),
                'student_name': sv.get('name', sv.get('student_name', 'N/A')),
                'student_id': sv.get('student_id', 'N/A'),
                'violation_type': sv.get('violation_type', 'Uniform Violation'),
                'course': sv.get('course', ''),
                'date': sv.get('date', sv.get('created_at', '')),
                'description': sv.get('description', 'Student violation'),
                'status': sv.get('status', 'Pending'),
                'reported_by': sv.get('reported_by', 'System'),
                'severity': sv.get('severity', 'Medium'),
                'last_updated': sv.get('last_updated', ''),  # Include last_updated from Firebase
                'last_missing_items': sv.get('last_missing_items', []),  # Include last_missing_items from Firebase
                'source': 'student_violations'  # Mark as coming from student_violations collection
            }
            formatted_violations.append(formatted_violation)
        
        print(f"[OK] Retrieved {len(formatted_violations)} violations from student_violations collection")
        return formatted_violations
    except Exception as e:
        print(f"[ERROR] Error fetching student_violations: {e}")
        return []


def get_student_violations_as_appeals():
    """Fetch student violations from Firebase and format them as appeals"""
    try:
        # Fetch from student_violations collection
        student_violations = get_from_firebase("student_violations") or []
        
        # Format the data to match appeals table structure
        formatted_appeals = []
        for sv in student_violations:
            # Extract name and student_id from student_violations and format as appeal
            formatted_appeal = {
                'id': sv.get('id', ''),
                'student_name': sv.get('name', sv.get('student_name', 'N/A')),
                'student_id': sv.get('student_id', 'N/A'),
                'violation_id': sv.get('id', ''),  # Use the same ID as violation_id
                'appeal_date': sv.get('date', sv.get('appeal_date', sv.get('created_at', ''))),
                'appeal_reason': sv.get('appeal_reason', sv.get('reason', sv.get('description', 'Appeal for violation'))),
                'reason': sv.get('appeal_reason', sv.get('reason', sv.get('description', 'Appeal for violation'))),
                'status': sv.get('appeal_status', sv.get('status', 'Pending Review')),
                'submitted_by': sv.get('submitted_by', sv.get('student_name', sv.get('name', 'Student'))),
                'priority': sv.get('priority', 'Medium'),
                'reason_type': sv.get('reason_type', 'Unexcused'),
                'source': 'student_violations'  # Mark as coming from student_violations collection
            }
            formatted_appeals.append(formatted_appeal)
        
        print(f"[OK] Retrieved {len(formatted_appeals)} appeals from student_violations collection")
        return formatted_appeals
    except Exception as e:
        print(f"[ERROR] Error fetching student_violations as appeals: {e}")
        return []


def clear_cache():
    """Clear the cache"""
    with _cache_lock:
        _cache.clear()


def analyze_design_uniqueness(design_data):
    """
    Analyze the uniqueness of a uniform design based on various factors.
    This is a simulated analysis - in a real implementation, you would use
    computer vision and machine learning models.
    """
    try:
        # Simulate uniqueness analysis based on design characteristics
        uniqueness_score = random.randint(60, 95)  # Simulated score 60-95%
        
        # Analyze different aspects
        color_uniqueness = analyze_color_uniqueness(design_data.get('colors', ''))
        pattern_uniqueness = analyze_pattern_uniqueness(design_data.get('type', ''))
        style_uniqueness = analyze_style_uniqueness(design_data.get('description', ''))
        
        # Generate uniqueness annotations
        annotations = []
        
        # Color analysis
        if color_uniqueness['score'] > 80:
            annotations.append({
                'aspect': 'Color Scheme',
                'score': color_uniqueness['score'],
                'comment': color_uniqueness['comment'],
                'uniqueness': 'High'
            })
        elif color_uniqueness['score'] > 60:
            annotations.append({
                'aspect': 'Color Scheme',
                'score': color_uniqueness['score'],
                'comment': color_uniqueness['comment'],
                'uniqueness': 'Medium'
            })
        else:
            annotations.append({
                'aspect': 'Color Scheme',
                'score': color_uniqueness['score'],
                'comment': color_uniqueness['comment'],
                'uniqueness': 'Low'
            })
        
        # Pattern analysis
        if pattern_uniqueness['score'] > 80:
            annotations.append({
                'aspect': 'Design Pattern',
                'score': pattern_uniqueness['score'],
                'comment': pattern_uniqueness['comment'],
                'uniqueness': 'High'
            })
        elif pattern_uniqueness['score'] > 60:
            annotations.append({
                'aspect': 'Design Pattern',
                'score': pattern_uniqueness['score'],
                'comment': pattern_uniqueness['comment'],
                'uniqueness': 'Medium'
            })
        else:
            annotations.append({
                'aspect': 'Design Pattern',
                'score': pattern_uniqueness['score'],
                'comment': pattern_uniqueness['comment'],
                'uniqueness': 'Low'
            })
        
        # Style analysis
        if style_uniqueness['score'] > 80:
            annotations.append({
                'aspect': 'Style Innovation',
                'score': style_uniqueness['score'],
                'comment': style_uniqueness['comment'],
                'uniqueness': 'High'
            })
        elif style_uniqueness['score'] > 60:
            annotations.append({
                'aspect': 'Style Innovation',
                'score': style_uniqueness['score'],
                'comment': style_uniqueness['comment'],
                'uniqueness': 'Medium'
            })
        else:
            annotations.append({
                'aspect': 'Style Innovation',
                'score': style_uniqueness['score'],
                'comment': style_uniqueness['comment'],
                'uniqueness': 'Low'
            })
        
        # Overall uniqueness assessment
        overall_score = sum(ann['score'] for ann in annotations) // len(annotations)
        
        if overall_score > 85:
            overall_assessment = "Highly Unique"
            recommendation = "This design stands out significantly and is recommended for approval."
        elif overall_score > 70:
            overall_assessment = "Moderately Unique"
            recommendation = "This design has good uniqueness but could benefit from minor enhancements."
        elif overall_score > 55:
            overall_assessment = "Somewhat Unique"
            recommendation = "Consider adding more distinctive elements to improve uniqueness."
        else:
            overall_assessment = "Low Uniqueness"
            recommendation = "This design may be too similar to existing uniforms. Consider redesigning."
        
        return {
            'overall_score': overall_score,
            'overall_assessment': overall_assessment,
            'recommendation': recommendation,
            'annotations': annotations,
            'analysis_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'unique_features': generate_unique_features(design_data)
        }
        
    except Exception as e:
        print(f"Error in uniqueness analysis: {e}")
        return {
            'overall_score': 50,
            'overall_assessment': 'Analysis Failed',
            'recommendation': 'Unable to analyze uniqueness. Please try again.',
            'annotations': [],
            'analysis_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'unique_features': []
        }


def analyze_color_uniqueness(colors):
    """Analyze color scheme uniqueness"""
    if not colors:
        return {'score': 30, 'comment': 'No color information provided'}
    
    color_keywords = ['unique', 'vibrant', 'distinctive', 'bold', 'creative', 'innovative']
    color_score = 50
    
    # Check for unique color combinations
    if any(keyword in colors.lower() for keyword in color_keywords):
        color_score += 25
    
    # Check for specific color combinations
    if 'gradient' in colors.lower():
        color_score += 15
    if 'metallic' in colors.lower():
        color_score += 10
    if len(colors.split()) > 3:  # Multiple colors
        color_score += 10
    
    return {
        'score': min(color_score, 100),
        'comment': f"Color scheme analysis: {colors}. {'Excellent color diversity' if color_score > 80 else 'Good color choices' if color_score > 60 else 'Consider more distinctive colors'}"
    }


def analyze_pattern_uniqueness(design_type):
    """Analyze design pattern uniqueness"""
    if not design_type:
        return {'score': 30, 'comment': 'No design type specified'}
    
    pattern_score = 60  # Base score
    
    # Different types have different uniqueness potential
    if design_type.lower() in ['complete set', 'blouse']:
        pattern_score += 20
    elif design_type.lower() in ['shirt', 'pants']:
        pattern_score += 10
    elif design_type.lower() == 'skirt':
        pattern_score += 15
    
    return {
        'score': min(pattern_score, 100),
        'comment': f"Design type '{design_type}' shows {'high' if pattern_score > 80 else 'moderate' if pattern_score > 60 else 'basic'} uniqueness potential"
    }


def analyze_style_uniqueness(description):
    """Analyze style innovation uniqueness"""
    if not description:
        return {'score': 40, 'comment': 'No description provided for style analysis'}
    
    style_keywords = ['modern', 'innovative', 'unique', 'distinctive', 'creative', 'elegant', 'sophisticated']
    style_score = 50
    
    # Check for style-related keywords
    keyword_count = sum(1 for keyword in style_keywords if keyword in description.lower())
    style_score += keyword_count * 8
    
    # Check description length (more detailed descriptions often indicate more thought)
    if len(description) > 100:
        style_score += 10
    if len(description) > 200:
        style_score += 5
    
    return {
        'score': min(style_score, 100),
        'comment': f"Style analysis: {'Excellent innovation' if style_score > 80 else 'Good style elements' if style_score > 60 else 'Basic style approach'}"
    }


def generate_unique_features(design_data):
    """Generate list of unique features identified in the design"""
    features = []
    
    # Color features
    if design_data.get('colors'):
        if 'gradient' in design_data['colors'].lower():
            features.append("Gradient color transition")
        if 'metallic' in design_data['colors'].lower():
            features.append("Metallic finish elements")
        if len(design_data['colors'].split()) > 2:
            features.append("Multi-color combination")
    
    # Type features
    if design_data.get('type'):
        if design_data['type'].lower() == 'complete set':
            features.append("Coordinated complete uniform set")
        elif design_data['type'].lower() == 'blouse':
            features.append("Professional blouse design")
    
    # Description features
    if design_data.get('description'):
        desc = design_data['description'].lower()
        if 'modern' in desc:
            features.append("Modern design approach")
        if 'elegant' in desc:
            features.append("Elegant styling")
        if 'innovative' in desc:
            features.append("Innovative design elements")
    
    # Default features if none identified
    if not features:
        features = ["Standard uniform design", "Functional design elements"]
    
    return features


def update_violation_in_firebase(violation_id, data):
    """Update violation in Firebase"""
    try:
        return update_in_firebase("violations", violation_id, data)
    except Exception as e:
        print(f"Error updating violation: {e}")
        return False


def delete_violation_from_firebase(violation_id):
    """Delete violation from Firebase"""
    try:
        return delete_from_firebase("violations", violation_id)
    except Exception as e:
        print(f"Error deleting violation: {e}")
        return False


def update_appeal_in_firebase(appeal_id, data):
    """Update appeal in Firebase"""
    try:
        return update_in_firebase("appeals", appeal_id, data)
    except Exception as e:
        print(f"Error updating appeal: {e}")
        return False


def delete_appeal_from_firebase(appeal_id):
    """Delete appeal from Firebase"""
    try:
        return delete_from_firebase("appeals", appeal_id)
    except Exception as e:
        print(f"Error deleting appeal: {e}")
        return False


def update_design_in_firebase(design_id, data):
    """Update design in Firebase"""
    try:
        return update_in_firebase("uniform_designs", design_id, data)
    except Exception as e:
        print(f"Error updating design: {e}")
        return False


def get_violation_status_by_count(student_name, student_id):
    """Determine violation status based on violation count for a student"""
    try:
        # Get all violations for this student
        violations = get_from_firebase("violations") or []
        student_violations = [v for v in violations if v.get('student_name') == student_name and v.get('student_id') == student_id]
        
        violation_count = len(student_violations)
        
        # New status logic based on offense count:
        # 1st offense = Warning
        # 2nd offense = Advisory  
        # 3rd+ offense = Guidance
        if violation_count == 1:
            return 'Warning'
        elif violation_count == 2:
            return 'Advisory'
        elif violation_count >= 3:
            return 'Guidance'
        else:
            return 'Warning'  # Default fallback
        
    except Exception as e:
        print(f"Error calculating violation status: {e}")
        return 'Warning'  # Default fallback


def update_all_violation_statuses():
    """Update all existing violations to have correct status based on count"""
    try:
        violations = get_from_firebase("violations") or []
        updated_count = 0
        
        # Group violations by student
        student_violations = {}
        for violation in violations:
            student_key = f"{violation.get('student_name', '')}_{violation.get('student_id', '')}"
            if student_key not in student_violations:
                student_violations[student_key] = []
            student_violations[student_key].append(violation)
        
        # Update status for each student's violations
        for student_key, student_viols in student_violations.items():
            violation_count = len(student_viols)
            if violation_count == 1:
                new_status = 'Warning'
            elif violation_count == 2:
                new_status = 'Advisory'
            elif violation_count >= 3:
                new_status = 'Guidance'
            else:
                new_status = 'Warning'
            
            # Update each violation for this student
            for violation in student_viols:
                if violation.get('status') != new_status:
                    violation_id = violation.get('id')
                    if violation_id:
                        update_data = {'status': new_status}
                        if update_violation_in_firebase(violation_id, update_data):
                            updated_count += 1
                            print(f"Updated violation {violation_id} status to {new_status}")
        
        print(f"Updated {updated_count} violations with new status logic")
        return updated_count
        
    except Exception as e:
        print(f"Error updating violation statuses: {e}")
        return 0


def delete_design_from_firebase(design_id):
    """Delete design from Firebase"""
    try:
        return delete_from_firebase("uniform_designs", design_id)
    except Exception as e:
        print(f"Error deleting design: {e}")
        return False


app = Flask(__name__)
app.secret_key = "replace-this-with-a-secure-secret-key"
app.permanent_session_lifetime = timedelta(hours=8)


@app.context_processor
def inject_globals():
    return {"app_name": "AI-niform"}


@app.route("/")
def root():
    return redirect(url_for("login"))


def load_local_users():
    """Load users from local users.txt file"""
    users = {}
    try:
        with open("users.txt", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split(",")
                    if len(parts) >= 5:
                        username, password_hash, user_type, name, status = parts[:5]
                        users[username] = {
                            "username": username,
                            "password_hash": password_hash,
                            "role": user_type,
                            "full_name": name,
                            "status": status,
                            "id": username  # Use username as ID for local users
                        }
    except FileNotFoundError:
        print("users.txt file not found")
    except Exception as e:
        print(f"Error loading users.txt: {e}")
    return users


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        print(f"[LOGIN] Login attempt: {username}")

        if not username or not password:
            flash("Please enter both username and password", "error")
            return render_template("login.html")

        user = None
        
        # Try local users first (faster)
        try:
            local_users = load_local_users()
            user = local_users.get(username)
            if user:
                print(f"[OK] User found locally: {username}")
        except Exception as e:
            print(f"[ERROR] Error loading local users: {e}")
        
        # Only try Firebase if not found locally (skip for now to speed up login)
        if not user:
            print(f"[WARN] User {username} not found locally, skipping Firebase search for faster login")
            # try:
            #     print(f"[SEARCH] Searching Firebase for user: {username}")
            #     user_records = search_in_firebase("users", "username", username) or []
            #     if user_records:
            #         user = user_records[0]
            #         print(f"[OK] User found in Firebase: {username}")
            # except Exception as e:
            #     print(f"[ERROR] Error searching Firebase users: {e}")

        if not user:
            print(f"[ERROR] User not found: {username}")
            flash("Invalid username or password", "error")
            return render_template("login.html")

        # Verify password
        password_hash = hash_password(password)
        if password_hash != user.get("password_hash"):
            print(f"[ERROR] Invalid password for user: {username}")
            flash("Invalid username or password", "error")
            return render_template("login.html")

        if (user.get("status") or "ACTIVE") != "ACTIVE":
            print(f"[ERROR] Account deactivated: {username}")
            flash("Account is deactivated. Please contact administrator.", "error")
            return render_template("login.html")

        # Login OK → put minimal user in session
        print(f"[OK] Login successful: {username}")
        session.permanent = True
        user_role = user.get("role", "guidance")
        session["user"] = {
            "id": user.get("id"),
            "username": user.get("username"),
            "name": user.get("full_name") or user.get("username"),
            "role": user_role,
        }
        flash("Welcome back!", "success")
        # Redirect based on user role
        if user_role.lower() == "admin":
            return redirect(url_for("admin_dashboard"))
        else:
            return redirect(url_for("loading"))

    # GET
    return render_template("login.html")


@app.route("/loading")
def loading():
    """Loading page that redirects to dashboard"""
    if not require_login():
        return redirect(url_for("login"))
    
    # Redirect to dashboard after a short delay
    return render_template("loading.html")

@app.route("/admin/add-sample-data")
def add_sample_data_to_firebase():
    """Admin route to add sample data to Firebase"""
    if not session.get("user"):
        return redirect(url_for("login"))
    
    try:
        # Add sample violations (empty for clean display)
        violations = []
        
        for violation in violations:
            add_to_firebase('violations', violation)
        
        # Add sample appeals (empty for clean display)
        appeals = []
        
        for appeal in appeals:
            add_to_firebase('appeals', appeal)
        
        # Add sample designs (empty for clean display)
        designs = []
        
        for design in designs:
            add_to_firebase('uniform_designs', design)
        
        # Clear cache to force refresh
        clear_cache()
        
        flash("Sample data added to Firebase successfully!", "success")
        return redirect(url_for("dashboard"))
        
    except Exception as e:
        flash(f"Error adding data to Firebase: {e}", "error")
        return redirect(url_for("dashboard"))


@app.route("/admin/update-violation-statuses")
def admin_update_violation_statuses():
    """Admin route to update all violation statuses based on new logic"""
    if not session.get("user"):
        return redirect(url_for("login"))
    
    try:
        updated_count = update_all_violation_statuses()
        clear_cache()  # Clear cache to force refresh
        flash(f"Updated {updated_count} violations with new status logic!", "success")
        return redirect(url_for("dashboard"))
        
    except Exception as e:
        flash(f"Error updating violation statuses: {e}", "error")
        return redirect(url_for("dashboard"))

# API Routes for AJAX requests
@app.route("/api/violations", methods=["GET", "POST"])
def api_violations():
    """API endpoint to get all violations or add a new violation"""
    if not session.get("user"):
        return {"error": "Unauthorized"}, 401
    
    if request.method == "GET":
        try:
            # Get all violations from Firebase
            violations = get_from_firebase("violations") or []
            # Get student violations from student_violations collection
            student_violations = get_student_violations_from_firebase()
            
            # Merge both collections
            all_violations = violations + student_violations
            
            print(f"[API] GET /api/violations returning {len(all_violations)} violations (from violations: {len(violations)}, from student_violations: {len(student_violations)})")
            return {"success": True, "data": all_violations}, 200
        except Exception as e:
            print(f"[ERROR] GET /api/violations failed: {e}")
            return {"error": str(e)}, 500

    elif request.method == "POST":
        try:
            print(f"[API] POST /api/violations - Starting violation creation")
            
            # Check Firebase connection first
            if not firebase_manager.db:
                print(f"[ERROR] Firebase not initialized - cannot add violation")
                return {"error": "Database connection failed. Please check Firebase configuration.", "debug": "firebase_not_initialized"}, 500
            
            data = request.get_json()
            if not data:
                print(f"[ERROR] No data provided in request")
                return {"error": "No data provided"}, 400
            
            print(f"[DEBUG] Received violation data: {data}")
            
            # Validate required fields
            required_fields = ['student_name', 'student_id', 'violation_type', 'description']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                print(f"[ERROR] Missing required fields: {missing_fields}")
                return {"error": f"Missing required fields: {', '.join(missing_fields)}"}, 400
            
            # Add current date automatically if not provided
            if 'date' not in data or not data['date']:
                from datetime import datetime
                data['date'] = datetime.now().strftime('%Y-%m-%d')
                print(f"[DEBUG] Added default date: {data['date']}")
            
            # Add unique timestamp to prevent race conditions
            from datetime import datetime
            data['created_timestamp'] = datetime.now().isoformat()
            print(f"[DEBUG] Added timestamp: {data['created_timestamp']}")
            
            # Set default values for severity and status
            if 'severity' not in data or not data['severity']:
                data['severity'] = 'Medium'
            
            # Check for duplicate violations (same student, same description, same date)
            student_name = data.get('student_name', '')
            student_id = data.get('student_id', '')
            description = data.get('description', '')
            violation_date = data.get('date', '')
            created_timestamp = data.get('created_timestamp', '')
            
            print(f"[DEBUG] Checking for duplicates - Student: {student_name}, ID: {student_id}, Date: {violation_date}")
            
            if student_name and student_id and description and violation_date:
                try:
                    # Get existing violations to check for duplicates
                    print(f"[DEBUG] Fetching existing violations for duplicate check")
                    existing_violations = get_from_firebase("violations") or []
                    print(f"[DEBUG] Found {len(existing_violations)} existing violations")
                    
                    # Check for exact duplicates (same student, description, date)
                    duplicate_check = [
                        v for v in existing_violations 
                        if (v.get('student_name') == student_name and 
                            v.get('student_id') == student_id and 
                            v.get('description', '').strip().lower() == description.strip().lower() and
                            v.get('date') == violation_date)
                    ]
                    
                    if duplicate_check:
                        print(f"[WARN] Duplicate violation found for {student_name}")
                        return {"error": "A violation with the same description already exists for this student on this date", "duplicate": True}, 409
                    
                    # Check for rapid duplicate submissions (within 5 seconds)
                    if created_timestamp:
                        from datetime import datetime, timedelta
                        current_time = datetime.now()
                        recent_violations = [
                            v for v in existing_violations 
                            if (v.get('student_name') == student_name and 
                                v.get('student_id') == student_id and
                                v.get('created_timestamp'))
                        ]
                        
                        for violation in recent_violations:
                            try:
                                violation_time = datetime.fromisoformat(violation.get('created_timestamp', ''))
                                if (current_time - violation_time).total_seconds() < 5:
                                    print(f"[WARN] Rapid duplicate submission detected for {student_name}")
                                    return {"error": "Please wait before submitting another violation for this student", "duplicate": True}, 429
                            except:
                                continue
                except Exception as e:
                    print(f"[WARN] Error checking duplicates: {e}")
                    # Continue with creation even if duplicate check fails
            
            # Determine status based on violation count for this student
            try:
                if student_name and student_id:
                    data['status'] = get_violation_status_by_count(student_name, student_id)
                    print(f"[DEBUG] Calculated status: {data['status']}")
                else:
                    data['status'] = 'Warning'  # Fallback if no student info
            except Exception as e:
                print(f"[WARN] Error calculating status: {e}")
                data['status'] = 'Warning'
            
            # Add violation to Firebase
            print(f"[DEBUG] Attempting to add violation to Firebase")
            doc_id = add_to_firebase("violations", data)
            
            if doc_id:
                print(f"[SUCCESS] Violation added successfully with ID: {doc_id}")
                appeal_created = False
                
                # Automatically create an appeal for the violation if enabled
                if AUTO_CREATE_APPEALS:
                    try:
                        appeal_data = {
                            'student_name': data.get('student_name', ''),
                            'student_id': data.get('student_id', ''),
                            'violation_id': doc_id,
                            'appeal_reason': 'Automatic appeal created for violation',
                            'status': 'Pending Review',
                            'submitted_date': data.get('date', ''),
                            'submitted_by': data.get('student_name', 'Student'),
                            'created_automatically': True
                        }
                        
                        appeal_id = add_to_firebase("appeals", appeal_data)
                        if appeal_id:
                            print(f"[OK] Auto-created appeal {appeal_id} for violation {doc_id}")
                            # Update the appeal data with the ID for consistency
                            appeal_data['id'] = appeal_id
                            update_in_firebase("appeals", appeal_id, appeal_data)
                            appeal_created = True
                        else:
                            print(f"[WARN] Failed to auto-create appeal for violation {doc_id}")
                    except Exception as e:
                        print(f"[WARN] Error auto-creating appeal: {e}")
                
                # Clear cache to force refresh
                print(f"[CACHE] Clearing cache after adding violation {doc_id}")
                clear_cache()
                print(f"[CACHE] Cache cleared successfully")
                return {"success": True, "id": doc_id, "appeal_created": appeal_created}, 201
            else:
                print(f"[ERROR] Failed to add violation to Firebase - add_to_firebase returned None")
                return {"error": "Failed to add violation to database. Please check Firebase configuration.", "debug": "add_to_firebase_failed"}, 500
                
        except Exception as e:
            print(f"[ERROR] POST /api/violations failed: {e}")
            import traceback
            traceback.print_exc()
            return {"error": f"Server error: {str(e)}", "debug": "exception_in_violation_creation"}, 500


@app.route("/api/violations/<violation_id>", methods=["PUT"])
def api_update_violation(violation_id):
    """API endpoint to update a violation"""
    if not session.get("user"):
        return {"error": "Unauthorized"}, 401
    
    try:
        data = request.get_json()
        if not data:
            return {"error": "No data provided"}, 400
        
        # Determine status based on violation count for this student
        student_name = data.get('student_name', '')
        student_id = data.get('student_id', '')
        if student_name and student_id:
            data['status'] = get_violation_status_by_count(student_name, student_id)
        
        # Update violation in Firebase
        success = update_violation_in_firebase(violation_id, data)
        if success:
            # Clear cache to force refresh
            clear_cache()
            return {"success": True}, 200
        else:
            return {"error": "Failed to update violation"}, 500
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/api/violations/<violation_id>", methods=["DELETE"])
def api_delete_violation(violation_id):
    """API endpoint to delete a violation"""
    if not session.get("user"):
        return {"error": "Unauthorized"}, 401
    
    try:
        # Delete violation from Firebase
        success = delete_violation_from_firebase(violation_id)
        if success:
            # Clear cache to force refresh
            clear_cache()
            return {"success": True}, 200
        else:
            return {"error": "Failed to delete violation"}, 500
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/api/violations/student/<student_name>", methods=["DELETE"])
def api_delete_student_violations(student_name):
    """API endpoint to delete all violations for a specific student"""
    if not session.get("user"):
        return {"error": "Unauthorized"}, 401
    
    try:
        # Get all violations
        violations = get_from_firebase("violations") or []
        
        # Filter violations for this student
        student_violations = [v for v in violations if v.get('student_name') == student_name]
        
        if not student_violations:
            return {"success": True, "deleted_count": 0, "message": "No violations found for this student"}, 200
        
        # Delete each violation
        deleted_violations = 0
        failed_violations = 0
        
        for violation in student_violations:
            violation_id = violation.get('id')
            if violation_id:
                success = delete_violation_from_firebase(violation_id)
                if success:
                    deleted_violations += 1
                else:
                    failed_violations += 1
        
        # Clear cache to force refresh
        clear_cache()
        
        # Prepare response message
        total_deleted = deleted_violations
        total_failed = failed_violations
        
        if total_failed == 0:
            message = f"Successfully deleted {deleted_violations} violation(s) for {student_name}"
        else:
            message = f"Deleted {deleted_violations} violation(s) for {student_name}, {total_failed} failed"
        
        return {
            "success": True, 
            "deleted_violations": deleted_violations,
            "total_deleted": total_deleted,
            "message": message
        }, 200
            
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/api/appeals", methods=["GET", "POST"])
def api_appeals():
    """API endpoint to get all appeals or add a new appeal"""
    if not session.get("user"):
        return {"error": "Unauthorized"}, 401
    
    if request.method == "GET":
        try:
            # Get all appeals from Firebase
            appeals = get_from_firebase("appeals") or []
            # Get student violations formatted as appeals from student_violations collection
            student_violations_appeals = get_student_violations_as_appeals()
            
            # Merge both collections
            all_appeals = appeals + student_violations_appeals
            
            print(f"[API] GET /api/appeals returning {len(all_appeals)} appeals (from appeals: {len(appeals)}, from student_violations: {len(student_violations_appeals)})")
            
            # Debug: Print first few appeals to see their structure
            if all_appeals:
                print(f"[DEBUG] First appeal structure: {all_appeals[0]}")
                print(f"[DEBUG] Appeal IDs: {[a.get('id', 'NO_ID') for a in all_appeals[:5]]}")
            
            # Migrate existing appeals to include reason_type if missing
            appeals_to_update = []
            
            for appeal in appeals:  # Only update appeals from the appeals collection
                if 'reason_type' not in appeal or not appeal['reason_type']:
                    appeal['reason_type'] = 'Unexcused'
                    if 'id' in appeal:
                        appeals_to_update.append(appeal)
            
            # Update only appeals that need migration
            if appeals_to_update:
                print(f"[MIGRATION] Updating {len(appeals_to_update)} appeals with default reason_type")
                for appeal in appeals_to_update:
                    try:
                        update_in_firebase("appeals", appeal['id'], appeal)
                    except Exception as e:
                        print(f"[WARN] Failed to update appeal {appeal['id']}: {e}")
                clear_cache()
            
            return {"success": True, "data": all_appeals}, 200
        except Exception as e:
            return {"error": str(e)}, 500
    
    elif request.method == "POST":
        try:
            data = request.get_json()
            if not data:
                return {"error": "No data provided"}, 400
            
            # Set default reason_type if not provided
            if 'reason_type' not in data or not data['reason_type']:
                data['reason_type'] = 'Unexcused'
            
            # Add appeal to Firebase
            doc_id = add_to_firebase("appeals", data)
            if doc_id:
                # Clear cache to force refresh
                clear_cache()
                return {"success": True, "id": doc_id}, 201
            else:
                return {"error": "Failed to add appeal"}, 500
        except Exception as e:
            return {"error": str(e)}, 500


@app.route("/api/appeals/<appeal_id>", methods=["PUT"])
def api_update_appeal(appeal_id):
    """API endpoint to update an appeal"""
    if not session.get("user"):
        return {"error": "Unauthorized"}, 401
    
    try:
        data = request.get_json()
        if not data:
            return {"error": "No data provided"}, 400
        
        # Set default reason_type if not provided
        if 'reason_type' not in data or not data['reason_type']:
            data['reason_type'] = 'Unexcused'
        
        # Determine which collection contains this appeal
        appeal = None
        collection_name = None
        
        # First check in appeals collection
        appeals = get_from_firebase("appeals") or []
        appeal = next((a for a in appeals if a.get('id') == appeal_id), None)
        if appeal:
            collection_name = "appeals"
            print(f"[INFO] Appeal {appeal_id} found in appeals collection")
        else:
            # Check in student_violations collection
            student_violations = get_from_firebase("student_violations") or []
            appeal = next((sv for sv in student_violations if sv.get('id') == appeal_id), None)
            if appeal:
                collection_name = "student_violations"
                print(f"[INFO] Appeal {appeal_id} found in student_violations collection")
        
        if not appeal:
            print(f"[ERROR] Appeal {appeal_id} not found in any collection")
            return {"error": f"Appeal {appeal_id} not found"}, 404
        
        # Check if appeal is being approved
        violation_deleted = False
        if data.get('status') == 'Approved' and AUTO_DELETE_VIOLATIONS_ON_APPEAL_APPROVAL:
            print(f"[REFRESH] Appeal {appeal_id} is being approved - checking for related violation to delete...")
            try:
                # Get violation_id from the appeal
                violation_id = appeal.get('violation_id') or appeal.get('id')  # For student_violations, the id is the violation_id
                
                if violation_id:
                    print(f"[SEARCH] Found related violation {violation_id} for appeal {appeal_id}")
                    
                    # Delete the related violation from violations collection
                    violation_deleted = delete_from_firebase("violations", violation_id)
                    if violation_deleted:
                        print(f"[OK] Successfully deleted violation {violation_id} for approved appeal {appeal_id}")
                    else:
                        # Also try deleting from student_violations if it's a student_violations appeal
                        if collection_name == "student_violations":
                            violation_deleted = delete_from_firebase("student_violations", violation_id)
                            if violation_deleted:
                                print(f"[OK] Successfully deleted student_violation {violation_id} for approved appeal {appeal_id}")
                            else:
                                print(f"[WARN] Failed to delete violation {violation_id} for approved appeal {appeal_id}")
                        else:
                            print(f"[WARN] Failed to delete violation {violation_id} for approved appeal {appeal_id}")
                else:
                    print(f"[WARN] No violation_id found for appeal {appeal_id} - skipping violation deletion")
            except Exception as e:
                print(f"[WARN] Error finding/deleting related violation: {e}")
        elif data.get('status') == 'Approved' and not AUTO_DELETE_VIOLATIONS_ON_APPEAL_APPROVAL:
            print(f"[INFO] Appeal {appeal_id} approved but auto-deletion is disabled")
        
        # Map status field for student_violations
        if collection_name == "student_violations":
            # For student_violations, use appeal_status field
            if 'status' in data:
                data['appeal_status'] = data['status']
                # Also keep status for compatibility
            print(f"[INFO] Updating student_violation {appeal_id} with status: {data.get('status')}")
        
        # Update appeal in the correct collection
        success = update_in_firebase(collection_name, appeal_id, data)
        if success:
            # Clear cache to force refresh
            clear_cache()
            return {"success": True, "violation_deleted": violation_deleted}, 200
        else:
            print(f"[ERROR] Failed to update appeal {appeal_id} in {collection_name} collection")
            return {"error": f"Failed to update appeal in {collection_name}"}, 500
    except Exception as e:
        print(f"[ERROR] Exception in api_update_appeal: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}, 500

@app.route("/api/appeals/<appeal_id>", methods=["DELETE"])
def api_delete_appeal(appeal_id):
    """API endpoint to delete an appeal"""
    if not session.get("user"):
        return {"error": "Unauthorized"}, 401
    
    try:
        # Delete appeal from Firebase
        success = delete_appeal_from_firebase(appeal_id)
        if success:
            # Clear cache to force refresh
            clear_cache()
            return {"success": True}, 200
        else:
            return {"error": "Failed to delete appeal"}, 500
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/api/designs", methods=["GET", "POST"])
def api_designs():
    """API endpoint to get all designs or add a new design"""
    if not session.get("user"):
        return {"error": "Unauthorized"}, 401
    
    if request.method == "GET":
        try:
            # Get all designs from Firebase
            designs = get_from_firebase("uniform_designs") or []
            return {"success": True, "data": designs}, 200
        except Exception as e:
            return {"error": str(e)}, 500
    
    elif request.method == "POST":
        try:
            # Handle file upload
            name = request.form.get("name", "").strip()
            typ = request.form.get("type", "").strip()
            
            if not name or not typ:
                return {"error": "Design name and type are required"}, 400
            
            # Handle image upload
            image_url = ""
            file = request.files.get("image")
            if file and file.filename:
                try:
                    suffix = os.path.splitext(file.filename)[1]
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        file.save(tmp.name)
                        tmp_path = tmp.name
                    
                    # Upload to Cloudinary
                    public_id = f"design_{name.replace(' ', '_')}_{int(time.time())}"
                    image_url = upload_image_to_cloudinary(tmp_path, public_id)
                    
                    if not image_url:
                        print("[WARN] Image upload failed - design will be saved without image")
                    
                    # Clean up temporary file
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
                except Exception as e:
                    print(f"Error uploading image: {e}")
                    image_url = ""
            
            data = {
                "name": name,
                "type": typ,
                "image_url": image_url,
                "created_date": time.strftime('%Y-%m-%d'),
                "status": "Under Review"
            }
            
            # Add design to Firebase
            doc_id = add_to_firebase("uniform_designs", data)
            if doc_id:
                # Clear cache to force refresh
                clear_cache()
                return {"success": True, "id": doc_id}, 201
            else:
                return {"error": "Failed to add design"}, 500
        except Exception as e:
            return {"error": str(e)}, 500


@app.route("/api/designs/<design_id>", methods=["PUT"])
def api_update_design(design_id):
    """API endpoint to update a design"""
    if not session.get("user"):
        return {"error": "Unauthorized"}, 401
    
    try:
        data = request.get_json()
        if not data:
            return {"error": "No data provided"}, 400
        
        # Update design in Firebase
        success = update_design_in_firebase(design_id, data)
        if success:
            # Clear cache to force refresh
            clear_cache()
            return {"success": True}, 200
        else:
            return {"error": "Failed to update design"}, 500
    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/api/designs/<design_id>", methods=["DELETE"])
def api_delete_design(design_id):
    """API endpoint to delete a design"""
    if not session.get("user"):
        return {"error": "Unauthorized"}, 401
    
    try:
        # Delete design from Firebase
        success = delete_design_from_firebase(design_id)
        if success:
            # Clear cache to force refresh
            clear_cache()
            return {"success": True}, 200
        else:
            return {"error": "Failed to delete design"}, 500
    except Exception as e:
        return {"error": str(e)}, 500


def require_login():
    if "user" not in session:
        return False
    return True


@app.route("/dashboard")
def dashboard():
    if not require_login():
        return redirect(url_for("login"))

    user = session.get("user")
    if not user:
        print("[ERROR] No user in session, redirecting to login")
        return redirect(url_for("login"))
    
    print(f"[DASHBOARD] Dashboard loading for user: {user.get('username', 'unknown')}")

    # Use cached data for better performance with fallback
    try:
        violations = get_cached_data("violations", 20)
        # Also fetch student violations from student_violations collection
        student_violations = get_student_violations_from_firebase()
        # Merge both collections for dashboard display
        violations = violations + student_violations
        appeals = get_cached_data("appeals", 20)
        # Also fetch student violations formatted as appeals from student_violations collection
        student_violations_appeals = get_student_violations_as_appeals()
        # Merge both collections for dashboard display
        appeals = appeals + student_violations_appeals
        designs = get_cached_data("uniform_designs", 20)
        print(f"[STATS] Loaded data - Violations: {len(violations)} (includes {len(student_violations)} from student_violations), Appeals: {len(appeals)} (includes {len(student_violations_appeals)} from student_violations), Designs: {len(designs)}")
    except Exception as e:
        print(f"[WARN] Error loading dashboard data: {e}")
        # Fallback to empty data
        violations = []
        appeals = []
        designs = []

    # Calculate real statistics
    total_violations = len(violations)
    pending_violations = len([v for v in violations if v.get('status') == 'Pending'])
    total_appeals = len(appeals)
    pending_appeals = len([a for a in appeals if a.get('status') == 'Pending Review'])
    total_designs = len(designs)
    approved_designs = len([d for d in designs if d.get('status') == 'Approved'])

    # Calculate compliance rate (mock calculation)
    compliance_rate = 94.2 if total_violations == 0 else max(70, 100 - (total_violations * 2))

    stats = {
        'total_students': 1247,  # This would come from a students collection
        'compliance_rate': compliance_rate,
        'violations_today': pending_violations,
        'events_this_week': 8,  # This would come from events collection
        'total_violations': total_violations,
        'total_appeals': total_appeals,
        'total_designs': total_designs,
        'approved_designs': approved_designs
    }

    print(f"[OK] Dashboard ready for user: {user.get('username', 'unknown')}")
    return render_template(
        "guidance_dashboard.html",
        user=user,
        violations=violations[:5],  # Show only recent 5
        appeals=appeals[:5],  # Show only recent 5
        designs=designs,  # Pass all designs for details view
        stats=stats
    )


@app.route("/admin-dashboard")
def admin_dashboard():
    """Admin dashboard showing only uniform designs"""
    if not require_login():
        return redirect(url_for("login"))

    user = session.get("user")
    if not user:
        print("[ERROR] No user in session, redirecting to login")
        return redirect(url_for("login"))
    
    # Check if user is admin
    if user.get("role", "").lower() != "admin":
        flash("Access denied. Admin access required.", "error")
        return redirect(url_for("dashboard"))
    
    print(f"[ADMIN DASHBOARD] Dashboard loading for admin: {user.get('username', 'unknown')}")

    # Use cached data for uniform designs only
    try:
        designs = get_cached_data("uniform_designs", 20)
        print(f"[STATS] Loaded data - Designs: {len(designs)}")
    except Exception as e:
        print(f"[WARN] Error loading admin dashboard data: {e}")
        # Fallback to empty data
        designs = []

    # Calculate statistics for designs only
    total_designs = len(designs)
    approved_designs = len([d for d in designs if d.get('status') == 'Approved'])
    pending_designs = len([d for d in designs if d.get('status') == 'Under Review' or d.get('status') == 'Pending Review'])
    rejected_designs = len([d for d in designs if d.get('status') == 'Rejected'])

    stats = {
        'total_designs': total_designs,
        'approved_designs': approved_designs,
        'pending_designs': pending_designs,
        'rejected_designs': rejected_designs,
        'approval_rate': round((approved_designs / total_designs * 100) if total_designs > 0 else 0, 1)
    }

    print(f"[OK] Admin dashboard ready for user: {user.get('username', 'unknown')}")
    return render_template(
        "admin_dashboard.html",
        user=user,
        designs=designs,  # Pass all designs
        stats=stats
    )


@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/api/health")
def health_check():
    """Health check endpoint to verify Firebase and other services"""
    health_status = {
        "status": "healthy",
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "services": {}
    }
    
    # Check Firebase connection
    try:
        if firebase_manager.db:
            # Test Firebase by trying to get a document
            test_docs = firebase_manager.get_documents("violations", limit=1)
            health_status["services"]["firebase"] = {
                "status": "connected",
                "message": f"Successfully connected to Firestore. Found {len(test_docs)} test documents."
            }
        else:
            health_status["services"]["firebase"] = {
                "status": "disconnected",
                "message": "Firebase not initialized. Check credentials."
            }
            health_status["status"] = "unhealthy"
    except Exception as e:
        health_status["services"]["firebase"] = {
            "status": "error",
            "message": f"Firebase connection error: {str(e)}"
        }
        health_status["status"] = "unhealthy"
    
    # Check Cloudinary connection
    try:
        from cloudinary_config import cloudinary
        if cloudinary:
            health_status["services"]["cloudinary"] = {
                "status": "connected",
                "message": "Cloudinary configuration loaded successfully."
            }
        else:
            health_status["services"]["cloudinary"] = {
                "status": "disconnected",
                "message": "Cloudinary not configured."
            }
    except Exception as e:
        health_status["services"]["cloudinary"] = {
            "status": "error",
            "message": f"Cloudinary error: {str(e)}"
        }
    
    # Check environment variables
    import os
    env_vars = {
        "FIREBASE_PROJECT_ID": os.getenv("FIREBASE_PROJECT_ID"),
        "FIREBASE_PRIVATE_KEY": "***" if os.getenv("FIREBASE_PRIVATE_KEY") else None,
        "FIREBASE_CLIENT_EMAIL": os.getenv("FIREBASE_CLIENT_EMAIL"),
        "CLOUDINARY_CLOUD_NAME": os.getenv("CLOUDINARY_CLOUD_NAME"),
        "CLOUDINARY_API_KEY": "***" if os.getenv("CLOUDINARY_API_KEY") else None,
        "SECRET_KEY": "***" if os.getenv("SECRET_KEY") else None,
    }
    
    health_status["environment"] = {
        "variables_set": sum(1 for v in env_vars.values() if v is not None),
        "total_variables": len(env_vars),
        "variables": env_vars
    }
    
    # Check cache status
    health_status["cache"] = {
        "entries": len(_cache),
        "status": "active" if _cache else "empty"
    }
    
    return health_status, 200 if health_status["status"] == "healthy" else 500


@app.route("/api/test-violation", methods=["POST"])
def test_violation_creation():
    """Test endpoint to create a violation for debugging Railway deployment"""
    if not session.get("user"):
        return {"error": "Unauthorized"}, 401
    
    try:
        print(f"[TEST] Testing violation creation on Railway")
        
        # Create a test violation
        test_data = {
            "student_name": "Test Student",
            "student_id": "TEST001",
            "violation_type": "Test Violation",
            "course": "Test Grade",
            "description": "This is a test violation for debugging Railway deployment",
            "date": time.strftime('%Y-%m-%d'),
            "reported_by": session.get("user", {}).get("name", "Test User"),
            "severity": "Low",
            "created_timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print(f"[TEST] Test data: {test_data}")
        
        # Check Firebase connection
        if not firebase_manager.db:
            return {"error": "Firebase not connected", "debug": "firebase_not_initialized"}, 500
        
        # Try to add the test violation
        doc_id = add_to_firebase("violations", test_data)
        
        if doc_id:
            print(f"[TEST] Test violation created successfully with ID: {doc_id}")
            return {
                "success": True, 
                "message": "Test violation created successfully",
                "violation_id": doc_id,
                "test_data": test_data
            }, 201
        else:
            print(f"[TEST] Failed to create test violation")
            return {"error": "Failed to create test violation", "debug": "add_to_firebase_returned_none"}, 500
            
    except Exception as e:
        print(f"[TEST] Test violation creation failed: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"Test failed: {str(e)}", "debug": "test_exception"}, 500


# ============ Feature pages ============

@app.route("/violations", methods=["GET", "POST"])
def violations_page():
    if not require_login():
        return redirect(url_for("login"))

    if request.method == "POST":
        data = {
            "student_name": request.form.get("student_name", "").strip(),
            "student_id": request.form.get("student_id", "").strip(),
            "violation_type": request.form.get("violation_type", "").strip(),
            "course": request.form.get("course", "").strip(),
            "date": request.form.get("date", "").strip(),
            "description": request.form.get("description", "").strip(),
            "status": "Pending",  # Will be calculated based on count
            "reported_by": session.get("user", {}).get("name", "Guidance"),
        }
        
        # Determine status based on violation count for this student
        student_name = data.get("student_name", "")
        student_id = data.get("student_id", "")
        if student_name and student_id:
            data["status"] = get_violation_status_by_count(student_name, student_id)
        
        if not data["student_name"] or not data["student_id"] or not data["violation_type"]:
            flash("Student, ID and Type are required", "error")
        else:
            doc_id = add_to_firebase("violations", data)
            if doc_id:
                clear_cache()  # Clear cache when data changes
                flash(f"Violation saved (ID: {doc_id})", "success")
            else:
                flash("Failed to save violation", "error")
        return redirect(url_for("violations_page"))

    # Get violations from both collections
    violations_items = get_from_firebase("violations") or []
    student_violations_items = get_student_violations_from_firebase()
    
    # Merge both collections
    items = violations_items + student_violations_items
    
    # Add document IDs to items for action buttons
    for i, item in enumerate(items):
        if 'id' not in item:
            item['id'] = f"violation_{i}"  # Fallback ID if not available
    
    print(f"[INFO] Total violations displayed: {len(items)} (from violations: {len(violations_items)}, from student_violations: {len(student_violations_items)})")
    return render_template("violations.html", user=session.get("user"), items=items)


@app.route("/violations/view/<violation_id>")
def view_violation(violation_id):
    if not require_login():
        return redirect(url_for("login"))
    
    # Get violation details from Firebase
    violation = search_in_firebase("violations", "id", violation_id)
    if not violation:
        flash("Violation not found", "error")
        return redirect(url_for("violations_page"))
    
    return render_template("violation_details.html", violation=violation[0], user=session.get("user"))


@app.route("/violations/edit/<violation_id>", methods=["GET", "POST"])
def edit_violation(violation_id):
    if not require_login():
        return redirect(url_for("login"))
    
    if request.method == "POST":
        # Update violation data
        data = {
            "student_name": request.form.get("student_name", "").strip(),
            "student_id": request.form.get("student_id", "").strip(),
            "violation_type": request.form.get("violation_type", "").strip(),
            "course": request.form.get("course", "").strip(),
            "date": request.form.get("date", "").strip(),
            "description": request.form.get("description", "").strip(),
            "status": "Pending",  # Will be calculated based on count
            "reported_by": session.get("user", {}).get("name", "Guidance"),
        }
        
        # Determine status based on violation count for this student
        student_name = data.get("student_name", "")
        student_id = data.get("student_id", "")
        if student_name and student_id:
            data["status"] = get_violation_status_by_count(student_name, student_id)
        
        if not data["student_name"] or not data["student_id"] or not data["violation_type"]:
            flash("Student, ID and Type are required", "error")
        else:
            # Update in Firebase
            success = update_violation_in_firebase(violation_id, data)
            if success:
                clear_cache()  # Clear cache when data changes
                flash("Violation updated successfully", "success")
            else:
                flash("Failed to update violation", "error")
        return redirect(url_for("violations_page"))
    
    # Get violation details for editing
    violation = search_in_firebase("violations", "id", violation_id)
    if not violation:
        flash("Violation not found", "error")
        return redirect(url_for("violations_page"))
    
    return render_template("edit_violation.html", violation=violation[0], user=session.get("user"))


@app.route("/violations/delete/<violation_id>", methods=["POST"])
def delete_violation(violation_id):
    if not require_login():
        return redirect(url_for("login"))
    
    # Delete violation from Firebase
    success = delete_violation_from_firebase(violation_id)
    if success:
        clear_cache()  # Clear cache when data changes
        flash("Violation deleted successfully", "success")
    else:
        flash("Failed to delete violation", "error")
    
    return redirect(url_for("violations_page"))


@app.route("/appeals", methods=["GET", "POST"])
def appeals_page():
    if not require_login():
        return redirect(url_for("login"))

    if request.method == "POST":
        data = {
            "student_name": request.form.get("student_name", "").strip(),
            "student_id": request.form.get("student_id", "").strip(),
            "violation_id": request.form.get("violation_id", "").strip(),
            "appeal_date": request.form.get("appeal_date", "").strip(),
            "reason": request.form.get("reason", "").strip(),
            "status": request.form.get("status", "Pending Review"),
            "submitted_by": request.form.get("submitted_by", "").strip(),
            "priority": request.form.get("priority", "Medium"),
        }
        if not data["student_name"] or not data["student_id"] or not data["violation_id"]:
            flash("Student, ID and Violation ID are required", "error")
        else:
            doc_id = add_to_firebase("appeals", data)
            if doc_id:
                clear_cache()  # Clear cache when data changes
                flash(f"Appeal saved (ID: {doc_id})", "success")
            else:
                flash("Failed to save appeal", "error")
        return redirect(url_for("appeals_page"))

    # Get appeals from both collections
    appeals_items = get_from_firebase("appeals") or []
    student_violations_appeals = get_student_violations_as_appeals()
    
    # Merge both collections
    items = appeals_items + student_violations_appeals
    
    # Add document IDs to items for action buttons
    for i, item in enumerate(items):
        if 'id' not in item:
            item['id'] = f"appeal_{i}"  # Fallback ID if not available
    
    print(f"[INFO] Total appeals displayed: {len(items)} (from appeals: {len(appeals_items)}, from student_violations: {len(student_violations_appeals)})")
    return render_template("appeals.html", user=session.get("user"), items=items)


@app.route("/appeals/view/<appeal_id>")
def view_appeal(appeal_id):
    if not require_login():
        return redirect(url_for("login"))
    
    # Get appeal details from Firebase
    appeal = search_in_firebase("appeals", "id", appeal_id)
    if not appeal:
        flash("Appeal not found", "error")
        return redirect(url_for("appeals_page"))
    
    return render_template("appeal_details.html", appeal=appeal[0], user=session.get("user"))


@app.route("/appeals/edit/<appeal_id>", methods=["GET", "POST"])
def edit_appeal(appeal_id):
    if not require_login():
        return redirect(url_for("login"))
    
    if request.method == "POST":
        # Update appeal data
        data = {
            "student_name": request.form.get("student_name", "").strip(),
            "student_id": request.form.get("student_id", "").strip(),
            "violation_id": request.form.get("violation_id", "").strip(),
            "appeal_date": request.form.get("appeal_date", "").strip(),
            "reason": request.form.get("reason", "").strip(),
            "status": request.form.get("status", "Pending Review"),
            "submitted_by": request.form.get("submitted_by", "").strip(),
            "priority": request.form.get("priority", "Medium"),
        }
        
        if not data["student_name"] or not data["student_id"] or not data["violation_id"]:
            flash("Student, ID and Violation ID are required", "error")
        else:
            # Update in Firebase
            success = update_appeal_in_firebase(appeal_id, data)
            if success:
                flash("Appeal updated successfully", "success")
            else:
                flash("Failed to update appeal", "error")
        return redirect(url_for("appeals_page"))
    
    # Get appeal details for editing
    appeal = search_in_firebase("appeals", "id", appeal_id)
    if not appeal:
        flash("Appeal not found", "error")
        return redirect(url_for("appeals_page"))
    
    return render_template("edit_appeal.html", appeal=appeal[0], user=session.get("user"))


@app.route("/appeals/delete/<appeal_id>", methods=["POST"])
def delete_appeal(appeal_id):
    if not require_login():
        return redirect(url_for("login"))
    
    # Delete appeal from Firebase
    success = delete_appeal_from_firebase(appeal_id)
    if success:
        flash("Appeal deleted successfully", "success")
    else:
        flash("Failed to delete appeal", "error")
    
    return redirect(url_for("appeals_page"))


@app.route("/designs", methods=["GET", "POST"])
def designs_page():
    if not require_login():
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        typ = request.form.get("type", "").strip()
        course = request.form.get("course", "").strip()
        colors = request.form.get("colors", "").strip()
        submitted_date = request.form.get("submitted_date", "").strip()
        status = request.form.get("status", "Under Review")
        designer = request.form.get("designer", "").strip()
        description = request.form.get("description", "").strip()

        image_url = ""
        file = request.files.get("image")
        if file and file.filename:
            try:
                suffix = os.path.splitext(file.filename)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    file.save(tmp.name)
                    tmp_path = tmp.name
                
                # Upload to Cloudinary
                public_id = f"design_{name.replace(' ', '_')}_{os.path.basename(tmp_path)}"
                image_url = upload_image_to_cloudinary(tmp_path, public_id)
                
                if not image_url:
                    print("[WARN] Image upload failed - design will be saved without image")
                    flash("Image upload failed - design saved without image", "warning")
            except Exception as e:
                print(f"Error uploading image: {e}")
                image_url = ""
                flash("Error uploading image - design saved without image", "warning")
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        data = {
            "name": name,
            "type": typ,
            "course": course,
            "colors": colors,
            "submitted_date": submitted_date,
            "status": status,
            "designer": designer,
            "description": description,
            "image_url": image_url,
        }
        
        # Perform uniqueness analysis
        uniqueness_analysis = analyze_design_uniqueness(data)
        data["uniqueness_analysis"] = uniqueness_analysis
        if not name or not typ:
            flash("Design name and type are required", "error")
        else:
            doc_id = add_to_firebase("uniform_designs", data)
            if doc_id:
                clear_cache()  # Clear cache when data changes
                analysis_score = uniqueness_analysis['overall_score']
                analysis_assessment = uniqueness_analysis['overall_assessment']
                flash(f"Design saved (ID: {doc_id}) - Uniqueness: {analysis_score}% ({analysis_assessment})", "success")
            else:
                flash("Failed to save design", "error")
        return redirect(url_for("designs_page"))

    items = get_from_firebase("uniform_designs") or []
    # Add document IDs to items for action buttons
    for i, item in enumerate(items):
        if 'id' not in item:
            item['id'] = f"design_{i}"  # Fallback ID if not available
    return render_template("designs.html", user=session.get("user"), items=items)


@app.route("/designs/view/<design_id>")
def view_design(design_id):
    if not require_login():
        return redirect(url_for("login"))
    
    # Get design details from Firebase
    design = search_in_firebase("uniform_designs", "id", design_id)
    if not design:
        flash("Design not found", "error")
        return redirect(url_for("designs_page"))
    
    return render_template("design_details.html", design=design[0], user=session.get("user"))


@app.route("/designs/edit/<design_id>", methods=["GET", "POST"])
def edit_design(design_id):
    if not require_login():
        return redirect(url_for("login"))
    
    if request.method == "POST":
        # Update design data
        name = request.form.get("name", "").strip()
        typ = request.form.get("type", "").strip()
        course = request.form.get("course", "").strip()
        colors = request.form.get("colors", "").strip()
        submitted_date = request.form.get("submitted_date", "").strip()
        status = request.form.get("status", "Under Review")
        designer = request.form.get("designer", "").strip()
        description = request.form.get("description", "").strip()
        
        # Handle image upload if provided
        image_url = ""
        if request.files.get("image"):
            img = request.files["image"]
            if img and img.filename:
                try:
                    # Save to temporary file
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                        img.save(tmp_file.name)
                        tmp_path = tmp_file.name
                    
                    # Upload to Cloudinary
                    public_id = f"design_{design_id}_{int(time.time())}"
                    image_url = upload_image_to_cloudinary(tmp_path, public_id)
                    
                    if not image_url:
                        print("[WARN] Image upload failed - keeping existing image")
                        flash("Image upload failed - keeping existing image", "warning")
                    
                    # Clean up temporary file
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass
                except Exception as e:
                    print(f"Error uploading image: {e}")
                    flash("Error uploading image - keeping existing image", "warning")
        
        data = {
            "name": name,
            "type": typ,
            "course": course,
            "colors": colors,
            "submitted_date": submitted_date,
            "status": status,
            "designer": designer,
            "description": description,
        }
        
        # Only update image_url if a new image was uploaded
        if image_url:
            data["image_url"] = image_url
        
        if not name or not typ:
            flash("Design name and type are required", "error")
        else:
            # Update in Firebase
            success = update_design_in_firebase(design_id, data)
            if success:
                flash("Design updated successfully", "success")
            else:
                flash("Failed to update design", "error")
        return redirect(url_for("designs_page"))
    
    # Get design details for editing
    design = search_in_firebase("uniform_designs", "id", design_id)
    if not design:
        flash("Design not found", "error")
        return redirect(url_for("designs_page"))
    
    return render_template("edit_design.html", design=design[0], user=session.get("user"))


@app.route("/designs/delete/<design_id>", methods=["POST"])
def delete_design(design_id):
    if not require_login():
        return redirect(url_for("login"))
    
    # Delete design from Firebase
    success = delete_design_from_firebase(design_id)
    if success:
        flash("Design deleted successfully", "success")
    else:
        flash("Failed to delete design", "error")
    
    return redirect(url_for("designs_page"))


if __name__ == "__main__":
    import socket
    import os
    
    # Get configuration from environment variables or use defaults
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', os.environ.get('FLASK_PORT', 5000)))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Production mode detection
    is_production = os.environ.get('ENVIRONMENT') == 'production' or os.environ.get('RAILWAY_ENVIRONMENT') == 'production'
    
    # Get local IP address function
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "127.0.0.1"
    
    if is_production:
        # Production settings
        app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')
        debug = False
        print(f"\n[START] AI-niform Server - Production Mode")
        print(f"🌐 Live at: https://your-railway-domain.railway.app")
    else:
        # Development settings
        local_ip = get_local_ip()
        print(f"\n[START] AI-niform Server - Development Mode")
        print(f"[HOST] Host: {host}")
        print(f"[PORT] Port: {port}")
        print(f"[DEBUG] Debug: {debug}")
        print(f"\n[MOBILE] Access URLs:")
        print(f"   Local: http://localhost:{port}")
        print(f"   Network: http://{local_ip}:{port}")
        print(f"\n[TIP] For mobile/tablet access:")
        print(f"   1. Connect device to same WiFi network")
        print(f"   2. Open browser and go to: http://{local_ip}:{port}")
        print(f"\n[TIP] For external internet access:")
        print(f"   1. Configure router port forwarding (port {port})")
        print(f"   2. Use your public IP address")
        print(f"\n[STOP] Press Ctrl+C to stop the server\n")
    
    # Run the server
    app.run(host=host, port=port, debug=debug, threaded=True)

