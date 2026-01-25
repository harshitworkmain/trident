#!/usr/bin/env python3
"""Clear all SOS requests from the database"""

import sqlite3

def clear_all_requests():
    """Delete all SOS requests from the database"""
    try:
        conn = sqlite3.connect('trident_sos.db')
        cursor = conn.cursor()
        
        # Get current count before deletion
        cursor.execute('SELECT COUNT(*) FROM sos_requests')
        initial_count = cursor.fetchone()[0]
        
        print(f"🗑️  Found {initial_count} SOS requests in database")
        
        if initial_count == 0:
            print("✅ Database is already empty!")
            conn.close()
            return
        
        # Delete all SOS requests
        print("🧹 Clearing all SOS requests...")
        cursor.execute('DELETE FROM sos_requests')
        
        # Reset the auto-increment counter
        cursor.execute('DELETE FROM sqlite_sequence WHERE name="sos_requests"')
        
        conn.commit()
        
        # Verify deletion
        cursor.execute('SELECT COUNT(*) FROM sos_requests')
        final_count = cursor.fetchone()[0]
        
        print(f"✅ Successfully deleted {initial_count} requests!")
        print(f"📊 Database now contains {final_count} requests")
        print("🎯 Database cleared and ready for new requests!")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    print("=" * 50)
    print("🌊 TRIDENT - Database Cleanup Tool")
    print("=" * 50)
    clear_all_requests()
    print("=" * 50)