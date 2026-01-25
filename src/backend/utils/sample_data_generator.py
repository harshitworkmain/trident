#!/usr/bin/env python3
"""
Add sample SOS requests to test the system
"""

import sqlite3
import uuid
from datetime import datetime

DATABASE = 'trident_sos.db'

def add_sample_sos_requests():
    """Add sample SOS requests to the database"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Sample SOS requests
    sample_requests = [
        {
            'reference_id': f"TRD-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}",
            'name': 'John Smith',
            'age': 35,
            'phone': '9876543210',
            'email': 'john@example.com',
            'address': '123 Main Street, Downtown',
            'city': 'Chennai',
            'pincode': '600001',
            'people_to_rescue': 3,
            'people_injured': 1,
            'food_availability': 'limited',
            'water_availability': 'critical',
            'pregnant': False,
            'elderly': True,
            'children': True,
            'disabled': False,
            'medical': True,
            'emergency_type': 'flood',
            'additional_info': 'Water level rising rapidly, need immediate evacuation',
            'latitude': 13.0827,
            'longitude': 80.2707,
            'priority': 4,
            'status': 'pending'
        },
        {
            'reference_id': f"TRD-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}",
            'name': 'Sarah Johnson',
            'age': 28,
            'phone': '9876543211',
            'email': 'sarah@example.com',
            'address': '456 Park Avenue, Suburb',
            'city': 'Mumbai',
            'pincode': '400001',
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
            'additional_info': 'Coastal area, tsunami warning issued, need immediate evacuation',
            'latitude': 19.0760,
            'longitude': 72.8777,
            'priority': 5,
            'status': 'pending'
        },
        {
            'reference_id': f"TRD-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}",
            'name': 'Michael Brown',
            'age': 45,
            'phone': '9876543212',
            'email': 'michael@example.com',
            'address': '789 Riverside Colony',
            'city': 'Delhi',
            'pincode': '110001',
            'people_to_rescue': 5,
            'people_injured': 2,
            'food_availability': 'none',
            'water_availability': 'none',
            'pregnant': False,
            'elderly': False,
            'children': True,
            'disabled': True,
            'medical': True,
            'emergency_type': 'dam-breach',
            'additional_info': 'Dam overflow, rapid water level rise, multiple people trapped',
            'latitude': 28.7041,
            'longitude': 77.1025,
            'priority': 5,
            'status': 'resolved'
        },
        {
            'reference_id': f"TRD-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}",
            'name': 'Priya Sharma',
            'age': 32,
            'phone': '9876543213',
            'email': 'priya@example.com',
            'address': '321 Beach Road, Coastal Area',
            'city': 'Chennai',
            'pincode': '600028',
            'people_to_rescue': 4,
            'people_injured': 0,
            'food_availability': 'limited',
            'water_availability': 'limited',
            'pregnant': False,
            'elderly': True,
            'children': True,
            'disabled': False,
            'medical': False,
            'emergency_type': 'storm',
            'additional_info': 'Cyclone approaching, need evacuation assistance',
            'latitude': 13.0827,
            'longitude': 80.2707,
            'priority': 3,
            'status': 'pending'
        }
    ]
    
    try:
        for request in sample_requests:
            cursor.execute('''
                INSERT INTO sos_requests (
                    reference_id, name, age, phone, email, address, city, pincode,
                    people_to_rescue, people_injured, food_availability, water_availability,
                    pregnant, elderly, children, disabled, medical, emergency_type,
                    additional_info, latitude, longitude, priority, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                request['reference_id'],
                request['name'],
                request['age'],
                request['phone'],
                request['email'],
                request['address'],
                request['city'],
                request['pincode'],
                request['people_to_rescue'],
                request['people_injured'],
                request['food_availability'],
                request['water_availability'],
                request['pregnant'],
                request['elderly'],
                request['children'],
                request['disabled'],
                request['medical'],
                request['emergency_type'],
                request['additional_info'],
                request['latitude'],
                request['longitude'],
                request['priority'],
                request['status']
            ))
        
        conn.commit()
        print(f"✅ Added {len(sample_requests)} sample SOS requests to the database")
        
        # Show what was added
        cursor.execute('SELECT COUNT(*) FROM sos_requests')
        total_count = cursor.fetchone()[0]
        print(f"📊 Total SOS requests in database: {total_count}")
        
    except Exception as e:
        print(f"❌ Error adding sample data: {str(e)}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("Adding sample SOS requests to the database...")
    add_sample_sos_requests()
    print("Sample data addition completed!")
