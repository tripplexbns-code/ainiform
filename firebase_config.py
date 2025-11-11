import firebase_admin
from firebase_admin import credentials, firestore, auth
from firebase_admin import storage as fb_storage
import os
from datetime import datetime
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class FirebaseManager:
    def __init__(self):
        """Initialize Firebase connection"""
        self.db = None
        self.cred = None
        self.app = None
        self.bucket = None
        self.initialize_firebase()
    
    def initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            # Check if Firebase is already initialized
            if not firebase_admin._apps:
                # Try Railway environment variables first
                if self._try_railway_credentials():
                    print("[OK] Firebase initialized with Railway environment variables")
                elif self._try_service_account_file():
                    print("[OK] Firebase initialized with service account key file")
                elif self._try_default_credentials():
                    print("[OK] Firebase initialized with default credentials")
                else:
                    print("[ERROR] Failed to initialize Firebase with any method")
                    return
                
                # Initialize Firestore
                self.db = firestore.client()
                print("[OK] Firestore database connected")
                
                # Initialize Storage bucket
                try:
                    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
                    if not bucket_name:
                        # Try to infer from service account project_id
                        try:
                            if isinstance(self.cred, credentials.Certificate):
                                with open(self.cred._certificate) as f:
                                    sa = json.load(f)
                                    project_id = sa.get("project_id")
                                    if project_id:
                                        bucket_name = f"{project_id}.appspot.com"
                                        print(f"[INFO] Inferred storage bucket from project ID: {bucket_name}")
                        except Exception as e:
                            print(f"[WARN] Could not infer bucket name from service account: {e}")
                            bucket_name = None
                    
                    if bucket_name:
                        try:
                            self.bucket = fb_storage.bucket(bucket_name)
                            # Test access by building a blob (no network call here)
                            _ = self.bucket.blob("test.txt")
                            print(f"[OK] Storage bucket configured: {bucket_name}")
                        except Exception as storage_error:
                            print(f"[WARN] Storage bucket '{bucket_name}' exists but is not accessible: {storage_error}")
                            print("[TIP] This might be due to:")
                            print("   - Storage not enabled in Firebase Console")
                            print("   - Insufficient permissions")
                            print("   - Billing plan limitations (Storage requires Blaze plan)")
                            print("   - Network connectivity issues")
                            self.bucket = None
                    else:
                        print("[WARN] Storage bucket not configured.")
                        print("[TIP] To fix this:")
                        print("   1. Set FIREBASE_STORAGE_BUCKET environment variable")
                        print("   2. Or create a .env file with: FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com")
                        print("   3. Note: Firebase Storage requires a Blaze (paid) billing plan")
                        self.bucket = None
                except Exception as e:
                    print(f"[WARN] Failed to configure Storage bucket: {e}")
                    print("[TIP] Storage will be disabled. Images will use Cloudinary instead.")
                    self.bucket = None
                
            else:
                # Use existing app
                self.app = firebase_admin.get_app()
                self.db = firestore.client()
                print("[OK] Using existing Firebase app")
                try:
                    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
                    if not bucket_name:
                        # Try to infer from service account project_id
                        try:
                            if isinstance(self.cred, credentials.Certificate):
                                with open(self.cred._certificate) as f:
                                    sa = json.load(f)
                                    project_id = sa.get("project_id")
                                    if project_id:
                                        bucket_name = f"{project_id}.appspot.com"
                                        print(f"[INFO] Inferred storage bucket from project ID: {bucket_name}")
                        except Exception as e:
                            print(f"[WARN] Could not infer bucket name from service account: {e}")
                            bucket_name = None
                    
                    if bucket_name:
                        self.bucket = fb_storage.bucket(bucket_name)
                        print(f"[OK] Storage bucket configured: {bucket_name}")
                    else:
                        self.bucket = None
                        print("[WARN] Storage bucket not configured")
                except Exception as e:
                    print(f"[WARN] Storage bucket not accessible: {e}")
                    self.bucket = None
                
        except Exception as e:
            print(f"[ERROR] Firebase initialization failed: {e}")
            print("📋 Please ensure you have:")
            print("   1. Installed firebase-admin: pip install firebase-admin")
            print("   2. Set up Firebase project in Firebase Console")
            print("   3. Downloaded serviceAccountKey.json or set GOOGLE_APPLICATION_CREDENTIALS")
            print("   4. For Railway: Set Firebase environment variables in Railway dashboard")
            self.db = None
    
    def _try_railway_credentials(self):
        """Try to initialize Firebase using Railway environment variables"""
        try:
            project_id = os.getenv("FIREBASE_PROJECT_ID")
            private_key_id = os.getenv("FIREBASE_PRIVATE_KEY_ID")
            private_key = os.getenv("FIREBASE_PRIVATE_KEY")
            client_email = os.getenv("FIREBASE_CLIENT_EMAIL")
            client_id = os.getenv("FIREBASE_CLIENT_ID")
            auth_uri = os.getenv("FIREBASE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth")
            token_uri = os.getenv("FIREBASE_TOKEN_URI", "https://oauth2.googleapis.com/token")
            auth_provider_x509_cert_url = os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL", "https://www.googleapis.com/oauth2/v1/certs")
            client_x509_cert_url = os.getenv("FIREBASE_CLIENT_X509_CERT_URL")
            
            if not all([project_id, private_key_id, private_key, client_email, client_id]):
                print("[DEBUG] Railway Firebase environment variables not complete")
                return False
            
            # Fix private key formatting (Railway might strip newlines)
            if private_key and "\\n" in private_key:
                private_key = private_key.replace("\\n", "\n")
            
            service_account_info = {
                "type": "service_account",
                "project_id": project_id,
                "private_key_id": private_key_id,
                "private_key": private_key,
                "client_email": client_email,
                "client_id": client_id,
                "auth_uri": auth_uri,
                "token_uri": token_uri,
                "auth_provider_x509_cert_url": auth_provider_x509_cert_url,
                "client_x509_cert_url": client_x509_cert_url
            }
            
            self.cred = credentials.Certificate(service_account_info)
            self.app = firebase_admin.initialize_app(self.cred)
            print(f"[DEBUG] Railway Firebase credentials loaded for project: {project_id}")
            return True
            
        except Exception as e:
            print(f"[DEBUG] Railway credentials failed: {e}")
            return False
    
    def _try_service_account_file(self):
        """Try to initialize Firebase using service account key file"""
        try:
            service_account_path = "ServiceAccountKey.json"
            
            if os.path.exists(service_account_path):
                self.cred = credentials.Certificate(service_account_path)
                self.app = firebase_admin.initialize_app(self.cred)
                print(f"[DEBUG] Service account file loaded: {service_account_path}")
                return True
            else:
                print("[DEBUG] ServiceAccountKey.json file not found")
                return False
                
        except Exception as e:
            print(f"[DEBUG] Service account file failed: {e}")
            return False
    
    def _try_default_credentials(self):
        """Try to initialize Firebase using default credentials"""
        try:
            self.app = firebase_admin.initialize_app()
            print("[DEBUG] Default credentials loaded")
            return True
        except Exception as e:
            print(f"[DEBUG] Default credentials failed: {e}")
            return False
    
    def get_collection(self, collection_name):
        """Get a Firestore collection reference"""
        if self.db:
            return self.db.collection(collection_name)
        return None

    def upload_file_to_storage(self, local_path: str, destination_path: str, make_public: bool = True) -> str:
        """Upload a local file to Firebase Storage and return its public URL.

        Returns empty string on failure.
        """
        try:
            if not self.bucket:
                print("[WARN] Firebase Storage not available. Using Cloudinary for image uploads.")
                print("[TIP] To enable Firebase Storage:")
                print("   1. Set FIREBASE_STORAGE_BUCKET environment variable")
                print("   2. Enable Storage in Firebase Console")
                print("   3. Upgrade to Blaze (paid) billing plan if needed")
                return ""
            if not os.path.exists(local_path):
                print(f"[ERROR] Local file not found: {local_path}")
                return ""
            blob = self.bucket.blob(destination_path)
            blob.upload_from_filename(local_path)
            if make_public:
                try:
                    blob.make_public()
                except Exception:
                    # If make_public fails due to rules, fall back to signed URL
                    pass
            url = getattr(blob, 'public_url', None)
            if not url:
                # Fallback signed URL (1 year)
                try:
                    url = blob.generate_signed_url(expiration=60*60*24*365)
                except Exception:
                    url = ""
            print(f"[OK] Uploaded to Storage: gs://{self.bucket.name}/{destination_path}")
            return str(url)
        except Exception as e:
            if "billing" in str(e).lower() or "upgrade" in str(e).lower():
                print(f"[ERROR] Storage upload failed: {e}")
                print("[TIP] To use Firebase Storage, upgrade to Blaze (paid) billing plan in Firebase Console")
                print("   https://console.firebase.google.com/project/_/usage/details")
            else:
                print(f"[ERROR] Storage upload failed: {e}")
            return ""
    
    def add_document(self, collection_name, data):
        """Add a document to Firestore"""
        try:
            if self.db:
                # Add timestamp
                data['created_at'] = datetime.now()
                data['updated_at'] = datetime.now()
                
                # Add document to collection
                doc_ref = self.db.collection(collection_name).add(data)
                print(f"[OK] Document added to {collection_name} with ID: {doc_ref[1].id}")
                return doc_ref[1].id
            else:
                print("[ERROR] Firebase not initialized")
                return None
        except Exception as e:
            print(f"[ERROR] Error adding document: {e}")
            return None
    
    def get_documents(self, collection_name, limit=100):
        """Get documents from Firestore collection with timeout"""
        try:
            if self.db:
                print(f"[INFO] Querying {collection_name} collection...")
                docs = self.db.collection(collection_name).limit(limit).stream()
                documents = []
                count = 0
                for doc in docs:
                    doc_data = doc.to_dict()
                    doc_data['id'] = doc.id
                    documents.append(doc_data)
                    count += 1
                    if count >= limit:
                        break
                print(f"[OK] Retrieved {len(documents)} documents from {collection_name}")
                return documents
            else:
                print("[ERROR] Firebase not initialized")
                return []
        except Exception as e:
            print(f"[ERROR] Error getting documents from {collection_name}: {e}")
            return []
    
    def update_document(self, collection_name, doc_id, data):
        """Update a document in Firestore"""
        try:
            if self.db:
                # Add update timestamp
                data['updated_at'] = datetime.now()
                
                # Update document
                doc_ref = self.db.collection(collection_name).document(doc_id)
                doc_ref.update(data)
                print(f"[OK] Document {doc_id} updated in {collection_name}")
                return True
            else:
                print("[ERROR] Firebase not initialized")
                return False
        except Exception as e:
            print(f"[ERROR] Error updating document: {e}")
            return False
    
    def delete_document(self, collection_name, doc_id):
        """Delete a document from Firestore"""
        try:
            if self.db:
                doc_ref = self.db.collection(collection_name).document(doc_id)
                doc_ref.delete()
                print(f"[OK] Document {doc_id} deleted from {collection_name}")
                return True
            else:
                print("[ERROR] Firebase not initialized")
                return False
        except Exception as e:
            print(f"[ERROR] Error deleting document: {e}")
            return False
    
    def search_documents(self, collection_name, field, value, limit=100):
        """Search documents by field value"""
        try:
            if self.db:
                docs = self.db.collection(collection_name).where(field, "==", value).limit(limit).stream()
                documents = []
                for doc in docs:
                    doc_data = doc.to_dict()
                    doc_data['id'] = doc.id
                    documents.append(doc_data)
                return documents
            else:
                print("[ERROR] Firebase not initialized")
                return []
        except Exception as e:
            print(f"[ERROR] Error searching documents: {e}")
            return []
    
    def get_subcollection_documents(self, collection_name, doc_id, subcollection_name, limit=100):
        """Get documents from a subcollection"""
        try:
            if self.db:
                print(f"[INFO] Querying {collection_name}/{doc_id}/{subcollection_name} subcollection...")
                docs = self.db.collection(collection_name).document(doc_id).collection(subcollection_name).limit(limit).stream()
                documents = []
                count = 0
                for doc in docs:
                    doc_data = doc.to_dict()
                    doc_data['id'] = doc.id
                    doc_data['parent_doc_id'] = doc_id  # Store parent document ID for reference
                    documents.append(doc_data)
                    count += 1
                    if count >= limit:
                        break
                print(f"[OK] Retrieved {len(documents)} documents from {collection_name}/{doc_id}/{subcollection_name}")
                return documents
            else:
                print("[ERROR] Firebase not initialized")
                return []
        except Exception as e:
            print(f"[ERROR] Error getting subcollection documents: {e}")
            return []
    
    def get_all_subcollection_documents(self, collection_name, subcollection_name, limit=100):
        """Get all documents from a subcollection across all parent documents"""
        try:
            if self.db:
                print(f"[INFO] Querying all {subcollection_name} subcollections under {collection_name}...")
                all_documents = []
                
                # Get all parent documents
                parent_docs = self.db.collection(collection_name).limit(limit).stream()
                
                for parent_doc in parent_docs:
                    parent_id = parent_doc.id
                    parent_data = parent_doc.to_dict()
                    
                    # Get subcollection documents for this parent
                    subcollection_docs = self.db.collection(collection_name).document(parent_id).collection(subcollection_name).stream()
                    
                    for doc in subcollection_docs:
                        doc_data = doc.to_dict()
                        doc_data['id'] = doc.id
                        doc_data['parent_doc_id'] = parent_id
                        # Include parent document data for reference
                        if parent_data:
                            doc_data['student_name'] = parent_data.get('name') or parent_data.get('student_name', 'N/A')
                            doc_data['student_id'] = parent_data.get('student_id', 'N/A')
                        all_documents.append(doc_data)
                
                print(f"[OK] Retrieved {len(all_documents)} documents from all {subcollection_name} subcollections")
                return all_documents
            else:
                print("[ERROR] Firebase not initialized")
                return []
        except Exception as e:
            print(f"[ERROR] Error getting all subcollection documents: {e}")
            return []
    
    def delete_subcollection_document(self, collection_name, doc_id, subcollection_name, subcollection_doc_id):
        """Delete a document from a subcollection"""
        try:
            if self.db:
                doc_ref = self.db.collection(collection_name).document(doc_id).collection(subcollection_name).document(subcollection_doc_id)
                doc_ref.delete()
                print(f"[OK] Document {subcollection_doc_id} deleted from {collection_name}/{doc_id}/{subcollection_name}")
                return True
            else:
                print("[ERROR] Firebase not initialized")
                return False
        except Exception as e:
            print(f"[ERROR] Error deleting subcollection document: {e}")
            return False
    
    def authenticate_user(self, username, password):
        """Authenticate user with Firebase Auth (placeholder for now)"""
        try:
            if self.db:
                # For now, check against Firestore users collection
                # In production, use Firebase Auth
                users = self.search_documents('users', 'username', username)
                if users:
                    user = users[0]
                    # In production, verify password hash
                    if user.get('password_hash') == password:  # Simplified for demo
                        return user
                return None
            else:
                print("[ERROR] Firebase not initialized")
                return None
        except Exception as e:
            print(f"[ERROR] Authentication error: {e}")
            return None

