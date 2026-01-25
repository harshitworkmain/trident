#!/usr/bin/env python3
"""
Quick test for ROV auto-deployment with Priority 5 emergency
"""

import requests
import json

# Priority 5 emergency data (should trigger auto-deployment)
test_emergency = {
    'name': 'Test ROV Auto Deploy',
    'age': '30',
    'phone': '9876543210',
    'email': 'test@rov.com',
    'address': 'Marina Beach, Chennai',
    'city': 'Chennai',
    'pincode': '600001',
    'peopleToRescue': '2',
    'peopleInjured': '0',
    'emergencyType': 'tsunami',  # +3 points
    'foodAvailability': 'sufficient',
    'waterAvailability': 'none',  # +1 point
    'pregnant': 'true',  # +1 point
    'elderly': 'false',
    'children': 'false',
    'disabled': 'false',
    'medical': 'false',
    'additionalInfo': 'Testing Priority 5 auto-deployment: Base(1) + Tsunami(3) + Pregnant(1) + No Water(1) = Priority 5'
}

print("🧪 TESTING ROV AUTO-DEPLOYMENT")
print("=" * 40)
print("Emergency Data:")
print(f"- Type: {test_emergency['emergencyType']}")
print(f"- Pregnant: {test_emergency['pregnant']}")  
print(f"- Water: {test_emergency['waterAvailability']}")
print("- Expected Priority: 5 (should trigger auto-deployment)")
print()

try:
    print("📤 Submitting emergency request...")
    response = requests.post(
        'http://127.0.0.1:5000/api/sos',
        json=test_emergency,
        headers={'Content-Type': 'application/json'}
    )
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Emergency submitted successfully!")
        print(f"📋 Reference ID: {result['referenceId']}")
        print()
        print("🔍 Expected Results:")
        print("1. Priority 5 emergency detected")
        print("2. Alpha ROV team auto-assigned") 
        print("3. ROV console launched automatically")
        print("4. 12-second countdown begins")
        print("5. Thrusters activate automatically")
        print()
        print("Check the Flask server logs for deployment messages!")
        
    else:
        print(f"❌ Request failed: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Error: {e}")
    print("Make sure Flask server is running on http://127.0.0.1:5000")