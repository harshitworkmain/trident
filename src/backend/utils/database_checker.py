#!/usr/bin/env python3
"""Check current database content"""

import sqlite3

def check_database():
    conn = sqlite3.connect('trident_sos.db')
    cursor = conn.cursor()
    
    # Check table structure
    cursor.execute("PRAGMA table_info(sos_requests)")
    columns = cursor.fetchall()
    print("📋 SOS requests table structure:")
    for col in columns:
        print(f"   {col[1]} ({col[2]})")
    
    print()
    
    # Check SOS requests
    cursor.execute('SELECT * FROM sos_requests ORDER BY created_at DESC')
    requests = cursor.fetchall()
    
    print(f"📊 Total SOS requests: {len(requests)}")
    print("\n🚨 Current requests:")
    print("-" * 100)
    
    for i, request in enumerate(requests[:15]):
        print(f"{i+1:2d}. {request}")
    
    if len(requests) > 15:
        print(f"... and {len(requests)-15} more requests")
    
    conn.close()

if __name__ == "__main__":
    check_database()