# Global Firebase manager instance
firebase_manager = FirebaseManager()

# Helper functions for easy access
def get_firebase_db():
    """Get Firestore database instance"""
    return firebase_manager.db

def add_to_firebase(collection, data):
    """Add data to Firebase collection"""
    return firebase_manager.add_document(collection, data)

def get_from_firebase(collection, limit=100):
    """Get data from Firebase collection"""
    return firebase_manager.get_documents(collection, limit)

def update_in_firebase(collection, doc_id, data):
    """Update data in Firebase collection"""
    return firebase_manager.update_document(collection, doc_id, data)

def delete_from_firebase(collection, doc_id):
    """Delete data from Firebase collection"""
    return firebase_manager.delete_document(collection, doc_id)

def search_in_firebase(collection, field, value, limit=100):
    """Search data in Firebase collection"""
    return firebase_manager.search_documents(collection, field, value, limit)

def get_from_subcollection(collection_name, doc_id, subcollection_name, limit=100):
    """Get data from Firebase subcollection"""
    return firebase_manager.get_subcollection_documents(collection_name, doc_id, subcollection_name, limit)

def get_all_from_subcollection(collection_name, subcollection_name, limit=100):
    """Get all data from a subcollection across all parent documents"""
    return firebase_manager.get_all_subcollection_documents(collection_name, subcollection_name, limit)

