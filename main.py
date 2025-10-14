from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import timedelta
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ainiform-secret-key-2024')
app.permanent_session_lifetime = timedelta(hours=8)

# Mock data
MOCK_VIOLATIONS = [
    {"id": "1", "student_name": "John Doe", "student_id": "ST001", "violation_type": "Improper Uniform", "status": "Warning"},
    {"id": "2", "student_name": "Jane Smith", "student_id": "ST002", "violation_type": "Missing ID", "status": "Advisory"},
    {"id": "3", "student_name": "Mike Johnson", "student_id": "ST003", "violation_type": "Wrong Shoes", "status": "Guidance"}
]

MOCK_APPEALS = [
    {"id": "1", "student_name": "John Doe", "status": "Pending Review", "reason": "Uniform was damaged during PE class"},
    {"id": "2", "student_name": "Sarah Wilson", "status": "Approved", "reason": "Medical condition requires different attire"}
]

MOCK_DESIGNS = [
    {"id": "1", "name": "Standard Uniform", "type": "Complete Set", "status": "Approved", "components": ["Shirt", "Pants", "Belt"]},
    {"id": "2", "name": "PE Uniform", "type": "Sports Wear", "status": "Pending", "components": ["T-shirt", "Shorts", "Sneakers"]}
]

@app.route("/")
def root():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        if username == "guidance1" and password == "guidance123":
            session["user"] = {
                "username": username,
                "name": "Guidance Counselor",
                "role": "guidance"
            }
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "error")
    
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    
    user = session.get("user")
    
    return render_template(
        "guidance_dashboard.html",
        user=user,
        violations=MOCK_VIOLATIONS,
        appeals=MOCK_APPEALS,
        designs=MOCK_DESIGNS,
        stats={
            'total_violations': len(MOCK_VIOLATIONS),
            'total_appeals': len(MOCK_APPEALS),
            'total_designs': len(MOCK_DESIGNS),
            'approved_designs': len([d for d in MOCK_DESIGNS if d.get('status') == 'Approved'])
        }
    )

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

# API endpoints
@app.route("/api/violations", methods=["GET"])
def api_violations():
    return {"success": True, "data": MOCK_VIOLATIONS}

@app.route("/api/violations/<violation_id>", methods=["DELETE"])
def api_delete_violation(violation_id):
    global MOCK_VIOLATIONS
    MOCK_VIOLATIONS = [v for v in MOCK_VIOLATIONS if v.get('id') != violation_id]
    return {"success": True, "message": "Violation deleted"}

@app.route("/api/appeals", methods=["GET"])
def api_appeals():
    return {"success": True, "data": MOCK_APPEALS}

@app.route("/api/designs", methods=["GET"])
def api_designs():
    return {"success": True, "data": MOCK_DESIGNS}

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
