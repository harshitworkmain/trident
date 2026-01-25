#!/usr/bin/env python3
"""
Simple server status test
"""

import requests
import time

def test_server():
    try:
        print("🔄 Testing server connection...")
        
        # Test basic connection
        response = requests.get('http://localhost:5000/', timeout=5)
        print(f"✅ Basic connection works - Status: {response.status_code}")
        
        # Test status distribution endpoint
        status_response = requests.get('http://localhost:5000/api/analytics/status-distribution', timeout=5)
        print(f"✅ Status API endpoint - Status: {status_response.status_code}")
        print(f"📊 Response: {status_response.text}")
        
        # Test emergency types endpoint  
        emergency_response = requests.get('http://localhost:5000/api/analytics/emergency-types', timeout=5)
        print(f"✅ Emergency API endpoint - Status: {emergency_response.status_code}")
        print(f"📊 Response: {emergency_response.text}")
        
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection failed: {e}")
    except requests.exceptions.Timeout as e:
        print(f"⏰ Timeout: {e}")
    except Exception as e:
        print(f"💥 Error: {e}")

if __name__ == "__main__":
    test_server()