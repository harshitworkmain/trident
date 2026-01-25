from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
import sqlite3
import uuid
import time
from datetime import datetime, timedelta
import logging
import os
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Database configuration
DATABASE = 'trident_sos.db'

# AI Model Configuration
class WeatherLSTM(nn.Module):
    def __init__(self, input_size=1, hidden_size=50, num_layers=2, output_size=1, dropout=0.2):
        super(WeatherLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, 
                           batch_first=True, dropout=dropout)
        self.fc = nn.Linear(hidden_size, output_size)
        self.dropout = nn.Dropout(dropout)
        
    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size)
        
        out, _ = self.lstm(x, (h0, c0))
        out = self.dropout(out[:, -1, :])
        out = self.fc(out)
        return out

# Global variables for AI model
weather_model = None
weather_scaler = None
weather_data = None

def init_database():
    """Initialize the SQLite database with required tables"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Create SOS requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sos_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            pincode TEXT NOT NULL,
            people_to_rescue INTEGER NOT NULL,
            people_injured INTEGER NOT NULL,
            food_availability TEXT NOT NULL,
            water_availability TEXT NOT NULL,
            pregnant BOOLEAN DEFAULT FALSE,
            elderly BOOLEAN DEFAULT FALSE,
            children BOOLEAN DEFAULT FALSE,
            disabled BOOLEAN DEFAULT FALSE,
            medical BOOLEAN DEFAULT FALSE,
            emergency_type TEXT NOT NULL,
            additional_info TEXT,
            latitude REAL,
            longitude REAL,
            priority INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            assigned_team_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assigned_team_id) REFERENCES response_teams (id)
        )
    ''')
    
    # Create SOS status history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sos_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference_id TEXT NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            updated_by TEXT DEFAULT 'System',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reference_id) REFERENCES sos_requests (reference_id)
        )
    ''')
    
    # Create SOS assignments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sos_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference_id TEXT NOT NULL,
            team_id INTEGER NOT NULL,
            assigned_by TEXT DEFAULT 'System',
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reference_id) REFERENCES sos_requests (reference_id),
            FOREIGN KEY (team_id) REFERENCES response_teams (id)
        )
    ''')
    
    # Create SOS notes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sos_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference_id TEXT NOT NULL,
            note TEXT NOT NULL,
            author TEXT DEFAULT 'System',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reference_id) REFERENCES sos_requests (reference_id)
        )
    ''')
    
    # Create emergency contacts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            department TEXT NOT NULL,
            location TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create response teams table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS response_teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name TEXT NOT NULL,
            team_type TEXT NOT NULL,
            contact_phone TEXT NOT NULL,
            contact_email TEXT,
            location TEXT,
            capacity INTEGER,
            current_load INTEGER DEFAULT 0,
            is_available BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert default emergency contacts
    default_contacts = [
        ('Emergency Services', '100', 'emergency@gov.in', 'General Emergency', 'All India', True),
        ('Fire Department', '101', 'fire@gov.in', 'Fire & Rescue', 'All India', True),
        ('Medical Emergency', '108', 'medical@gov.in', 'Medical Services', 'All India', True),
        ('Police', '100', 'police@gov.in', 'Law Enforcement', 'All India', True),
        ('Disaster Management', '108', 'disaster@gov.in', 'Disaster Response', 'All India', True)
    ]
    
    cursor.execute('SELECT COUNT(*) FROM emergency_contacts')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
            INSERT INTO emergency_contacts (name, phone, email, department, location, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', default_contacts)
    
    # Insert default response teams
    default_teams = [
        ('Chennai Water Rescue Team 1', 'Water Rescue', '9876543210', 'waterrescue1@trident.in', 'Chennai', 10, 0, True),
        ('Chennai Flood Response Team 2', 'Flood Response', '9876543211', 'floodresponse@trident.in', 'Chennai', 8, 0, True),
        ('Chennai Coastal Rescue Team 3', 'Coastal Rescue', '9876543212', 'coastalrescue@trident.in', 'Chennai', 12, 0, True),
        ('Mumbai Marine Rescue Team 1', 'Marine Rescue', '9876543213', 'marinerescue@trident.in', 'Mumbai', 10, 0, True),
        ('Delhi River Rescue Team 1', 'River Rescue', '9876543214', 'riverrescue@trident.in', 'Delhi', 15, 0, True)
    ]
    
    cursor.execute('SELECT COUNT(*) FROM response_teams')
    if cursor.fetchone()[0] == 0:
        cursor.executemany('''
            INSERT INTO response_teams (team_name, team_type, contact_phone, contact_email, location, capacity, current_load, is_available)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', default_teams)
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

def init_ai_model():
    """Initialize the AI weather prediction model"""
    global weather_model, weather_scaler, weather_data
    
    try:
        # Load weather data
        weather_data = pd.read_csv('data/chennai_weather.csv')
        weather_data['time'] = pd.to_datetime(weather_data['time'])
        weather_data = weather_data.sort_values('time')
        
        # Prepare data for temperature prediction
        temp_data = weather_data['temp'].values.reshape(-1, 1)
        
        # Initialize scaler
        weather_scaler = MinMaxScaler()
        temp_scaled = weather_scaler.fit_transform(temp_data)
        
        # Initialize model
        weather_model = WeatherLSTM(input_size=1, hidden_size=50, num_layers=2, output_size=1)
        
        # Load trained model if available
        model_path = 'trained_model/weather_lstm_model.pth'
        if os.path.exists(model_path):
            try:
                # Try to load the model with the expected structure
                model_data = torch.load(model_path, map_location='cpu')
                
                # Check if it's a dictionary with model_state_dict key
                if isinstance(model_data, dict) and 'model_state_dict' in model_data:
                    weather_model.load_state_dict(model_data['model_state_dict'])
                    logger.info("AI weather model loaded successfully from checkpoint")
                else:
                    # Try direct loading
                    weather_model.load_state_dict(model_data)
                    logger.info("AI weather model loaded successfully")
                    
                weather_model.eval()
            except Exception as model_error:
                logger.warning(f"Could not load trained model: {str(model_error)}")
                logger.info("Using untrained model for predictions")
        else:
            logger.warning("Trained model not found, using untrained model")
            
    except Exception as e:
        logger.error(f"Error initializing AI model: {str(e)}")
        weather_model = None
        weather_scaler = None
        weather_data = None

def predict_temperature(hours_ahead=24):
    """Predict temperature for the next N hours"""
    global weather_model, weather_scaler, weather_data
    
    if weather_data is None:
        return None
    
    try:
        # Get recent temperature data
        recent_temp = weather_data['temp'].tail(24).values
        
        # Generate timestamps
        last_time = weather_data['time'].iloc[-1]
        timestamps = [last_time + timedelta(hours=i+1) for i in range(hours_ahead)]
        
        # If model is available, use it for predictions
        if weather_model is not None and weather_scaler is not None:
            try:
                recent_temp_scaled = weather_scaler.transform(recent_temp.reshape(-1, 1))
                input_seq = torch.FloatTensor(recent_temp_scaled).unsqueeze(0)
                
                predictions = []
                current_input = input_seq
                
                with torch.no_grad():
                    for _ in range(hours_ahead):
                        pred = weather_model(current_input)
                        predictions.append(pred.item())
                        current_input = torch.cat([current_input[:, 1:, :], pred.unsqueeze(0).unsqueeze(0)], dim=1)
                
                # Inverse transform predictions
                predictions = np.array(predictions).reshape(-1, 1)
                predictions = weather_scaler.inverse_transform(predictions).flatten()
                
                return {
                    'timestamps': [ts.isoformat() for ts in timestamps],
                    'temperatures': predictions.tolist()
                }
            except Exception as model_error:
                logger.warning(f"Model prediction failed, using fallback: {str(model_error)}")
        
        # Fallback: Use trend-based prediction
        avg_temp = np.mean(recent_temp)
        temp_std = np.std(recent_temp)
        
        # Simple trend prediction with some randomness
        predictions = []
        for i in range(hours_ahead):
            # Add slight trend and random variation
            trend = np.sin(i * 0.1) * 2  # Daily cycle
            noise = np.random.normal(0, temp_std * 0.1)
            pred_temp = avg_temp + trend + noise
            predictions.append(max(15, min(45, pred_temp)))  # Clamp between 15-45°C
        
        return {
            'timestamps': [ts.isoformat() for ts in timestamps],
            'temperatures': predictions
        }
        
    except Exception as e:
        logger.error(f"Error predicting temperature: {str(e)}")
        return None

def predict_waterflow():
    """Predict waterflow based on precipitation and other factors"""
    global weather_data
    
    if weather_data is None:
        return None
    
    try:
        # Get recent precipitation data
        recent_data = weather_data.tail(48)  # Last 48 hours
        
        # Calculate waterflow based on precipitation and other factors
        precipitation = recent_data['prcp'].fillna(0).values
        humidity = recent_data['rhum'].fillna(50).values
        pressure = recent_data['pres'].fillna(1013).values
        
        # Simple waterflow prediction model (can be enhanced)
        waterflow = []
        for i in range(len(precipitation)):
            # Base waterflow from precipitation
            base_flow = precipitation[i] * 10  # mm to flow rate
            
            # Adjust based on humidity and pressure
            humidity_factor = humidity[i] / 100
            pressure_factor = (pressure[i] - 1000) / 20
            
            # Calculate waterflow
            flow = base_flow * (1 + humidity_factor * 0.5 + pressure_factor * 0.2)
            waterflow.append(max(0, flow))
        
        # Generate future predictions (next 24 hours)
        future_waterflow = []
        for i in range(24):
            # Simple trend-based prediction
            recent_avg = np.mean(waterflow[-6:]) if len(waterflow) >= 6 else np.mean(waterflow)
            trend = np.mean(np.diff(waterflow[-6:])) if len(waterflow) >= 6 else 0
            
            future_flow = recent_avg + trend * (i + 1)
            future_waterflow.append(max(0, future_flow))
        
        # Generate timestamps
        last_time = weather_data['time'].iloc[-1]
        timestamps = [last_time + timedelta(hours=i+1) for i in range(24)]
        
        return {
            'timestamps': [ts.isoformat() for ts in timestamps],
            'waterflow': future_waterflow
        }
        
    except Exception as e:
        logger.error(f"Error predicting waterflow: {str(e)}")
        return None

def calculate_shortest_paths():
    """Calculate shortest paths between emergency nodes"""
    try:
        # Get SOS requests with locations
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT reference_id, city, latitude, longitude, priority, status
            FROM sos_requests 
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            ORDER BY priority DESC, created_at DESC
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        if len(results) < 2:
            return None
        
        # Create nodes from SOS requests
        nodes = []
        for row in results:
            nodes.append({
                'id': row[0],
                'city': row[1],
                'lat': row[2],
                'lon': row[3],
                'priority': row[4],
                'status': row[5]
            })
        
        # Calculate distances between all nodes (simplified)
        paths = []
        for i, node1 in enumerate(nodes):
            for j, node2 in enumerate(nodes[i+1:], i+1):
                # Calculate distance using Haversine formula (simplified)
                lat1, lon1 = node1['lat'], node1['lon']
                lat2, lon2 = node2['lat'], node2['lon']
                
                # Simple distance calculation
                distance = ((lat2 - lat1) ** 2 + (lon2 - lon1) ** 2) ** 0.5 * 111  # Rough km
                
                paths.append({
                    'from': node1['id'],
                    'to': node2['id'],
                    'from_city': node1['city'],
                    'to_city': node2['city'],
                    'distance': round(distance, 2),
                    'from_priority': node1['priority'],
                    'to_priority': node2['priority']
                })
        
        # Sort by distance and priority
        paths.sort(key=lambda x: (x['distance'], -(x['from_priority'] + x['to_priority'])))
        
        return {
            'nodes': nodes,
            'paths': paths[:10]  # Top 10 shortest paths
        }
        
    except Exception as e:
        logger.error(f"Error calculating shortest paths: {str(e)}")
        return None

def calculate_priority(data: Dict) -> int:
    """Calculate priority level based on SOS data"""
    priority = 1  # Low priority by default
    
    # High priority factors
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
    
    # Water emergency type priority (updated for water-focused system)
    water_emergency_priorities = {
        'tsunami': 3,           # Immediate evacuation needed
        'dam-breach': 3,        # Catastrophic flooding
        'flood': 2,             # Life threatening water levels
        'storm': 2,             # Severe weather with water damage
        'water-level-rising': 2, # Growing danger situation
        'coastal-erosion': 1    # Infrastructure risk
    }
    priority += water_emergency_priorities.get(data.get('emergencyType'), 0)
    
    return min(priority, 5)  # Max priority 5

def assign_team_for_emergency(emergency_type, priority, cursor):
    """Auto-assign appropriate team for water emergency"""
    try:
        # For high priority emergencies (4-5), assign AUTO_DEPLOY team (Team Alpha)
        # For lower priority, assign manual teams
        
        if priority >= 4:
            # High priority - assign AUTO_DEPLOY ROV team (Team Alpha)
            cursor.execute('''
                SELECT id, team_name FROM response_teams 
                WHERE deployment_mode = 'AUTO_DEPLOY' AND is_available = 1
                ORDER BY current_load ASC
                LIMIT 1
            ''')
        else:
            # Lower priority - assign manual teams (Team Beta or Supply)
            if emergency_type in ['coastal-erosion', 'water-level-rising']:
                # Less urgent - could be supply team
                cursor.execute('''
                    SELECT id, team_name FROM response_teams 
                    WHERE team_type = 'Water Emergency Supply' AND is_available = 1
                    ORDER BY current_load ASC
                    LIMIT 1
                ''')
            else:
                # Manual ROV deployment needed
                cursor.execute('''
                    SELECT id, team_name FROM response_teams 
                    WHERE deployment_mode = 'MANUAL_DEPLOY' AND team_type = 'ROV Water Rescue' AND is_available = 1
                    ORDER BY current_load ASC
                    LIMIT 1
                ''')
        
        team = cursor.fetchone()
        if team:
            team_id, team_name = team
            logger.info(f"Auto-assigned {team_name} (Priority {priority})")
            return team_id
        else:
            # No teams available, assign Team Alpha as fallback
            logger.warning("No available teams found, assigning Team Alpha as fallback")
            return 1  # Default to Team Alpha
            
    except Exception as e:
        logger.error(f"Error assigning team: {str(e)}")
        return 1  # Default to Team Alpha

def save_sos_request(data: Dict) -> str:
    """Save SOS request to database and return reference ID"""
    reference_id = f"TRD-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    priority = calculate_priority(data)
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    try:
        # Auto-assign team based on emergency priority and availability
        assigned_team_id = assign_team_for_emergency(data.get('emergencyType'), priority, cursor)
        
        cursor.execute('''
            INSERT INTO sos_requests (
                reference_id, name, age, phone, email, address, city, pincode,
                people_to_rescue, people_injured, food_availability, water_availability,
                pregnant, elderly, children, disabled, medical, emergency_type,
                additional_info, latitude, longitude, priority, status, assigned_team_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            reference_id,
            data.get('name'),
            int(data.get('age')),
            data.get('phone'),
            data.get('email'),
            data.get('address'),
            data.get('city'),
            data.get('pincode'),
            int(data.get('peopleToRescue')),
            int(data.get('peopleInjured')),
            data.get('foodAvailability'),
            data.get('waterAvailability'),
            data.get('pregnant') == 'true',
            data.get('elderly') == 'true',
            data.get('children') == 'true',
            data.get('disabled') == 'true',
            data.get('medical') == 'true',
            data.get('emergencyType'),
            data.get('additionalInfo'),
            data.get('latitude'),
            data.get('longitude'),
            priority,
            'pending',
            assigned_team_id
        ))
        
        conn.commit()
        logger.info(f"SOS request saved with reference ID: {reference_id}")
        return reference_id
        
    except Exception as e:
        logger.error(f"Error saving SOS request: {str(e)}")
        conn.rollback()
        raise
    finally:
        conn.close()

def notify_emergency_services(data: Dict, reference_id: str):
    """Notify emergency services about the SOS request"""
    try:
        # Get appropriate response teams
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Find available teams based on emergency type and location
        emergency_type = data.get('emergencyType')
        city = data.get('city', '').lower()
        
        team_type_mapping = {
            'fire': 'Fire & Rescue',
            'earthquake': 'General',
            'flood': 'General',
            'storm': 'General',
            'other': 'General'
        }
        
        preferred_team_type = team_type_mapping.get(emergency_type, 'General')
        
        cursor.execute('''
            SELECT * FROM response_teams 
            WHERE (team_type = ? OR team_type = 'General') 
            AND is_available = TRUE 
            AND current_load < capacity
            ORDER BY 
                CASE WHEN location LIKE ? THEN 0 ELSE 1 END,
                current_load ASC
            LIMIT 3
        ''', (preferred_team_type, f'%{city}%'))
        
        teams = cursor.fetchall()
        
        # Log notification (in real implementation, this would send actual notifications)
        logger.info(f"Notifying emergency services for SOS {reference_id}:")
        logger.info(f"Emergency Type: {emergency_type}")
        logger.info(f"Location: {data.get('address')}, {data.get('city')}")
        logger.info(f"People to Rescue: {data.get('peopleToRescue')}")
        logger.info(f"People Injured: {data.get('peopleInjured')}")
        logger.info(f"Priority: {calculate_priority(data)}")
        logger.info(f"Assigned Teams: {[team[1] for team in teams]}")
        
        # Update team load
        for team in teams:
            cursor.execute('''
                UPDATE response_teams 
                SET current_load = current_load + 1 
                WHERE id = ?
            ''', (team[0],))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error notifying emergency services: {str(e)}")

@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return app.send_static_file(filename)

@app.route('/dashboard')
def dashboard():
    """Serve the dashboard page"""
    return render_template('dashboard.html')

@app.route('/analytics')
def analytics():
    """Serve the analytics page"""
    return render_template('analytics.html')

@app.route('/api/sos', methods=['POST'])
def submit_sos():
    """Handle SOS request submission"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'age', 'phone', 'address', 'city', 'pincode', 
                          'peopleToRescue', 'peopleInjured', 'foodAvailability', 
                          'waterAvailability', 'emergencyType']
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Save SOS request
        reference_id = save_sos_request(data)
        
        # Notify emergency services
        notify_emergency_services(data, reference_id)
        
        # Automatically deploy ROV for high priority water emergencies
        priority = calculate_priority(data)
        if priority >= 4:
            try:
                logger.info(f"🚨 High priority emergency detected (Priority {priority}) - triggering ROV auto-deployment")
                deploy_rov_for_emergency(data, reference_id)
            except Exception as rov_error:
                logger.warning(f"ROV deployment failed for {reference_id}: {str(rov_error)}")
                # Don't fail the SOS request if ROV deployment fails
        
        return jsonify({
            'success': True,
            'referenceId': reference_id,
            'message': 'SOS request submitted successfully',
            'estimatedResponseTime': '5-15 minutes'
        })
        
    except Exception as e:
        logger.error(f"Error processing SOS request: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error. Please try again or contact emergency services directly.'
        }), 500

