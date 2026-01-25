#!/usr/bin/env python3
"""
Start the Trident Emergency Response System server
"""

import subprocess
import sys
import time
import os

def start_server():
    """Start the Flask server"""
    print("🚀 Starting Trident Emergency Response System...")
    print("=" * 50)
    
    # Check if app.py exists
    if not os.path.exists('app.py'):
        print("❌ Error: app.py not found!")
        return False
    
    try:
        # Start the Flask app
        print("📡 Starting Flask server on http://localhost:5000")
        print("📊 Dashboard: http://localhost:5000/dashboard")
        print("📈 Analytics: http://localhost:5000/analytics")
        print("🏠 Home: http://localhost:5000")
        print()
        print("Press Ctrl+C to stop the server")
        print("=" * 50)
        
        # Run the Flask app
        subprocess.run([sys.executable, 'app.py'], check=True)
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error starting server: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    start_server()
