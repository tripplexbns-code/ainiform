#!/usr/bin/env python3
"""
Cloudinary Test Script
This script helps you test your Cloudinary configuration
"""

import os
from cloudinary_config import configure_cloudinary, upload_image_to_cloudinary
from dotenv import load_dotenv

def test_cloudinary_setup():
    """Test Cloudinary configuration and upload functionality"""
    print("🧪 Testing Cloudinary Configuration")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("💡 Create a .env file with your Cloudinary credentials")
        print("   See CLOUDINARY_SETUP.md for instructions")
        return False
    
    # Check environment variables
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    api_key = os.getenv('CLOUDINARY_API_KEY')
    api_secret = os.getenv('CLOUDINARY_API_SECRET')
    
    print(f"📋 Environment Variables:")
    print(f"   CLOUDINARY_CLOUD_NAME: {'✅ Set' if cloud_name else '❌ Missing'}")
    print(f"   CLOUDINARY_API_KEY: {'✅ Set' if api_key else '❌ Missing'}")
    print(f"   CLOUDINARY_API_SECRET: {'✅ Set' if api_secret else '❌ Missing'}")
    
    if not all([cloud_name, api_key, api_secret]):
        print("\n❌ Missing required credentials!")
        print("💡 Update your .env file with the correct values")
        return False
    
    # Test configuration
    print(f"\n🔧 Testing Cloudinary configuration...")
    config_result = configure_cloudinary()
    
    if not config_result:
        print("❌ Cloudinary configuration failed!")
        return False
    
    print("✅ Cloudinary configured successfully!")
    
    # Test upload with a sample image (if available)
    print(f"\n📤 Testing image upload...")
    
    # Create a simple test image
    try:
        from PIL import Image
        import tempfile
        
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            img.save(tmp.name)
            test_image_path = tmp.name
        
        print(f"   Created test image: {test_image_path}")
        
        # Test upload
        upload_result = upload_image_to_cloudinary(test_image_path, "test_upload")
        
        if upload_result:
            print(f"✅ Image upload successful!")
            print(f"   URL: {upload_result}")
            
            # Clean up test image
            os.unlink(test_image_path)
            return True
        else:
            print("❌ Image upload failed!")
            return False
            
    except ImportError:
        print("⚠️  PIL not available - skipping upload test")
        print("💡 Install Pillow: pip install Pillow")
        return True
    except Exception as e:
        print(f"❌ Upload test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Cloudinary Setup Test")
    print("=" * 50)
    
    success = test_cloudinary_setup()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed! Your Cloudinary setup is working correctly.")
        print("💡 You can now upload images in your web application.")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        print("💡 See CLOUDINARY_SETUP.md for detailed setup instructions.")
    
    return success

if __name__ == "__main__":
    main()