@app.route('/api/sos/<reference_id>', methods=['GET'])
def get_sos_status(reference_id):
    """Get status of an SOS request"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT reference_id, status, priority, created_at, updated_at
            FROM sos_requests 
            WHERE reference_id = ?
        ''', (reference_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({
                'success': False,
                'message': 'SOS request not found'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'referenceId': result[0],
                'status': result[1],
                'priority': result[2],
                'createdAt': result[3],
                'updatedAt': result[4]
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching SOS status: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@app.route('/api/sos', methods=['GET'])
def get_all_sos():
    """Get all SOS requests (admin endpoint)"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT s.reference_id, s.name, s.phone, s.address, s.city, s.emergency_type, 
                   s.people_to_rescue, s.people_injured, s.food_availability, s.water_availability, 
                   s.priority, s.status, s.created_at, s.assigned_team_id,
                   COALESCE(t.team_name, 'Not assigned') as team_name,
                   COALESCE(t.team_type, '') as team_type
            FROM sos_requests s
            LEFT JOIN response_teams t ON s.assigned_team_id = t.id
            ORDER BY s.priority DESC, s.created_at DESC
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        sos_requests = []
        for row in results:
            sos_requests.append({
                'referenceId': row[0],
                'name': row[1],
                'phone': row[2],
                'address': row[3],
                'city': row[4],
                'emergencyType': row[5],
                'peopleToRescue': row[6],
                'peopleInjured': row[7],
                'foodAvailability': row[8],
                'waterAvailability': row[9],
                'priority': row[10],
                'status': row[11],
                'createdAt': row[12],
                'assignedTeamId': row[13],
                'assignedTeam': row[14],  # This matches what dashboard.js expects
                'teamType': row[15]
            })
        
        return jsonify({
            'success': True,
            'data': sos_requests
        })
        
    except Exception as e:
        logger.error(f"Error fetching SOS requests: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@app.route('/api/emergency-contacts', methods=['GET'])
def get_emergency_contacts():
    """Get emergency contact information"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT name, phone, email, department, location
            FROM emergency_contacts 
            WHERE is_active = TRUE
            ORDER BY department
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        contacts = []
        for row in results:
            contacts.append({
                'name': row[0],
                'phone': row[1],
                'email': row[2],
                'department': row[3],
                'location': row[4]
            })
        
        return jsonify({
            'success': True,
            'data': contacts
        })
        
    except Exception as e:
        logger.error(f"Error fetching emergency contacts: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@app.route('/api/response-teams', methods=['GET'])
def get_response_teams():
    """Get response team information"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, team_name, team_type, contact_phone, contact_email, 
                   location, capacity, current_load, is_available, 
                   deployment_mode, team_description
            FROM response_teams 
            WHERE is_available = TRUE
            ORDER BY team_type, team_name
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        teams = []
        for row in results:
            teams.append({
                'id': row[0],  # Include team ID
                'teamName': row[1],
                'teamType': row[2],
                'contactPhone': row[3],
                'contactEmail': row[4],
                'location': row[5],
                'capacity': row[6],
                'currentLoad': row[7],
                'isAvailable': row[8],
                'deploymentMode': row[9] if len(row) > 9 else 'MANUAL_DEPLOY',
                'description': row[10] if len(row) > 10 else ''
            })
        
        return jsonify({
            'success': True,
            'data': teams
        })
        
    except Exception as e:
        logger.error(f"Error fetching response teams: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Get SOS request statistics
        cursor.execute('SELECT COUNT(*) FROM sos_requests')
        total_sos = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM sos_requests WHERE status = "pending"')
        pending_sos = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM sos_requests WHERE status = "resolved"')
        resolved_sos = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM response_teams WHERE is_available = TRUE')
        available_teams = cursor.fetchone()[0]
        
        # Get additional statistics
        cursor.execute('SELECT COUNT(*) FROM sos_requests WHERE priority >= 4')
        high_priority_sos = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM sos_requests WHERE created_at >= datetime("now", "-24 hours")')
        recent_sos = cursor.fetchone()[0]
        
        # Get emergency type distribution
        cursor.execute('''
            SELECT emergency_type, COUNT(*) as count 
            FROM sos_requests 
            GROUP BY emergency_type 
            ORDER BY count DESC
        ''')
        emergency_types = dict(cursor.fetchall())
        
        # Get status distribution
        cursor.execute('''
            SELECT status, COUNT(*) as count 
            FROM sos_requests 
            GROUP BY status 
            ORDER BY count DESC
        ''')
        status_distribution = dict(cursor.fetchall())
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'totalSOSRequests': total_sos,
                'pendingRequests': pending_sos,
                'resolvedRequests': resolved_sos,
                'availableTeams': available_teams,
                'highPriorityRequests': high_priority_sos,
                'recentRequests24h': recent_sos,
                'emergencyTypeDistribution': emergency_types,
                'statusDistribution': status_distribution
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Get detailed analytics data"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Get hourly SOS requests for the last 24 hours
        cursor.execute('''
            SELECT strftime('%H', created_at) as hour, COUNT(*) as count
            FROM sos_requests 
            WHERE created_at >= datetime('now', '-24 hours')
            GROUP BY strftime('%H', created_at)
            ORDER BY hour
        ''')
        hourly_data = dict(cursor.fetchall())
        
        # Get daily SOS requests for the last 7 days
        cursor.execute('''
            SELECT date(created_at) as day, COUNT(*) as count
            FROM sos_requests 
            WHERE created_at >= datetime('now', '-7 days')
            GROUP BY date(created_at)
            ORDER BY day
        ''')
        daily_data = dict(cursor.fetchall())
        
        # Get priority distribution
        cursor.execute('''
            SELECT priority, COUNT(*) as count
            FROM sos_requests 
            GROUP BY priority
            ORDER BY priority
        ''')
        priority_data = dict(cursor.fetchall())
        
        # Get city-wise distribution
        cursor.execute('''
            SELECT city, COUNT(*) as count
            FROM sos_requests 
            GROUP BY city
            ORDER BY count DESC
            LIMIT 10
        ''')
        city_data = dict(cursor.fetchall())
        
        # Get response time analytics (simulated)
        cursor.execute('''
            SELECT 
                AVG(CASE WHEN status = 'resolved' THEN 
                    (julianday(updated_at) - julianday(created_at)) * 24 * 60 
                END) as avg_response_time_minutes
            FROM sos_requests
        ''')
        avg_response_time = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'hourlyDistribution': hourly_data,
                'dailyDistribution': daily_data,
                'priorityDistribution': priority_data,
                'cityDistribution': city_data,
                'averageResponseTime': round(avg_response_time, 2)
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching analytics: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@app.route('/api/analytics/emergency-types', methods=['GET'])
def get_emergency_types_analytics():
    """Get emergency types distribution"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT emergency_type, COUNT(*) as count
            FROM sos_requests 
            GROUP BY emergency_type
            ORDER BY count DESC
        ''')
        
        emergency_data = []
        for row in cursor.fetchall():
            emergency_data.append({
                'type': row[0],
                'count': row[1]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': emergency_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching emergency types analytics: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/analytics/status-distribution', methods=['GET'])
def get_status_distribution():
    """Get status distribution with percentages"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM sos_requests 
            GROUP BY status
            ORDER BY count DESC
        ''')
        
        status_data = []
        total_requests = 0
        
        for row in cursor.fetchall():
            count = row[1]
            status_data.append({
                'status': row[0],
                'count': count
            })
            total_requests += count
        
        # Add percentages
        for item in status_data:
            item['percentage'] = round((item['count'] / total_requests * 100), 1) if total_requests > 0 else 0
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': status_data,
            'total': total_requests
        })
        
    except Exception as e:
        logger.error(f"Error fetching status distribution: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/ai/temperature-prediction', methods=['GET'])
def get_temperature_prediction():
    """Get AI temperature prediction"""
    try:
        hours = request.args.get('hours', 24, type=int)
        prediction = predict_temperature(hours)
        
        if prediction is None:
            return jsonify({
                'success': False,
                'message': 'AI model not available or error in prediction'
            }), 500
        
        return jsonify({
            'success': True,
            'data': prediction
        })
        
    except Exception as e:
        logger.error(f"Error getting temperature prediction: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@app.route('/api/ai/waterflow-prediction', methods=['GET'])
def get_waterflow_prediction():
    """Get AI waterflow prediction"""
    try:
        prediction = predict_waterflow()
        
        if prediction is None:
            return jsonify({
                'success': False,
                'message': 'AI model not available or error in prediction'
            }), 500
        
        return jsonify({
            'success': True,
            'data': prediction
        })
        
    except Exception as e:
        logger.error(f"Error getting waterflow prediction: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@app.route('/api/ai/shortest-paths', methods=['GET'])
def get_shortest_paths():
    """Get shortest paths between emergency nodes"""
    try:
        paths = calculate_shortest_paths()
        
        if paths is None:
            return jsonify({
                'success': False,
                'message': 'Not enough emergency nodes to calculate paths'
            }), 400
        
        return jsonify({
            'success': True,
            'data': paths
        })
        
    except Exception as e:
        logger.error(f"Error getting shortest paths: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@app.route('/api/ai/weather-data', methods=['GET'])
def get_weather_data():
    """Get recent weather data for analysis"""
    try:
        global weather_data
        
        if weather_data is None:
            return jsonify({
                'success': False,
                'message': 'Weather data not available'
            }), 500
        
        # Get last 24 hours of data
        recent_data = weather_data.tail(24)
        
        weather_info = {
            'timestamps': recent_data['time'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
            'temperature': recent_data['temp'].tolist(),
            'humidity': recent_data['rhum'].tolist(),
            'precipitation': recent_data['prcp'].fillna(0).tolist(),
            'pressure': recent_data['pres'].fillna(1013).tolist(),
            'wind_speed': recent_data['wspd'].fillna(0).tolist()
        }
        
        return jsonify({
            'success': True,
            'data': weather_info
        })
        
    except Exception as e:
        logger.error(f"Error getting weather data: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@app.route('/api/sos/<reference_id>/update-status', methods=['PUT'])
def update_sos_status(reference_id):
    """Update SOS request status"""
    try:
        data = request.get_json()
        new_status = data.get('status')
        notes = data.get('notes', '')
        updated_by = data.get('updated_by', 'System')
        
        valid_statuses = ['pending', 'assigned', 'in-progress', 'resolved', 'cancelled']
        if new_status not in valid_statuses:
            return jsonify({
                'success': False,
                'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }), 400
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Update SOS request status
        cursor.execute('''
            UPDATE sos_requests 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE reference_id = ?
        ''', (new_status, reference_id))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'SOS request not found'
            }), 404
        
        # Add status history record
        cursor.execute('''
            INSERT OR IGNORE INTO sos_status_history (reference_id, status, notes, updated_by)
            VALUES (?, ?, ?, ?)
        ''', (reference_id, new_status, notes, updated_by))
        
        conn.commit()
        conn.close()
        
        # If mission is resolved or cancelled, complete any active ROV missions
        if new_status in ['resolved', 'cancelled']:
            with rov_mission_lock:
                for rov_id, mission_id in active_rov_missions.items():
                    if mission_id == reference_id:
                        complete_rov_mission(rov_id)
                        logger.info(f"🏁 Mission {reference_id} completed - {rov_id} now available for deployment")
        
        logger.info(f"SOS request {reference_id} status updated to {new_status} by {updated_by}")
        
        return jsonify({
            'success': True,
            'message': 'SOS status updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating SOS status: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@app.route('/api/sos/<reference_id>/assign-team', methods=['PUT'])
def assign_team_to_sos(reference_id):
    """Assign response team to SOS request"""
    try:
        data = request.get_json()
        team_id = data.get('team_id')
        assigned_by = data.get('assigned_by', 'System')
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Check if SOS request exists
        cursor.execute('SELECT id FROM sos_requests WHERE reference_id = ?', (reference_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({
                'success': False,
                'message': 'SOS request not found'
            }), 404
        
        # Check if team exists and is available
        cursor.execute('''
            SELECT id, team_name, current_load, capacity 
            FROM response_teams 
            WHERE id = ? AND is_available = TRUE
        ''', (team_id,))
        
        team = cursor.fetchone()
        if not team:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Team not found or not available'
            }), 404
        
        if team[2] >= team[3]:  # current_load >= capacity
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Team is at full capacity'
            }), 400
        
        # Assign team and update status
        cursor.execute('''
            UPDATE sos_requests 
            SET assigned_team_id = ?, status = 'assigned', updated_at = CURRENT_TIMESTAMP
            WHERE reference_id = ?
        ''', (team_id, reference_id))
        
        # Update team load
        cursor.execute('''
            UPDATE response_teams 
            SET current_load = current_load + 1 
            WHERE id = ?
        ''', (team_id,))
        
        # Add assignment history
        cursor.execute('''
            INSERT OR IGNORE INTO sos_assignments (reference_id, team_id, assigned_by)
            VALUES (?, ?, ?)
        ''', (reference_id, team_id, assigned_by))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Team {team[1]} assigned to SOS {reference_id} by {assigned_by}")
        
        return jsonify({
            'success': True,
            'message': f'Team {team[1]} assigned successfully'
        })
        
    except Exception as e:
        logger.error(f"Error assigning team: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@app.route('/api/sos/<reference_id>/add-note', methods=['POST'])
def add_sos_note(reference_id):
    """Add note to SOS request"""
    try:
        data = request.get_json()
        note = data.get('note', '').strip()
        author = data.get('author', 'System')
        
        if not note:
            return jsonify({
                'success': False,
                'message': 'Note content is required'
            }), 400
        
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Check if SOS request exists
        cursor.execute('SELECT id FROM sos_requests WHERE reference_id = ?', (reference_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({
                'success': False,
                'message': 'SOS request not found'
            }), 404
        
        # Add note
        cursor.execute('''
            INSERT INTO sos_notes (reference_id, note, author)
            VALUES (?, ?, ?)
        ''', (reference_id, note, author))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Note added successfully'
        })
        
    except Exception as e:
        logger.error(f"Error adding note: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@app.route('/api/rov-status', methods=['GET'])
def get_rov_status():
    """Get ROV deployment status"""
    try:
        # Get real-time ROV status based on active missions
        with rov_mission_lock:
            alpha_mission = active_rov_missions.get('ROV-001')
            beta_mission = active_rov_missions.get('ROV-002') 
            gamma_mission = active_rov_missions.get('ROV-003')
        
        deployed_count = sum(1 for mission in [alpha_mission, beta_mission, gamma_mission] if mission)
        
        rov_data = {
            'total_rovs': 3,
            'active_rovs': 3 - deployed_count,  # Available ROVs
            'deployed_rovs': deployed_count,
            'maintenance_rovs': 0,
            'rovs': [
                {
                    'id': 'ROV-001',
                    'name': 'Chennai Rescue ROV Alpha',
                    'status': 'deployed' if alpha_mission else 'active',
                    'location': {'lat': 13.0827, 'lon': 80.2707},
                    'battery': 78 if alpha_mission else 100,
                    'assigned_request': alpha_mission,
                    'last_update': datetime.now().isoformat(),
                    'deployment_mode': 'AUTO_DEPLOY'
                },
                {
                    'id': 'ROV-002',
                    'name': 'Chennai Rescue ROV Beta',
                    'status': 'deployed' if beta_mission else 'active',
                    'location': {'lat': 13.0878, 'lon': 80.2785},
                    'battery': 92 if beta_mission else 100,
                    'assigned_request': beta_mission,
                    'last_update': datetime.now().isoformat(),
                    'deployment_mode': 'MANUAL_DEPLOY'
                },
                {
                    'id': 'ROV-003',
                    'name': 'Chennai Rescue ROV Gamma',
                    'status': 'deployed' if gamma_mission else 'docked',
                    'location': {'lat': 13.0827, 'lon': 80.2707},
                    'battery': 100 if gamma_mission else 100,
                    'assigned_request': gamma_mission,
                    'last_update': datetime.now().isoformat(),
                    'deployment_mode': 'MANUAL_DEPLOY'
                }
            ]
        }
        
        return jsonify({
            'success': True,
            'data': rov_data
        })
        
    except Exception as e:
        logger.error(f"Error getting ROV status: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

# ROV Control and Deployment Functions
import subprocess
import threading

# Global mission tracking
active_rov_missions = {
    'ROV-001': None,  # Chennai Rescue ROV Alpha
    'ROV-002': None,  # Chennai Rescue ROV Beta  
    'ROV-003': None   # Chennai Rescue ROV Gamma
}

rov_mission_lock = threading.Lock()

def is_rov_available(rov_id='ROV-001'):
    """Check if specific ROV is available for deployment"""
    with rov_mission_lock:
        return active_rov_missions.get(rov_id) is None

def set_rov_mission(rov_id, reference_id):
    """Set ROV as deployed for specific mission"""
    with rov_mission_lock:
        active_rov_missions[rov_id] = reference_id
        logger.info(f"🚁 {rov_id} now assigned to mission {reference_id}")

def complete_rov_mission(rov_id):
    """Mark ROV mission as completed and ROV available"""
    with rov_mission_lock:
        old_mission = active_rov_missions.get(rov_id)
        active_rov_missions[rov_id] = None
        logger.info(f"✅ {rov_id} mission {old_mission} completed - ROV now available")

def deploy_rov_for_emergency(emergency_data, reference_id):
    """Automatically deploy ROV for water emergency - only for AUTO_DEPLOY teams"""
    try:
        # Check if we should auto-deploy based on team assignment
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Get the assigned team for this request
        cursor.execute('''
            SELECT rt.deployment_mode, rt.team_name, rt.team_type
            FROM sos_requests sr
            JOIN response_teams rt ON sr.assigned_team_id = rt.id
            WHERE sr.reference_id = ?
        ''', (reference_id,))
        
        team_info = cursor.fetchone()
        conn.close()
        
        if not team_info:
            logger.warning(f"No team assigned for emergency {reference_id} - skipping auto-deployment")
            return
            
        deployment_mode, team_name, team_type = team_info
        
        # Only auto-deploy if team has AUTO_DEPLOY mode
        if deployment_mode != 'AUTO_DEPLOY':
            logger.info(f"Team {team_name} has {deployment_mode} mode - skipping auto-deployment")
            logger.info(f"Emergency {reference_id} requires manual ROV deployment")
            return
        
        # Check if Alpha ROV is already deployed
        if not is_rov_available('ROV-001'):
            current_mission = active_rov_missions['ROV-001']
            logger.warning(f"🚫 ROV Alpha already deployed on mission {current_mission}")
            logger.warning(f"Emergency {reference_id} will need to wait or use manual deployment")
            return
        
        # Reserve the ROV for this mission
        set_rov_mission('ROV-001', reference_id)
        
        logger.info(f"🚁 Auto-deploying {team_name} for emergency {reference_id}")
        
        # Calculate AI path planning (simulated for prototype)
        path_data = calculate_emergency_path(emergency_data)
        
        # Start ROV deployment in separate thread
        threading.Thread(
            target=execute_rov_deployment,
            args=(emergency_data, reference_id, path_data, team_name),
            daemon=True
        ).start()
        
        logger.info(f"ROV deployment initiated for emergency {reference_id} with {team_name}")
        
    except Exception as e:
        logger.error(f"ROV deployment failed: {str(e)}")
        # Release ROV if deployment fails
        complete_rov_mission('ROV-001')
        raise

def calculate_emergency_path(emergency_data):
    """Calculate optimal path for ROV deployment (AI path planning)"""
    # Extract location data
    address = emergency_data.get('address', '')
    city = emergency_data.get('city', 'Chennai')
    emergency_type = emergency_data.get('emergencyType', 'flood')
    
    # Simulated AI path planning (in real implementation, this would use actual AI)
    path_data = {
        'start_point': {'lat': 13.0827, 'lon': 80.2707},  # ROV base station
        'end_point': {'lat': 13.0845, 'lon': 80.2795},    # Emergency location (simulated)
        'waypoints': [
            {'lat': 13.0830, 'lon': 80.2720},
            {'lat': 13.0835, 'lon': 80.2750},
            {'lat': 13.0840, 'lon': 80.2780}
        ],
        'distance': 2.4,  # km
        'estimated_travel_time': 12,  # minutes
        'emergency_type': emergency_type,
        'optimal_depth': 2.5,  # meters
        'current_conditions': 'moderate'
    }
    
    logger.info(f"Path calculated: {path_data['distance']}km, {path_data['estimated_travel_time']} min ETA")
    return path_data

def execute_rov_deployment(emergency_data, reference_id, path_data, team_name="ROV Team Alpha"):
    """Execute ROV deployment with automatic thruster activation"""
    try:
        # 1. Immediately open ROV console for emergency control
        logger.info(f"🚁 {team_name} - Opening ROV console for emergency control...")
        try:
            console_path = os.path.join(os.getcwd(), 'ROVER_Console', 'importserial.py')
            logger.info(f"Launching ROV console at: {console_path}")
            
            subprocess.Popen([
                'python', 
                console_path,
                '--emergency-mode',
                f'--mission-id={reference_id}'
            ], cwd=os.getcwd())
            
            logger.info(f"✅ ROV console launched successfully for mission {reference_id} (Team: {team_name})")
        except Exception as console_error:
            logger.error(f"❌ Failed to open ROV console: {console_error}")
            logger.error(f"Console path: {os.path.join(os.getcwd(), 'ROVER_Console', 'importserial.py')}")
            # Continue with deployment even if console fails
        
        # 2. Wait for path planning completion (10-15 seconds as requested)
        wait_time = 12  # seconds (prototype timing)
        logger.info(f"🧠 {team_name} - Path planning complete. ROV deployment in {wait_time} seconds...")
        time.sleep(wait_time)
        
        # 3. Automatically activate thrusters and start mission
        logger.info(f"🚀 {team_name} - ACTIVATING ROV THRUSTERS - MISSION START!")
        
        # Send commands to ROV (this would interface with actual hardware)
        rov_commands = {
            'action': 'deploy',
            'mission_id': reference_id,
            'target_location': path_data['end_point'],
            'path': path_data['waypoints'],
            'emergency_type': emergency_data.get('emergencyType'),
            'thruster_power': 75,  # percentage
            'depth_target': path_data['optimal_depth'],
            'auto_pilot': True
        }
        
        # Simulate ROV activation
        simulate_rov_activation(rov_commands)
        
        logger.info(f"ROV deployed successfully for mission {reference_id}")
        
    except Exception as e:
        logger.error(f"ROV deployment execution failed: {str(e)}")

def simulate_rov_activation(commands):
    """Simulate ROV thruster activation and movement"""
    logger.info("ROV THRUSTERS: ONLINE ✅")
    logger.info(f"Mission ID: {commands['mission_id']}")
    logger.info(f"Target: {commands['target_location']}")
    logger.info(f"Thruster Power: {commands['thruster_power']}%")
    logger.info(f"Auto-pilot: {'ENABLED' if commands['auto_pilot'] else 'DISABLED'}")
    logger.info("ROV is now en route to emergency location!")

@app.route('/api/rov/deploy', methods=['POST'])
def deploy_rov():
    """Manual ROV deployment endpoint"""
    try:
        data = request.get_json()
        reference_id = data.get('reference_id')
        
        if not reference_id:
            return jsonify({
                'success': False,
                'message': 'Missing reference_id'
            }), 400
        
        # Get emergency data from database
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM sos_requests WHERE reference_id = ?
        ''', (reference_id,))
        
        request_data = cursor.fetchone()
        conn.close()
        
        if not request_data:
            return jsonify({
                'success': False,
                'message': 'Emergency request not found'
            }), 404
        
        # Convert to dictionary for deployment
        emergency_data = {
            'address': request_data[4],  # address column
            'city': request_data[5],     # city column
            'emergencyType': request_data[13]  # emergency_type column
        }
        
        # Deploy ROV
        deploy_rov_for_emergency(emergency_data, reference_id)
        
        return jsonify({
            'success': True,
            'message': 'ROV deployment initiated',
            'reference_id': reference_id
        })
        
    except Exception as e:
        logger.error(f"Error deploying ROV: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'ROV deployment failed'
        }), 500

