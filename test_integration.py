#!/usr/bin/env python3
"""
Test script to verify detection.py integration with Final guard_ui_2.py
"""

def test_detection_service_import():
    """Test if detection service can be imported"""
    try:
        from detection import get_detection_service, UniformDetectionService
        print("✅ Detection service import: SUCCESS")
        return True
    except Exception as e:
        print(f"❌ Detection service import: FAILED - {e}")
        return False

def test_detection_service_creation():
    """Test if detection service can be created"""
    try:
        from detection import UniformDetectionService
        
        # Test with male model
        male_service = UniformDetectionService("bsba male2.pt", 0.65)
        print("✅ Male model service creation: SUCCESS")
        
        # Test with female model
        female_service = UniformDetectionService("bsba_female.pt", 0.65)
        print("✅ Female model service creation: SUCCESS")
        
        return True
    except Exception as e:
        print(f"❌ Detection service creation: FAILED - {e}")
        return False

def test_model_files():
    """Test if model files exist"""
    import os
    
    models = ["bsba male2.pt", "bsba_female.pt", "bsba_male.pt"]
    all_exist = True
    
    for model in models:
        if os.path.exists(model):
            print(f"✅ Model file {model}: EXISTS")
        else:
            print(f"❌ Model file {model}: MISSING")
            all_exist = False
    
    return all_exist

def main():
    """Run all integration tests"""
    print("🧪 Testing Detection Service Integration")
    print("=" * 50)
    
    tests = [
        ("Detection Service Import", test_detection_service_import),
        ("Detection Service Creation", test_detection_service_creation),
        ("Model Files Check", test_model_files)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing: {test_name}")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed!")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed! Integration should work correctly.")
        print("\n💡 You can now run Final guard_ui_2.py and it will use detection.py")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
    
    return passed == total

if __name__ == "__main__":
    main()


