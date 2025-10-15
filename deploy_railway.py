#!/usr/bin/env python3
"""
Railway Deployment Helper Script
This script helps prepare your application for Railway deployment
"""

import os
import json
import sys
from pathlib import Path

def check_required_files():
    """Check if all required files exist"""
    required_files = [
        'web_server.py',
        'requirements.txt',
        'runtime.txt',
        'railway.json',
        'firebase_config.py',
        'cloudinary_config.py'
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print("❌ Missing required files:")
        for file in missing_files:
            print(f"   - {file}")
        return False
    
    print("✅ All required files present")
    return True

def check_environment_variables():
    """Check if environment variables are documented"""
    env_file = Path('RAILWAY_DEPLOYMENT.md')
    if not env_file.exists():
        print("❌ RAILWAY_DEPLOYMENT.md not found")
        return False
    
    print("✅ Environment variables documentation found")
    return True

def validate_railway_config():
    """Validate railway.json configuration"""
    try:
        with open('railway.json', 'r') as f:
            config = json.load(f)
        
        required_keys = ['build', 'deploy']
        for key in required_keys:
            if key not in config:
                print(f"❌ Missing '{key}' in railway.json")
                return False
        
        print("✅ railway.json configuration is valid")
        return True
    except Exception as e:
        print(f"❌ Error validating railway.json: {e}")
        return False

def check_requirements():
    """Check requirements.txt for essential packages"""
    try:
        with open('requirements.txt', 'r') as f:
            requirements = f.read()
        
        essential_packages = ['Flask', 'firebase-admin', 'cloudinary', 'gunicorn']
        missing_packages = []
        
        for package in essential_packages:
            if package.lower() not in requirements.lower():
                missing_packages.append(package)
        
        if missing_packages:
            print(f"❌ Missing essential packages: {', '.join(missing_packages)}")
            return False
        
        print("✅ All essential packages present in requirements.txt")
        return True
    except Exception as e:
        print(f"❌ Error checking requirements.txt: {e}")
        return False

def main():
    """Main deployment check"""
    print("🚀 Railway Deployment Check")
    print("=" * 40)
    
    checks = [
        ("Required Files", check_required_files),
        ("Environment Variables", check_environment_variables),
        ("Railway Configuration", validate_railway_config),
        ("Requirements", check_requirements)
    ]
    
    all_passed = True
    for check_name, check_func in checks:
        print(f"\n📋 {check_name}:")
        if not check_func():
            all_passed = False
    
    print("\n" + "=" * 40)
    if all_passed:
        print("✅ All checks passed! Your app is ready for Railway deployment.")
        print("\nNext steps:")
        print("1. Push your code to GitHub")
        print("2. Connect your repository to Railway")
        print("3. Set up environment variables in Railway dashboard")
        print("4. Deploy!")
    else:
        print("❌ Some checks failed. Please fix the issues above before deploying.")
        sys.exit(1)

if __name__ == "__main__":
    main()
