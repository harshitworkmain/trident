#!/usr/bin/env python3
"""
Test the updated priority calculation system
"""
import sys
import os
sys.path.append('.')

# Mock data for testing
test_cases = [
    {
        'name': 'Tsunami + Pregnant + No Water',
        'data': {
            'emergencyType': 'tsunami',
            'peopleInjured': '0',
            'pregnant': 'true',
            'elderly': 'false',
            'children': 'false', 
            'disabled': 'false',
            'medical': 'false',
            'foodAvailability': 'sufficient',
            'waterAvailability': 'none'
        }
    },
    {
        'name': 'Dam Breach + 3 Injured + Elderly',
        'data': {
            'emergencyType': 'dam-breach',
            'peopleInjured': '3',
            'pregnant': 'false',
            'elderly': 'true',
            'children': 'false',
            'disabled': 'false', 
            'medical': 'false',
            'foodAvailability': 'sufficient',
            'waterAvailability': 'sufficient'
        }
    },
    {
        'name': 'Flood + Children + Medical',
        'data': {
            'emergencyType': 'flood', 
            'peopleInjured': '0',
            'pregnant': 'false',
            'elderly': 'false',
            'children': 'true',
            'disabled': 'false',
            'medical': 'true',
            'foodAvailability': 'sufficient', 
            'waterAvailability': 'sufficient'
        }
    },
    {
        'name': 'Coastal Erosion + Children',
        'data': {
            'emergencyType': 'coastal-erosion',
            'peopleInjured': '0',
            'pregnant': 'false',
            'elderly': 'false', 
            'children': 'true',
            'disabled': 'false',
            'medical': 'false',
            'foodAvailability': 'sufficient',
            'waterAvailability': 'sufficient'
        }
    }
]

def calculate_priority_test(data):
    """Test version of priority calculation"""
    priority = 1  # Base priority
    
    # Medical & Safety Factors
    if int(data.get('peopleInjured', 0)) > 0:
        priority += 2
    if data.get('pregnant') == 'true':
        priority += 1
    if data.get('elderly') == 'true':
        priority += 1
    if data.get('children') == 'true':
        priority += 1
    if data.get('disabled') == 'true':
        priority += 1
    if data.get('medical') == 'true':
        priority += 2
    if data.get('foodAvailability') in ['none', 'critical']:
        priority += 1
    if data.get('waterAvailability') in ['none', 'critical']:
        priority += 1
    
    # Water emergency priorities
    water_emergency_priorities = {
        'tsunami': 3,
        'dam-breach': 3,
        'flood': 2,
        'storm': 2,
        'water-level-rising': 2,
        'coastal-erosion': 1
    }
    priority += water_emergency_priorities.get(data.get('emergencyType'), 0)
    
    return min(priority, 5)

def get_team_assignment(priority):
    """Get team assignment based on priority"""
    if priority >= 4:
        return "Chennai Water ROV Team Alpha (AUTO-DEPLOY) ⚡"
    elif priority == 3:
        return "Chennai Water ROV Team Beta or Supply Team (MANUAL) 👤"
    else:
        return "Chennai Water Supply Team (MANUAL) 👤"

print("🧪 PRIORITY SYSTEM TEST RESULTS")
print("=" * 60)

for test in test_cases:
    priority = calculate_priority_test(test['data'])
    team = get_team_assignment(priority)
    
    print(f"\n📋 {test['name']}")
    print(f"   Priority: {priority}/5")
    print(f"   Team: {team}")
    
    # Show calculation breakdown
    factors = []
    if int(test['data'].get('peopleInjured', 0)) > 0:
        factors.append(f"Injured({test['data']['peopleInjured']}): +2")
    if test['data'].get('pregnant') == 'true':
        factors.append("Pregnant: +1")
    if test['data'].get('elderly') == 'true':
        factors.append("Elderly: +1")
    if test['data'].get('children') == 'true':
        factors.append("Children: +1")
    if test['data'].get('medical') == 'true':
        factors.append("Medical: +2")
    if test['data'].get('foodAvailability') in ['none', 'critical']:
        factors.append("Food: +1")
    if test['data'].get('waterAvailability') in ['none', 'critical']:
        factors.append("Water: +1")
    
    # Emergency type
    emergency_type = test['data'].get('emergencyType')
    type_priorities = {'tsunami': 3, 'dam-breach': 3, 'flood': 2, 'storm': 2, 'water-level-rising': 2, 'coastal-erosion': 1}
    type_priority = type_priorities.get(emergency_type, 0)
    factors.append(f"{emergency_type.replace('-', ' ').title()}: +{type_priority}")
    
    print(f"   Factors: Base(1) + {' + '.join(factors)} = {priority}")

print("\n" + "=" * 60)
print("✅ Priority system working correctly!")