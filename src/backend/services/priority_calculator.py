#!/usr/bin/env python3
"""
Chennai Water Emergency Response - Priority System Guide
========================================================

This document explains how emergency priorities are calculated and assigned
in the Trident Water Emergency Response System.
"""

print("🌊 CHENNAI WATER EMERGENCY PRIORITY SYSTEM")
print("=" * 70)

# Base Priority System
print("\n📊 BASE PRIORITY CALCULATION:")
print("Starting Priority: 1 (Low)")
print()

# Medical & Safety Factors
print("🏥 MEDICAL & SAFETY FACTORS:")
print("├─ People Injured > 0           → +2 priority")
print("├─ Pregnant woman               → +1 priority") 
print("├─ Elderly people present       → +1 priority")
print("├─ Children present             → +1 priority")
print("├─ Disabled people present      → +1 priority")
print("└─ Medical emergency            → +2 priority")
print()

# Resource Factors
print("📦 RESOURCE AVAILABILITY:")
print("├─ Food: None/Critical          → +1 priority")
print("└─ Water: None/Critical         → +1 priority")
print()

# Water Emergency Type Priorities (Updated System)
print("🌊 WATER EMERGENCY TYPE PRIORITIES:")
print("├─ Tsunami                      → +3 priority (Immediate evacuation)")
print("├─ Dam Breach                   → +3 priority (Catastrophic flooding)")
print("├─ Flood                        → +2 priority (Life threatening)")
print("├─ Storm                        → +2 priority (Severe weather)")
print("├─ Water Level Rising           → +2 priority (Growing danger)")
print("└─ Coastal Erosion              → +1 priority (Infrastructure risk)")
print()

# Priority Levels & Team Assignment
print("🚁 PRIORITY LEVELS & TEAM ASSIGNMENT:")
print()
print("PRIORITY 5 (CRITICAL - AUTO ROV DEPLOYMENT)")
print("├─ Team: Chennai Water ROV Team Alpha")
print("├─ Deployment: ⚡ AUTOMATIC (12-second countdown)")
print("├─ Response: Immediate ROV activation with thrusters")
print("└─ Example: Dam breach + injured + pregnant woman")
print()
print("PRIORITY 4 (HIGH - AUTO ROV DEPLOYMENT)")  
print("├─ Team: Chennai Water ROV Team Alpha")
print("├─ Deployment: ⚡ AUTOMATIC (12-second countdown)")
print("├─ Response: Immediate ROV activation")
print("└─ Example: Flood + elderly + medical emergency")
print()
print("PRIORITY 3 (MEDIUM - MANUAL DEPLOYMENT)")
print("├─ Team: Chennai Water ROV Team Beta OR Supply Team")
print("├─ Deployment: 👤 MANUAL (requires operator approval)")
print("├─ Response: Manual ROV or supply deployment")
print("└─ Example: Coastal erosion + children")
print()
print("PRIORITY 2 (STANDARD - MANUAL DEPLOYMENT)")
print("├─ Team: Chennai Water Supply Team")
print("├─ Deployment: 👤 MANUAL (supply distribution)")
print("├─ Response: Emergency supplies and evacuation support")
print("└─ Example: Water level rising + food shortage")
print()
print("PRIORITY 1 (LOW - MANUAL DEPLOYMENT)")
print("├─ Team: Chennai Water Supply Team")
print("├─ Deployment: 👤 MANUAL (basic assistance)")
print("├─ Response: Supply distribution and monitoring")
print("└─ Example: Basic coastal erosion report")
print()

# Example Calculations
print("📝 PRIORITY CALCULATION EXAMPLES:")
print("=" * 50)

examples = [
    {
        'scenario': 'Tsunami + Pregnant Woman + No Water',
        'calculation': 'Base(1) + Tsunami(+3) + Pregnant(+1) + No Water(+1) = 6 → Priority 5 (MAX)',
        'team': 'ROV Team Alpha (AUTO-DEPLOY)',
        'response': '⚡ Immediate ROV deployment in 12 seconds'
    },
    {
        'scenario': 'Dam Breach + 3 Injured + Elderly + Medical',
        'calculation': 'Base(1) + Dam Breach(+3) + Injured(+2) + Elderly(+1) + Medical(+2) = 9 → Priority 5 (MAX)',
        'team': 'ROV Team Alpha (AUTO-DEPLOY)', 
        'response': '⚡ Emergency ROV rescue with medical support'
    },
    {
        'scenario': 'Flood + Children + Critical Food',
        'calculation': 'Base(1) + Flood(+2) + Children(+1) + Critical Food(+1) = 5 → Priority 5',
        'team': 'ROV Team Alpha (AUTO-DEPLOY)',
        'response': '⚡ Immediate ROV deployment'
    },
    {
        'scenario': 'Storm + Elderly',
        'calculation': 'Base(1) + Storm(+2) + Elderly(+1) = 4 → Priority 4',
        'team': 'ROV Team Alpha (AUTO-DEPLOY)',
        'response': '⚡ High priority auto-deployment'
    },
    {
        'scenario': 'Coastal Erosion + Children',
        'calculation': 'Base(1) + Coastal Erosion(+1) + Children(+1) = 3 → Priority 3',
        'team': 'ROV Team Beta or Supply Team (MANUAL)',
        'response': '👤 Manual deployment decision'
    },
    {
        'scenario': 'Water Level Rising + No Food',
        'calculation': 'Base(1) + Water Rising(+2) + No Food(+1) = 4 → Priority 4',
        'team': 'ROV Team Alpha (AUTO-DEPLOY)',
        'response': '⚡ Auto-deployment with supply support'
    }
]

for i, example in enumerate(examples, 1):
    print(f"\nExample {i}: {example['scenario']}")
    print(f"Calculation: {example['calculation']}")
    print(f"Assigned Team: {example['team']}")  
    print(f"Response: {example['response']}")

print("\n" + "=" * 70)
print("🎯 KEY POINTS:")
print("• Maximum Priority = 5 (anything above gets capped)")
print("• Priority 4-5 = AUTO ROV deployment (Team Alpha only)")
print("• Priority 1-3 = MANUAL deployment (Team Beta/Supply)")
print("• Only 1 ROV auto-deploys at a time (Team Alpha)")
print("• System prioritizes life-threatening water emergencies")
print("=" * 70)