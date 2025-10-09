#!/usr/bin/env python3
"""Start the AI Uniform Web Server"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("🚀 Starting AI Uniform Web Server...")
    print("=" * 50)
    
    # Import and run the web server
    from web_server import app
    import socket
    
    # Get configuration
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', os.environ.get('FLASK_PORT', 5000)))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Get local IP address
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return "127.0.0.1"
    
    local_ip = get_local_ip()
    
    print(f"📡 Host: {host}")
    print(f"🔌 Port: {port}")
    print(f"🐛 Debug: {debug}")
    print(f"\n📱 Access URLs:")
    print(f"   Local: http://localhost:{port}")
    print(f"   Network: http://{local_ip}:{port}")
    print(f"\n💡 For mobile/tablet access:")
    print(f"   1. Connect device to same WiFi network")
    print(f"   2. Open browser and go to: http://{local_ip}:{port}")
    print(f"\n🔑 Login Credentials:")
    print(f"   Username: guidance1 | Password: guidance123")
    print(f"   Username: guidance2 | Password: guidance123")
    print(f"   Username: admin1    | Password: guidance123")
    print(f"\n🛑 Press Ctrl+C to stop the server\n")
    
    # Run the server
    app.run(host=host, port=port, debug=debug, threaded=True)
    
except Exception as e:
    print(f"❌ Error starting server: {e}")
    print("\n📋 Troubleshooting:")
    print("1. Make sure you're in the correct directory")
    print("2. Check that all dependencies are installed: pip install -r requirements.txt")
    print("3. Verify Firebase configuration")
    sys.exit(1)


