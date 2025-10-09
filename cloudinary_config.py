import cloudinary
import cloudinary.uploader
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def configure_cloudinary():
    """Configure Cloudinary with API credentials"""
    try:
        cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
        api_key = os.getenv('CLOUDINARY_API_KEY')
        api_secret = os.getenv('CLOUDINARY_API_SECRET')
        
        # Check if all required credentials are provided
        if not all([cloud_name, api_key, api_secret]):
            print("[WARN] Cloudinary credentials not fully configured.")
            print("[TIP] To enable image uploads, set the following environment variables:")
            print("   - CLOUDINARY_CLOUD_NAME")
            print("   - CLOUDINARY_API_KEY")
            print("   - CLOUDINARY_API_SECRET")
            print("   Or create a .env file with these values")
            return False
        
        # Check for placeholder values
        if any(cred in ['your_cloud_name', 'your_api_key', 'your_api_secret'] for cred in [cloud_name, api_key, api_secret]):
            print("[WARN] Cloudinary credentials contain placeholder values.")
            print("[TIP] Please update with your actual Cloudinary credentials.")
            return False
        
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
        print("[OK] Cloudinary configured successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Cloudinary configuration failed: {e}")
        print("[TIP] Please set the following environment variables:")
        print("   - CLOUDINARY_CLOUD_NAME")
        print("   - CLOUDINARY_API_KEY")
        print("   - CLOUDINARY_API_SECRET")
        return False

def upload_image_to_cloudinary(image_path, public_id=None):
    """Upload an image to Cloudinary and return the URL"""
    try:
        if not os.path.exists(image_path):
            print(f"[ERROR] Image file not found: {image_path}")
            return ""
        
        # Configure Cloudinary if not already configured
        if not hasattr(cloudinary.config(), 'cloud_name') or not cloudinary.config().cloud_name:
            if not configure_cloudinary():
                print("[WARN] Image upload skipped - Cloudinary not configured")
                return ""
        
        # Upload image
        result = cloudinary.uploader.upload(
            image_path,
            public_id=public_id,
            folder="uniform_designs",
            resource_type="image"
        )
        
        if result and 'secure_url' in result:
            print(f"[OK] Image uploaded successfully: {result['secure_url']}")
            return result['secure_url']
        else:
            print("[ERROR] Upload failed - no URL returned")
            return ""
            
    except Exception as e:
        print(f"[ERROR] Error uploading image to Cloudinary: {e}")
        print("[TIP] Image upload will be skipped. Configure Cloudinary to enable image uploads.")
        return ""

# Initialize Cloudinary configuration
configure_cloudinary()
