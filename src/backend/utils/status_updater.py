#!/usr/bin/env python3
"""
Update sample data with varied statuses for meaningful analytics charts
"""

import sqlite3
import random
from datetime import datetime, timedelta

# Connect to database
conn = sqlite3.connect('trident_sos.db')
cursor = conn.cursor()

# Define status updates with realistic scenarios
status_updates = [
    # Keep some pending (newer requests)
    (7, 'pending'),  # Recent storm - still processing
    (8, 'pending'),  # Recent water level - just received
    
    # Set some to in-progress (active rescues)
    (1, 'in-progress'),  # Flood rescue ongoing
    (2, 'in-progress'),  # Tsunami evacuation in progress
    (4, 'in-progress'),  # Dam breach - already in progress
    
    # Set some to resolved (successful rescues)
    (3, 'resolved'),   # Storm - rescue completed
    (5, 'resolved'),   # Coastal erosion - successfully evacuated
    
    # Set one to cancelled (false alarm or duplicate)
    (6, 'cancelled'),  # Water level rising - false alarm
]

print("🔄 Updating emergency request statuses for better analytics...")

# Update each request
for request_id, new_status in status_updates:
    cursor.execute("""
        UPDATE sos_requests 
        SET status = ?, updated_at = ?
        WHERE id = ?
    """, (new_status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), request_id))
    
    print(f"   ✅ Request {request_id} → {new_status}")

# Commit changes
conn.commit()
conn.close()

print("\n📊 Status distribution should now show:")
print("   • Pending: 2 requests")
print("   • In-Progress: 3 requests") 
print("   • Resolved: 2 requests")
print("   • Cancelled: 1 request")
print("\n🎯 Your charts will now display meaningful data!")