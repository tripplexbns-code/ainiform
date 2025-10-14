import os
import json
from firebase_admin import credentials, initialize_app, firestore, storage

def initialize_firebase():
    """Initialize Firebase with environment variables or service account key"""
    try:
        # Try to get Firebase config from environment variables first
        if os.environ.get('FIREBASE_PROJECT_ID'):
            # Use environment variables for Firebase config
            cred = credentials.ApplicationDefault()
            initialize_app(cred, {
                'projectId': os.environ.get('FIREBASE_PROJECT_ID'),
                'storageBucket': os.environ.get('FIREBASE_STORAGE_BUCKET')
            })
            print("[OK] Firebase initialized with environment variables")
        else:
            # Fallback to service account key file
            if os.path.exists('ServiceAccountKey.json'):
                cred = credentials.Certificate('ServiceAccountKey.json')
                initialize_app(cred)
                print("[OK] Firebase initialized with service account key")
            else:
                print("[ERROR] No Firebase configuration found")
                return False
        
        # Initialize Firestore
        db = firestore.client()
        print("[OK] Firestore database connected")
        
        # Initialize Storage
        try:
            bucket = storage.bucket()
            print("[OK] Firebase Storage connected")
        except Exception as e:
            print(f"[WARN] Storage bucket not configured: {e}")
            print("[TIP] Set FIREBASE_STORAGE_BUCKET environment variable")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Firebase initialization failed: {e}")
        return False

# Initialize Firebase when module is imported
if not initialize_firebase():
    print("[WARN] Firebase not initialized - some features may not work")
