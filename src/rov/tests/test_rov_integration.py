#!/usr/bin/env python3
"""
ROV Integration Test Script
Demonstrates automatic ROV deployment when emergency request is received
"""

import requests
import json
import time

# Test emergency data
emergency_data = {
    "name": "Test Emergency Response",
    "age": 30,
    "phone": "9876543210", 
    "email": "test@emergency.com",
    "address": "Marina Beach, Chennai - Emergency Location",
    "city": "Chennai",
    "pincode": "600001",
    "peopleToRescue": 3,
    "peopleInjured": 1,
    "foodAvailability": "critical",
    "waterAvailability": "none",
    "emergencyType": "tsunami",
    "pregnant": False,
    "elderly": True,
    "children": True,
    "disabled": False,
    "medical": True,
    "additionalInfo": "Tsunami warning - immediate ROV deployment required"
}

def test_emergency_rov_deployment():
    """Test automatic ROV deployment on emergency request"""
    
    print("🌊 TRIDENT EMERGENCY ROV INTEGRATION TEST")
    print("=" * 50)
    
    try:
        # Submit emergency request
        print("📤 Submitting emergency request...")
        response = requests.post(
            "http://127.0.0.1:5000/api/sos",
            json=emergency_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Emergency request submitted successfully!")
            print(f"📋 Reference ID: {result['referenceId']}")
            print(f"⏱️  Estimated Response Time: {result['estimatedResponseTime']}")
            
            # The Flask backend should now:
            # 1. Save the emergency request
            # 2. Trigger automatic ROV deployment
            # 3. Open ROV console in emergency mode
            # 4. Activate thrusters after 12 seconds
            
            print("\n🤖 EXPECTED ROV SEQUENCE:")
            print("1. ✅ ROV Console opens immediately (emergency stop capability)")
            print("2. ⏱️  AI path planning (simulated - 12 seconds)")
            print("3. 🚀 Automatic thruster activation")
            print("4. 📍 ROV deployment to emergency location")
            
            return result['referenceId']
            
        else:
            print(f"❌ Emergency request failed: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return None

def check_rov_status():
    """Check ROV deployment status"""
    try:
        print("\n🔍 Checking ROV Status...")
        response = requests.get("http://127.0.0.1:5000/api/rov-status")
        
        if response.status_code == 200:
            rov_data = response.json()['data']
            print(f"🤖 Total ROVs: {rov_data['total_rovs']}")
            print(f"⚡ Active ROVs: {rov_data['active_rovs']}")
            print(f"🚀 Deployed ROVs: {rov_data['deployed_rovs']}")
            
            for rov in rov_data['rovs']:
                status_emoji = "🚀" if rov['status'] == 'deployed' else "⚡" if rov['status'] == 'active' else "🔋"
                print(f"{status_emoji} {rov['name']}: {rov['status']} ({rov['battery']}% battery)")
                
        else:
            print(f"❌ Failed to get ROV status: {response.status_code}")
            
    except Exception as e:
        print(f"❌ ROV status check failed: {str(e)}")

if __name__ == "__main__":
    print("🧪 Starting ROV Integration Test...")
    print("⚠️  Make sure Flask server is running on http://127.0.0.1:5000")
    print()
    
    # Test the emergency ROV deployment
    reference_id = test_emergency_rov_deployment()
    
    if reference_id:
        print("\n⏳ Waiting 15 seconds for ROV deployment sequence...")
        time.sleep(15)
        
        # Check ROV status after deployment
        check_rov_status()
        
        print("\n🎯 INTEGRATION TEST COMPLETE!")
        print("📝 Check the Flask server logs to see ROV deployment messages")
        print("🖥️  ROV Console should have opened with emergency mission details")
    else:
        print("\n❌ Integration test failed!")