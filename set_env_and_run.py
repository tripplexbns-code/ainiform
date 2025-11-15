#!/usr/bin/env python3
"""
Script to set environment variables and run the AI-niform web server.
This fixes the "storage bucket not configured" error.
"""

import os
import sys
import subprocess

def set_environment_variables():
    """Set the required environment variables for Firebase Storage"""
    print("[SETUP] Setting up environment variables...")
    
    # Set Firebase Storage bucket
    os.environ['FIREBASE_STORAGE_BUCKET'] = 'ainiform-45224.appspot.com'
    print("[OK] FIREBASE_STORAGE_BUCKET set to: ainiform-45224.appspot.com")
    
    # Set other optional variables if not already set
    if not os.environ.get('FIREBASE_PROJECT_ID'):
        os.environ['FIREBASE_PROJECT_ID'] = 'ainiform-45224'
        print("[OK] FIREBASE_PROJECT_ID set to: ainiform-45224")
    
    # Set Flask secret key if not set
    if not os.environ.get('SECRET_KEY'):
        os.environ['SECRET_KEY'] = 'ainiform-secret-key-2024'
        print("[OK] SECRET_KEY set")
    
    print("[SUCCESS] Environment variables configured successfully!")
    print("[TIP] The 'storage bucket not configured' error should now be resolved.")

def run_server():
    """Run the web server"""
    print("\n[START] Starting AI-niform web server...")
    try:
        # Import and run the web server
        from web_server import app
        app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
    except KeyboardInterrupt:
        print("\n[STOP] Server stopped by user")
    except Exception as e:
        print(f"[ERROR] Error running server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("=" * 50)
    print("[SETUP] AI-niform Environment Setup & Server")
    print("=" * 50)
    
    # Set environment variables
    set_environment_variables()
    
    # Run the server
    run_server()