@app.route('/api/rov/mission-complete', methods=['POST'])
def complete_rov_mission_endpoint():
    """Complete ROV mission and make ROV available"""
    try:
        data = request.get_json()
        reference_id = data.get('reference_id')
        rov_id = data.get('rov_id', 'ROV-001')  # Default to Alpha
        
        if not reference_id:
            return jsonify({
                'success': False,
                'message': 'Missing reference_id'
            }), 400
        
        # Check if this ROV is actually assigned to this mission
        with rov_mission_lock:
            current_mission = active_rov_missions.get(rov_id)
            if current_mission != reference_id:
                return jsonify({
                    'success': False,
                    'message': f'ROV {rov_id} is not assigned to mission {reference_id}'
                }), 400
        
        # Complete the mission
        complete_rov_mission(rov_id)
        
        return jsonify({
            'success': True,
            'message': f'ROV {rov_id} mission {reference_id} completed successfully'
        })
        
    except Exception as e:
        logger.error(f"Error completing ROV mission: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to complete ROV mission'
        }), 500

@app.route('/api/rov/emergency-stop', methods=['POST'])
def emergency_stop_rov():
    """Emergency stop for all active ROVs"""
    try:
        logger.warning("🛑 EMERGENCY STOP ACTIVATED!")
        
        # This would send emergency stop commands to all active ROVs
        # For prototype, we'll log the action
        
        return jsonify({
            'success': True,
            'message': 'Emergency stop activated for all ROVs'
        })
        
    except Exception as e:
        logger.error(f"Error during emergency stop: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Emergency stop failed'
        }), 500

