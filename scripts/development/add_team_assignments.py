#!/usr/bin/env python3
"""
Add team assignment functionality to existing database
"""

import sqlite3
import random
from datetime import datetime

def add_team_column():
    """Add assigned_team_id column to sos_requests table"""
    conn = sqlite3.connect('trident_sos.db')
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute('PRAGMA table_info(sos_requests)')
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'assigned_team_id' not in columns:
            print("🔧 Adding assigned_team_id column to sos_requests table...")
            cursor.execute('ALTER TABLE sos_requests ADD COLUMN assigned_team_id INTEGER')
            print("✅ Column added successfully!")
        else:
            print("✅ assigned_team_id column already exists")
            
        conn.commit()
        
    except Exception as e:
        print(f"❌ Error adding column: {e}")
        conn.rollback()
    
    return conn, cursor

def assign_teams_to_in_progress():
    """Assign appropriate teams to in-progress requests"""
    conn, cursor = add_team_column()
    
    try:
        # Get available Chennai teams (since all requests are in Chennai)
        cursor.execute('''
            SELECT id, team_name, team_type 
            FROM response_teams 
            WHERE location = 'Chennai' AND is_available = 1
        ''')
        available_teams = cursor.fetchall()
        
        print(f"\n🚁 Available Chennai teams: {len(available_teams)}")
        for team in available_teams:
            print(f"   - {team[1]} ({team[2]})")
        
        # Get in-progress requests
        cursor.execute('''
            SELECT id, reference_id, name, emergency_type 
            FROM sos_requests 
            WHERE status = 'in-progress' AND assigned_team_id IS NULL
        ''')
        in_progress_requests = cursor.fetchall()
        
        print(f"\n📋 In-progress requests needing teams: {len(in_progress_requests)}")
        
        # Team assignment logic based on emergency type
        team_assignments = {
            'flood': 2,           # Chennai Rescue Team 2 (Fire & Rescue) - good for floods
            'tsunami': 1,         # Chennai Rescue Team 1 (Medical) - medical expertise needed  
            'dam-breach': 2,      # Chennai Rescue Team 2 (Fire & Rescue) - emergency response
            'storm': 3,           # Chennai Rescue Team 3 (General) - versatile
            'water-level-rising': 3, # Chennai Rescue Team 3 (General)
            'coastal-erosion': 3  # Chennai Rescue Team 3 (General)
        }
        
        # Assign teams to requests
        for request in in_progress_requests:
            request_id, ref_id, name, emergency_type = request
            
            # Get appropriate team for this emergency type
            preferred_team_id = team_assignments.get(emergency_type, 1)
            
            # Make sure the team is available
            if preferred_team_id <= len(available_teams):
                team_id = preferred_team_id
            else:
                team_id = random.choice(available_teams)[0]
            
            # Get team details
            cursor.execute('SELECT team_name, team_type FROM response_teams WHERE id = ?', (team_id,))
            team_info = cursor.fetchone()
            
            # Assign team to request
            cursor.execute('''
                UPDATE sos_requests 
                SET assigned_team_id = ?, updated_at = ?
                WHERE id = ?
            ''', (team_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), request_id))
            
            print(f"   ✅ {ref_id} ({name}) → {team_info[0]} ({team_info[1]})")
        
        conn.commit()
        print(f"\n🎯 Successfully assigned teams to {len(in_progress_requests)} in-progress requests!")
        
    except Exception as e:
        print(f"❌ Error assigning teams: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("🚁 Trident Emergency Response - Team Assignment Migration")
    print("=" * 60)
    assign_teams_to_in_progress()
    print("\n✅ Migration completed!")