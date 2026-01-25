#!/usr/bin/env python3
"""
Test script to verify API endpoints are working
"""

import requests
import json
import time

def test_api_endpoints():
    base_url = "http://localhost:5000"
    
    print("Testing Trident Emergency Response System API...")
    print("=" * 50)
    
    # Test endpoints
    endpoints = [
        ("/api/stats", "GET", "System Statistics"),
        ("/api/sos", "GET", "All SOS Requests"),
        ("/api/emergency-contacts", "GET", "Emergency Contacts"),
        ("/api/response-teams", "GET", "Response Teams"),
        ("/api/analytics", "GET", "Analytics Data")
    ]
    
    for endpoint, method, description in endpoints:
        try:
            print(f"\nTesting {description}...")
            url = base_url + endpoint
            
            if method == "GET":
                response = requests.get(url, timeout=10)
            else:
                response = requests.post(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print(f"✅ {description}: SUCCESS")
                    if 'data' in data:
                        if isinstance(data['data'], list):
                            print(f"   📊 Records: {len(data['data'])}")
                        elif isinstance(data['data'], dict):
                            print(f"   📊 Keys: {list(data['data'].keys())}")
                else:
                    print(f"❌ {description}: API returned success=False")
                    print(f"   Message: {data.get('message', 'No message')}")
            else:
                print(f"❌ {description}: HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ {description}: Connection failed - Is the server running?")
        except requests.exceptions.Timeout:
            print(f"❌ {description}: Request timeout")
        except Exception as e:
            print(f"❌ {description}: Error - {str(e)}")
    
    print("\n" + "=" * 50)
    print("API testing completed!")

def test_sos_submission():
    """Test SOS form submission"""
    print("\nTesting SOS Form Submission...")
    print("-" * 30)
    
    sos_data = {
        "name": "Test User",
        "age": "25",
        "phone": "9876543210",
        "email": "test@example.com",
        "address": "123 Test Street, Test Area",
        "city": "Chennai",
        "pincode": "600001",
        "peopleToRescue": "2",
        "peopleInjured": "0",
        "foodAvailability": "sufficient",
        "waterAvailability": "sufficient",
        "pregnant": False,
        "elderly": False,
        "children": False,
        "disabled": False,
        "medical": False,
        "emergencyType": "flood",
        "additionalInfo": "This is a test emergency request"
    }
    
    try:
        response = requests.post(
            "http://localhost:5000/api/sos",
            json=sos_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ SOS Submission: SUCCESS")
                print(f"   Reference ID: {data.get('referenceId')}")
                print(f"   Message: {data.get('message')}")
                return data.get('referenceId')
            else:
                print("❌ SOS Submission: API returned success=False")
                print(f"   Message: {data.get('message')}")
        else:
            print(f"❌ SOS Submission: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ SOS Submission: Error - {str(e)}")
    
    return None

if __name__ == "__main__":
    print("Starting API tests...")
    print("Make sure the Flask app is running on http://localhost:5000")
    print()
    
    # Wait a moment for server to be ready
    time.sleep(2)
    
    # Test all endpoints
    test_api_endpoints()
    
    # Test SOS submission
    reference_id = test_sos_submission()
    
    if reference_id:
        print(f"\n✅ Test SOS request created with ID: {reference_id}")
        print("You can now check the dashboard and analytics pages to see if the data updates!")
    else:
        print("\n❌ Failed to create test SOS request")
    
    print("\nTest completed!")