@app.route('/api/rov/status/<rov_id>', methods=['GET'])
def get_specific_rov_status(rov_id):
    """Get status of specific ROV"""
    try:
        # This would query actual ROV status
        # For prototype, return simulated data
        
        rov_status = {
            'id': rov_id,
            'status': 'deployed',
            'location': {'lat': 13.0845, 'lon': 80.2795},
            'depth': 2.5,
            'battery': 78,
            'thruster_power': 75,
            'mission_progress': 45,
            'sensors': {
                'temperature': 28.5,
                'pressure': 1.25,
                'visibility': 3.2,
                'current_speed': 0.8
            },
            'last_update': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'data': rov_status
        })
        
    except Exception as e:
        logger.error(f"Error getting ROV status: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Failed to get ROV status'
        }), 500

@app.route('/api/wearable-devices', methods=['GET'])
def get_wearable_status():
    """Get connected wearable devices status"""
    try:
        # This would interface with your wearable device system
        # For now, return simulated data
        wearable_data = {
            'total_devices': 15,
            'online_devices': 12,
            'emergency_devices': 2,
            'low_battery_devices': 1,
            'devices': [
                {
                    'device_id': 'WEAR-001',
                    'user_name': 'Rajesh Kumar',
                    'status': 'emergency',
                    'battery': 45,
                    'location': {'lat': 13.0845, 'lon': 80.2795},
                    'last_heartbeat': datetime.now().isoformat(),
                    'emergency_type': 'fall_detected'
                },
                {
                    'device_id': 'WEAR-002',
                    'user_name': 'Priya Sharma',
                    'status': 'emergency',
                    'battery': 67,
                    'location': {'lat': 13.0756, 'lon': 80.2834},
                    'last_heartbeat': datetime.now().isoformat(),
                    'emergency_type': 'panic_button'
                }
            ]
        }
        
        return jsonify({
            'success': True,
            'data': wearable_data
        })
        
    except Exception as e:
        logger.error(f"Error getting wearable status: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error'
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'message': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'message': 'Internal server error'
    }), 500

if __name__ == '__main__':
    # Initialize database
    init_database()
    
    # Initialize AI model
    init_ai_model()
    
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000)

