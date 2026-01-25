#!/usr/bin/env python3
"""
Test ROV Auto-deployment System
Demonstrates Priority 4-5 automatic deployment and mission tracking
"""

import requests
import json
import time

BASE_URL = 'http://127.0.0.1:5000'

def create_priority_emergency(priority_level=5):
    """Create a high-priority emergency to trigger auto-deployment"""
    
    if priority_level == 5:
        # Priority 5: Tsunami + Pregnant + No Water
        emergency_data = {
            'name': 'ROV Test Emergency',
            'age': '28',
            'phone': '9876543210',
            'email': 'test@emergency.com',
            'address': 'Marina Beach, Chennai',
            'city': 'Chennai',
            'pincode': '600001',
            'peopleToRescue': '2',
            'peopleInjured': '0',
            'emergencyType': 'tsunami',
            'foodAvailability': 'sufficient',
            'waterAvailability': 'none',
            'pregnant': 'true',
            'elderly': 'false',
            'children': 'false',
            'disabled': 'false',
            'medical': 'false',
            'additionalInfo': 'Testing ROV auto-deployment for Priority 5 tsunami emergency'
        }
    else:
        # Priority 4: Flood + Children + Medical
        emergency_data = {
            'name': 'ROV Test Emergency 2',
            'age': '35',
            'phone': '9876543211',
            'email': 'test2@emergency.com',
            'address': 'T Nagar, Chennai',
            'city': 'Chennai',
            'pincode': '600017',
            'peopleToRescue': '3',
            'peopleInjured': '0',
            'emergencyType': 'flood',
            'foodAvailability': 'sufficient',
            'waterAvailability': 'sufficient',
            'pregnant': 'false',
            'elderly': 'false',
            'children': 'true',
            'disabled': 'false',
            'medical': 'true',
            'additionalInfo': 'Testing ROV auto-deployment for Priority 4 flood emergency'
        }
    
    return emergency_data

def test_rov_auto_deployment():
    """Test complete ROV auto-deployment workflow"""
    
    print("🧪 ROV AUTO-DEPLOYMENT TEST")
    print("=" * 50)
    
    # Step 1: Check initial ROV status
    print("\n1️⃣ Initial ROV Status:")
    response = requests.get(f'{BASE_URL}/api/rov-status')
    if response.status_code == 200:
        data = response.json()['data']
        for rov in data['rovs']:
            status = "🟢 Available" if rov['status'] in ['active', 'docked'] else f"🔴 {rov['status'].title()}"
            print(f"   {rov['name']}: {status}")
            if rov['assigned_request']:
                print(f"      Mission: {rov['assigned_request']}")
    
    # Step 2: Create Priority 5 emergency (should auto-deploy)
    print("\n2️⃣ Creating Priority 5 Emergency (Tsunami)...")
    emergency_data = create_priority_emergency(5)
    
    response = requests.post(f'{BASE_URL}/api/sos', json=emergency_data)
    if response.status_code == 200:
        result = response.json()
        reference_id_1 = result['data']['reference_id']
        print(f"   ✅ Emergency created: {reference_id_1}")
        print("   ⏱️  Alpha ROV should auto-deploy in 12 seconds...")
    else:
        print(f"   ❌ Failed to create emergency: {response.text}")
        return
    
    # Step 3: Wait for auto-deployment
    print("\n3️⃣ Waiting for auto-deployment...")
    time.sleep(15)  # Wait for 12-second countdown + processing
    
    # Check ROV status after auto-deployment
    response = requests.get(f'{BASE_URL}/api/rov-status')
    if response.status_code == 200:
        data = response.json()['data']
        alpha_rov = next(rov for rov in data['rovs'] if rov['id'] == 'ROV-001')
        if alpha_rov['assigned_request']:
            print(f"   🚁 Alpha ROV deployed to mission: {alpha_rov['assigned_request']}")
        else:
            print("   ⚠️  Alpha ROV not deployed (check logs)")
    
    # Step 4: Try creating another Priority 5 emergency (should be blocked)
    print("\n4️⃣ Creating Second Priority 5 Emergency (should be blocked)...")
    emergency_data_2 = create_priority_emergency(5)
    emergency_data_2['name'] = 'Second ROV Test Emergency'
    emergency_data_2['phone'] = '9876543212'
    emergency_data_2['emergencyType'] = 'dam-breach'
    
    response = requests.post(f'{BASE_URL}/api/sos', json=emergency_data_2)
    if response.status_code == 200:
        result = response.json()
        reference_id_2 = result['data']['reference_id']
        print(f"   ✅ Second emergency created: {reference_id_2}")
        print("   🚫 Alpha ROV should NOT auto-deploy (already busy)")
    
    time.sleep(3)
    
    # Check if second deployment was blocked
    response = requests.get(f'{BASE_URL}/api/rov-status')
    if response.status_code == 200:
        data = response.json()['data']
        alpha_rov = next(rov for rov in data['rovs'] if rov['id'] == 'ROV-001')
        if alpha_rov['assigned_request'] == reference_id_1:
            print("   ✅ Correctly blocked second auto-deployment")
        else:
            print(f"   ⚠️  Unexpected ROV assignment: {alpha_rov['assigned_request']}")
    
    # Step 5: Complete first mission to free up Alpha ROV
    print("\n5️⃣ Completing First Mission...")
    status_data = {
        'status': 'resolved',
        'notes': 'Test mission completed - ROV should be available now',
        'updated_by': 'Test System'
    }
    
    response = requests.put(f'{BASE_URL}/api/sos/{reference_id_1}/update-status', json=status_data)
    if response.status_code == 200:
        print(f"   ✅ Mission {reference_id_1} marked as resolved")
        print("   🆓 Alpha ROV should now be available")
    
    # Step 6: Final ROV status check
    print("\n6️⃣ Final ROV Status:")
    response = requests.get(f'{BASE_URL}/api/rov-status')
    if response.status_code == 200:
        data = response.json()['data']
        for rov in data['rovs']:
            status = "🟢 Available" if rov['status'] in ['active', 'docked'] else f"🔴 {rov['status'].title()}"
            print(f"   {rov['name']}: {status}")
            if rov['assigned_request']:
                print(f"      Mission: {rov['assigned_request']}")
    
    print("\n🎯 ROV Auto-deployment Test Complete!")
    print("Summary:")
    print("- Priority 4-5 emergencies trigger 12-second auto-deployment")
    print("- Only Alpha ROV auto-deploys (AUTO_DEPLOY mode)")
    print("- Prevents multiple deployments until mission complete")
    print("- Automatic mission completion on status update")

if __name__ == "__main__":
    try:
        test_rov_auto_deployment()
    except KeyboardInterrupt:
        print("\n\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")