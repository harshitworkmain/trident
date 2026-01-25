#!/usr/bin/env python3
"""Clear all SOS requests and add fresh water emergency sample data"""

import sqlite3
import random
from datetime import datetime, timedelta

def clear_and_populate_database():
    conn = sqlite3.connect('trident_sos.db')
    cursor = conn.cursor()
    
    # Clear all existing SOS requests
    print("🧹 Clearing all existing SOS requests...")
    cursor.execute('DELETE FROM sos_requests')
    
    # Reset the auto-increment counter
    cursor.execute('DELETE FROM sqlite_sequence WHERE name="sos_requests"')
    
    print("✅ All previous requests cleared!")
    
    # Fresh water emergency sample data
    water_emergencies = [
        {
            'reference_id': 'TRD-20250925-FLOOD001',
            'name': 'Rajesh Kumar',
            'age': 42,
            'phone': '9876543210',
            'email': 'rajesh.kumar@example.com',
            'address': '15 Flood Plains Colony, Near River',
            'city': 'Chennai',
            'pincode': '600001',
            'people_to_rescue': 4,
            'people_injured': 1,
            'food_availability': 'none',
            'water_availability': 'contaminated',
            'pregnant': False,
            'elderly': True,
            'children': True,
            'disabled': False,
            'medical': True,
            'emergency_type': 'flood',
            'additional_info': 'Flash flood, water level 6 feet high, family trapped on second floor',
            'latitude': 13.0827,
            'longitude': 80.2707,
            'priority': 5,
            'status': 'pending'
        },
        {
            'reference_id': 'TRD-20250925-TSUNAMI01',
            'name': 'Meera Srinivasan',
            'age': 35,
            'phone': '9876543211',
            'email': 'meera.s@example.com',
            'address': '42 Coastal Highway, Marina Beach Area',
            'city': 'Chennai',
            'pincode': '600028',
            'people_to_rescue': 2,
            'people_injured': 0,
            'food_availability': 'sufficient',
            'water_availability': 'sufficient',
            'pregnant': True,
            'elderly': False,
            'children': False,
            'disabled': False,
            'medical': False,
            'emergency_type': 'tsunami',
            'additional_info': 'Tsunami warning issued, pregnant woman needs immediate evacuation',
            'latitude': 13.0478,
            'longitude': 80.2838,
            'priority': 5,
            'status': 'pending'
        },
        {
            'reference_id': 'TRD-20250925-STORM001',
            'name': 'Arun Patel',
            'age': 28,
            'phone': '9876543212',
            'email': 'arun.patel@example.com',
            'address': '78 Seaside Avenue, Fishing Colony',
            'city': 'Chennai',
            'pincode': '600030',
            'people_to_rescue': 6,
            'people_injured': 2,
            'food_availability': 'limited',
            'water_availability': 'limited',
            'pregnant': False,
            'elderly': True,
            'children': True,
            'disabled': True,
            'medical': True,
            'emergency_type': 'storm',
            'additional_info': 'Cyclone damage, roof collapsed, multiple people trapped with injuries',
            'latitude': 13.1067,
            'longitude': 80.2969,
            'priority': 4,
            'status': 'pending'
        },
        {
            'reference_id': 'TRD-20250925-DAMBRCH1',
            'name': 'Lakshmi Nair',
            'age': 38,
            'phone': '9876543213',
            'email': 'lakshmi.nair@example.com',
            'address': '23 Riverside Colony, Near Dam',
            'city': 'Chennai',
            'pincode': '600032',
            'people_to_rescue': 8,
            'people_injured': 3,
            'food_availability': 'none',
            'water_availability': 'none',
            'pregnant': False,
            'elderly': True,
            'children': True,
            'disabled': False,
            'medical': True,
            'emergency_type': 'dam-breach',
            'additional_info': 'Dam breach upstream, rapid water rise, entire community evacuating',
            'latitude': 13.0678,
            'longitude': 80.2372,
            'priority': 5,
            'status': 'in-progress'
        },
        {
            'reference_id': 'TRD-20250925-COAST001',
            'name': 'Vikram Singh',
            'age': 45,
            'phone': '9876543214',
            'email': 'vikram.singh@example.com',
            'address': '56 Shore Road, Coastal Village',
            'city': 'Chennai',
            'pincode': '600025',
            'people_to_rescue': 3,
            'people_injured': 0,
            'food_availability': 'sufficient',
            'water_availability': 'limited',
            'pregnant': False,
            'elderly': False,
            'children': True,
            'disabled': False,
            'medical': False,
            'emergency_type': 'coastal-erosion',
            'additional_info': 'Severe coastal erosion, house foundation compromised, need evacuation',
            'latitude': 13.0332,
            'longitude': 80.2789,
            'priority': 3,
            'status': 'pending'
        },
        {
            'reference_id': 'TRD-20250925-WATER001',
            'name': 'Priya Reddy',
            'age': 29,
            'phone': '9876543215',
            'email': 'priya.reddy@example.com',
            'address': '89 Low Lying Area, Flood Zone',
            'city': 'Chennai',
            'pincode': '600033',
            'people_to_rescue': 5,
            'people_injured': 1,
            'food_availability': 'limited',
            'water_availability': 'critical',
            'pregnant': True,
            'elderly': False,
            'children': True,
            'disabled': False,
            'medical': True,
            'emergency_type': 'water-level-rising',
            'additional_info': 'Water level rising due to heavy rains, pregnant woman with complications',
            'latitude': 13.0543,
            'longitude': 80.2456,
            'priority': 4,
            'status': 'pending'
        }
    ]
    
    print(f"🌊 Adding {len(water_emergencies)} fresh water emergency requests...")
    
    for emergency in water_emergencies:
        # Generate creation time (within last 24 hours)
        hours_ago = random.randint(1, 24)
        created_at = datetime.now() - timedelta(hours=hours_ago)
        
        cursor.execute('''
            INSERT INTO sos_requests (
                reference_id, name, age, phone, email, address, city, pincode,
                people_to_rescue, people_injured, food_availability, water_availability,
                pregnant, elderly, children, disabled, medical, emergency_type,
                additional_info, latitude, longitude, priority, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            emergency['reference_id'], emergency['name'], emergency['age'],
            emergency['phone'], emergency['email'], emergency['address'],
            emergency['city'], emergency['pincode'], emergency['people_to_rescue'],
            emergency['people_injured'], emergency['food_availability'],
            emergency['water_availability'], emergency['pregnant'],
            emergency['elderly'], emergency['children'], emergency['disabled'],
            emergency['medical'], emergency['emergency_type'],
            emergency['additional_info'], emergency['latitude'],
            emergency['longitude'], emergency['priority'], emergency['status'],
            created_at, created_at
        ))
    
    conn.commit()
    
    # Verify the data
    cursor.execute('SELECT COUNT(*) FROM sos_requests')
    count = cursor.fetchone()[0]
    
    print(f"✅ Successfully added {count} fresh water emergency requests!")
    print("\n🚨 New emergency summary:")
    
    cursor.execute('SELECT emergency_type, COUNT(*) FROM sos_requests GROUP BY emergency_type')
    for emergency_type, count in cursor.fetchall():
        print(f"   {emergency_type}: {count} requests")
    
    conn.close()

if __name__ == "__main__":
    clear_and_populate_database()