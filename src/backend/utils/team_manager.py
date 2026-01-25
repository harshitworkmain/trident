#!/usr/bin/env python3
"""
Update teams to water-specialized ROV rescue and supply teams
"""

import sqlite3
from datetime import datetime

def update_water_rescue_teams():
    """Replace existing teams with water-specialized ROV teams"""
    conn = sqlite3.connect('trident_sos.db')
    cursor = conn.cursor()
    
    try:
        print("🌊 Updating to Water Emergency Specialized Teams...")
        print("=" * 60)
        
        # Clear existing teams
        cursor.execute('DELETE FROM response_teams')
        print("🗑️  Cleared existing teams")
        
        # Insert new water-specialized teams
        water_teams = [
            # ROV Rescue Teams (2)
            (
                1,  # id
                'Chennai Water ROV Team Alpha', 
                'ROV Water Rescue', 
                '9876543301', 
                'rov-alpha@trident.in', 
                'Chennai Marina Base', 
                5,  # capacity (ROV + 4 operators)
                0,  # current_load 
                1,  # is_available
                'AUTO_DEPLOY',  # deployment_mode
                'Primary ROV rescue unit with underwater rescue capabilities and emergency medical support'
            ),
            (
                2,  # id
                'Chennai Water ROV Team Beta', 
                'ROV Water Rescue', 
                '9876543302', 
                'rov-beta@trident.in', 
                'Chennai Port Base', 
                5,  # capacity (ROV + 4 operators)
                0,  # current_load
                1,  # is_available 
                'MANUAL_DEPLOY',  # deployment_mode
                'Secondary ROV rescue unit with deep water search and rescue capabilities'
            ),
            # Supply Team (1)
            (
                3,  # id
                'Chennai Water Supply Team', 
                'Water Emergency Supply', 
                '9876543303', 
                'supply@trident.in', 
                'Chennai Emergency Warehouse', 
                10,  # capacity (larger supply team)
                0,   # current_load
                1,   # is_available
                'MANUAL_DEPLOY',  # deployment_mode
                'Emergency supply distribution for food, clean water, medical supplies, and evacuation support'
            )
        ]
        
        # Add deployment_mode column if it doesn't exist
        try:
            cursor.execute('ALTER TABLE response_teams ADD COLUMN deployment_mode TEXT DEFAULT "MANUAL_DEPLOY"')
            cursor.execute('ALTER TABLE response_teams ADD COLUMN team_description TEXT DEFAULT ""')
            print("✅ Added deployment_mode and team_description columns")
        except Exception as e:
            print(f"ℹ️  Columns might already exist: {e}")
        
        # Insert new teams
        for team in water_teams:
            cursor.execute('''
                INSERT OR REPLACE INTO response_teams 
                (id, team_name, team_type, contact_phone, contact_email, location, 
                 capacity, current_load, is_available, deployment_mode, team_description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (*team, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            print(f"   ✅ {team[1]} ({team[2]})")
            print(f"      📞 {team[3]} | 📧 {team[4]}")
            print(f"      📍 {team[5]} | 👥 {team[6]} capacity")
            print(f"      🚁 Deployment: {team[9]}")
            print(f"      💬 {team[10]}")
            print()
        
        conn.commit()
        print("🎯 Successfully updated to water emergency specialized teams!")
        
        # Update existing request assignments to use new teams
        print("\n🔄 Updating existing request assignments...")
        
        # Auto-assign in-progress requests to appropriate teams
        cursor.execute('''
            SELECT id, reference_id, emergency_type, status
            FROM sos_requests 
            WHERE status = 'in-progress'
        ''')
        
        requests = cursor.fetchall()
        
        for request in requests:
            request_id, ref_id, emergency_type, status = request
            
            # Primary ROV team gets first in-progress request (auto-deploy)
            # Others go to secondary team (manual deploy)
            if request_id == 1:  # First request gets auto-deploy team
                new_team_id = 1  # Chennai Water ROV Team Alpha (AUTO_DEPLOY)
            else:
                new_team_id = 2  # Chennai Water ROV Team Beta (MANUAL_DEPLOY)
            
            cursor.execute('''
                UPDATE sos_requests 
                SET assigned_team_id = ?, updated_at = ?
                WHERE id = ?
            ''', (new_team_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), request_id))
            
            team_name = "Alpha (Auto-Deploy)" if new_team_id == 1 else "Beta (Manual)"
            print(f"   ✅ {ref_id} → ROV Team {team_name}")
        
        conn.commit()
        print(f"\n✅ Updated {len(requests)} existing assignments")
        
    except Exception as e:
        print(f"❌ Error updating teams: {e}")
        conn.rollback()
    finally:
        conn.close()

def show_new_teams():
    """Display the new team structure"""
    conn = sqlite3.connect('trident_sos.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, team_name, team_type, contact_phone, contact_email, 
                   location, capacity, deployment_mode, team_description
            FROM response_teams 
            ORDER BY id
        ''')
        
        teams = cursor.fetchall()
        
        print("\n🌊 CHENNAI WATER EMERGENCY RESPONSE TEAMS")
        print("=" * 80)
        
        for team in teams:
            team_id, name, type_name, phone, email, location, capacity, deploy_mode, description = team
            
            print(f"\n🚁 {name}")
            print(f"   Type: {type_name}")
            print(f"   Contact: {phone} | {email}")
            print(f"   Base: {location}")
            print(f"   Capacity: {capacity} personnel")
            print(f"   Deployment: {deploy_mode}")
            print(f"   Mission: {description}")
            
            if deploy_mode == 'AUTO_DEPLOY':
                print("   ⚡ AUTOMATIC ROV DEPLOYMENT ENABLED")
            else:
                print("   👤 Manual deployment required")
                
    except Exception as e:
        print(f"❌ Error displaying teams: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_water_rescue_teams()
    show_new_teams()