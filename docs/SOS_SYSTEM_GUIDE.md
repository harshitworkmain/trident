# 🛡️ Trident - Disaster Help & SOS System

A comprehensive emergency response system designed to help people report SOS messages during disasters and emergencies. The system collects detailed information about the emergency situation and coordinates with rescue teams for timely assistance.

## 🌟 Features

### 🚨 SOS Reporting System
- **Personal Information**: Name, age, contact details
- **Location Details**: Current address, city, pincode with GPS coordinates
- **Emergency Details**: 
  - Number of people needing rescue
  - Number of people injured
  - Food and water availability status
- **Special Conditions**: 
  - Pregnant persons
  - Elderly persons (65+ years)
  - Children (under 12 years)
  - Persons with disabilities
  - Medical attention requirements
- **Emergency Types**: Flood, Earthquake, Fire, Storm/Cyclone, Other

### 🎯 Smart Features
- **Priority Calculation**: Automatic priority assignment based on emergency severity
- **Real-time Validation**: Form validation with error handling
- **Auto-save**: Form data automatically saved to prevent data loss
- **GPS Integration**: Automatic location detection for accurate positioning
- **Responsive Design**: Works on desktop, tablet, and mobile devices

### 🔧 Backend API
- **RESTful API**: Complete backend with Flask
- **Database Integration**: SQLite database for data persistence
- **Emergency Coordination**: Automatic team assignment and notification
- **Status Tracking**: Real-time SOS request status updates
- **Admin Dashboard**: System statistics and management

## 🚀 Quick Start

### Prerequisites
- Python 3.7 or higher
- Modern web browser
- Internet connection (for GPS and external services)

### Installation

1. **Clone or download the project files**
   ```bash
   # Navigate to the project directory
   cd Chennai_Weather_AI_System
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Access the application**
   - Open your web browser
   - Navigate to `http://localhost:5000`
   - The Trident SOS system will be ready to use!

## 📱 Usage

### For Emergency Reporting
1. **Fill out the SOS form** with all required information
2. **Provide accurate location details** for faster response
3. **Specify special conditions** (pregnant, elderly, children, disabled)
4. **Submit the form** - you'll receive a reference ID
5. **Keep the reference ID** for status tracking

### For Emergency Services
- **API Endpoints** available for integration with existing systems
- **Real-time notifications** for new SOS requests
- **Priority-based routing** to appropriate response teams
- **Status management** for tracking response progress

## 🔌 API Endpoints

### SOS Management
- `POST /api/sos` - Submit new SOS request
- `GET /api/sos/<reference_id>` - Get SOS request status
- `GET /api/sos` - Get all SOS requests (admin)

### System Information
- `GET /api/emergency-contacts` - Get emergency contact numbers
- `GET /api/response-teams` - Get available response teams
- `GET /api/stats` - Get system statistics

### Example API Usage
```javascript
// Submit SOS request
fetch('/api/sos', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        name: 'John Doe',
        age: 30,
        phone: '9876543210',
        address: '123 Main Street',
        city: 'Chennai',
        pincode: '600001',
        peopleToRescue: 3,
        peopleInjured: 1,
        foodAvailability: 'limited',
        waterAvailability: 'sufficient',
        emergencyType: 'flood',
        // ... other fields
    })
})
.then(response => response.json())
.then(data => console.log(data));
```

## 🗄️ Database Schema

### SOS Requests Table
- Personal information (name, age, contact details)
- Location data (address, coordinates)
- Emergency details (people count, injuries, resources)
- Special conditions (pregnant, elderly, children, disabled)
- Priority and status tracking
- Timestamps for audit trail

### Emergency Contacts Table
- Contact information for emergency services
- Department categorization
- Location-based routing

### Response Teams Table
- Team details and capabilities
- Current load and availability
- Location and contact information

## 🎨 Frontend Features

### Modern UI/UX
- **Responsive Design**: Works on all device sizes
- **Accessibility**: WCAG compliant design
- **Progressive Web App**: Offline functionality support
- **Real-time Validation**: Instant form feedback
- **Smooth Animations**: Professional user experience

### User Experience
- **Auto-save**: Never lose form data
- **GPS Integration**: Automatic location detection
- **Keyboard Shortcuts**: Ctrl+Enter to submit
- **Error Handling**: Clear error messages and recovery
- **Success Feedback**: Confirmation with reference ID

## 🔒 Security Features

- **Input Validation**: Server-side validation for all inputs
- **SQL Injection Protection**: Parameterized queries
- **CORS Configuration**: Secure cross-origin requests
- **Error Handling**: Secure error messages
- **Data Sanitization**: Clean input processing

## 📊 Priority System

The system automatically calculates priority levels (1-5) based on:

### High Priority Factors (+2 points each)
- People injured
- Medical attention required

### Medium Priority Factors (+1 point each)
- Pregnant persons present
- Elderly persons present
- Children present
- Persons with disabilities
- Critical food/water shortage

### Emergency Type Priority
- Fire: +2 points
- Earthquake: +2 points
- Flood: +1 point
- Storm: +1 point

## 🚁 Emergency Response Flow

1. **SOS Submission**: User submits emergency request
2. **Priority Calculation**: System calculates priority level
3. **Team Assignment**: Appropriate response teams are notified
4. **Status Tracking**: Real-time status updates
5. **Resolution**: Emergency resolved and marked complete

## 🛠️ Development

### Project Structure
```
Chennai_Weather_AI_System/
├── index.html          # Main frontend page
├── styles.css          # CSS styling
├── script.js           # Frontend JavaScript
├── app.py              # Flask backend
├── requirements.txt    # Python dependencies
├── README.md          # Documentation
└── trident_sos.db     # SQLite database (created automatically)
```

### Adding New Features
1. **Frontend**: Modify HTML, CSS, or JavaScript files
2. **Backend**: Add new routes in `app.py`
3. **Database**: Update schema in `init_database()` function
4. **API**: Add new endpoints following RESTful conventions

### Testing
```bash
# Run the Flask application in debug mode
python app.py

# Test API endpoints
curl -X POST http://localhost:5000/api/sos \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","age":30,...}'
```

## 🌐 Deployment

### Local Development
```bash
python app.py
```

### Production Deployment
```bash
# Install production server
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Environment Variables
Create a `.env` file for configuration:
```
FLASK_ENV=production
DATABASE_URL=sqlite:///trident_sos.db
SECRET_KEY=your-secret-key-here
```

## 📞 Emergency Contacts

- **General Emergency**: 100
- **Fire Department**: 101
- **Medical Emergency**: 108
- **Police**: 100
- **Disaster Management**: 108

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For technical support or emergency assistance:
- **Email**: support@trident-emergency.com
- **Phone**: 24/7 Emergency Hotline
- **Documentation**: This README file

## 🔮 Future Enhancements

- **SMS Integration**: Send SMS notifications
- **Push Notifications**: Real-time mobile notifications
- **AI Integration**: Smart emergency classification
- **Multi-language Support**: Localization for different regions
- **Mobile App**: Native mobile application
- **IoT Integration**: Sensor-based emergency detection
- **Blockchain**: Secure and immutable emergency records

---

**⚠️ Important**: This is an emergency response system. In case of real emergencies, always contact local emergency services directly using the numbers provided above.

**🛡️ Trident - Your Shield in Times of Crisis**

