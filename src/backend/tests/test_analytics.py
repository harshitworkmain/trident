#!/usr/bin/env python3
"""
Test the analytics API endpoints directly
"""

import sqlite3
import json

# Test direct database query
print("🔍 Testing database query directly...")

conn = sqlite3.connect('trident_sos.db')
cursor = conn.cursor()

print("\n📊 Current data in sos_requests table:")
cursor.execute('SELECT id, status FROM sos_requests ORDER BY id')
for row in cursor.fetchall():
    print(f"   ID {row[0]}: {row[1]}")

print("\n📈 Status distribution query result:")
cursor.execute('''
    SELECT status, COUNT(*) as count
    FROM sos_requests 
    GROUP BY status
    ORDER BY count DESC
''')

status_data = []
for row in cursor.fetchall():
    status_data.append({
        'status': row[0],
        'count': row[1]
    })
    print(f"   {row[0]}: {row[1]} requests")

print(f"\n🎯 JSON that should be returned:")
print(json.dumps({
    'success': True,
    'data': status_data,
    'total': sum(item['count'] for item in status_data)
}, indent=2))

conn.close()