def delete_from_subcollection(collection_name, doc_id, subcollection_name, subcollection_doc_id):
    """Delete data from Firebase subcollection"""
    return firebase_manager.delete_subcollection_document(collection_name, doc_id, subcollection_name, subcollection_doc_id)

def upload_to_storage(local_path: str, destination_path: str, make_public: bool = True) -> str:
    """Helper to upload a local file to Firebase Storage and return its URL."""
    return firebase_manager.upload_file_to_storage(local_path, destination_path, make_public)

# Test function
if __name__ == "__main__":
    print("🔥 Testing Firebase Configuration")
    print("=" * 40)
    
    # Test Firebase connection
    if firebase_manager.db:
        print("[OK] Firebase connection successful!")
        
        # Test adding a document
        test_data = {
            'name': 'Test Document',
            'description': 'This is a test document',
            'timestamp': datetime.now()
        }
        
        doc_id = add_to_firebase('test_collection', test_data)
        if doc_id:
            print(f"[OK] Test document added with ID: {doc_id}")
            
            # Test getting documents
            docs = get_from_firebase('test_collection')
            print(f"[OK] Retrieved {len(docs)} documents")
            
            # Test updating document
            update_data = {'description': 'Updated description'}
            if update_in_firebase('test_collection', doc_id, update_data):
                print("[OK] Document updated successfully")
            
            # Test deleting document
            if delete_from_firebase('test_collection', doc_id):
                print("[OK] Document deleted successfully")
        
    else:
        print("[ERROR] Firebase connection failed!")
        print("\n📋 Setup Instructions:")
        print("1. Create a Firebase project at https://console.firebase.google.com/")
        print("2. Enable Firestore Database")
        print("3. Download serviceAccountKey.json")
        print("4. Place it in the project directory")
        print("5. Install firebase-admin: pip install firebase-admin")

