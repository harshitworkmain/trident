# 🚀 Trident Emergency Response System - Setup & Run Guide

## 📋 Prerequisites

Before running the system, ensure you have:

- **Python 3.8+** installed on your system
- **pip** (Python package installer)
- **Git** (optional, for version control)
- **Web browser** (Chrome, Firefox, Safari, or Edge)

## 🛠️ Installation Steps

### Step 1: Navigate to Project Directory
```bash
cd "c:\loopster\Akshay\Chennai_Weather_AI_System"
```

### Step 2: Create Virtual Environment (Recommended)
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Verify Installation
```bash
python -c "import flask; print('Flask installed successfully!')"
```

## 🚀 Running the Application

### Method 1: Development Server (Recommended for Testing)
```bash
python app.py
```

The application will start and you'll see output like:
```
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://[your-ip]:5000
```

### Method 2: Production Server (For Deployment)
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 🌐 Accessing the Application

Once the server is running, open your web browser and navigate to:

### Main Pages:
- **Home/SOS Form**: http://localhost:5000
- **Dashboard**: http://localhost:5000/dashboard
- **Analytics**: http://localhost:5000/analytics

### API Endpoints:
- **Submit SOS**: POST http://localhost:5000/api/sos
- **Get All SOS**: GET http://localhost:5000/api/sos
- **Get Statistics**: GET http://localhost:5000/api/stats
- **Get Analytics**: GET http://localhost:5000/api/analytics
- **Get Emergency Contacts**: GET http://localhost:5000/api/emergency-contacts
- **Get Response Teams**: GET http://localhost:5000/api/response-teams

## 📱 Features Overview

### 1. **Emergency SOS Form** (`/`)
- Complete emergency reporting form
- Real-time form validation
- Auto-save functionality
- Location detection
- Priority calculation

### 2. **Live Dashboard** (`/dashboard`)
- Real-time emergency statistics
- SOS requests table
- Response teams status
- Emergency contacts
- Auto-refresh every 30 seconds

### 3. **Analytics Dashboard** (`/analytics`)
- Emergency type distribution
- Hourly/daily trends
- Geographic analysis
- Performance metrics
- Interactive charts

## 🗄️ Database

The system uses SQLite database (`trident_sos.db`) which is automatically created with:
- **SOS Requests Table**: Stores all emergency requests
- **Emergency Contacts Table**: Stores emergency contact information
- **Response Teams Table**: Stores rescue team information

## 🔧 Configuration

### Environment Variables (Optional)
Create a `.env` file in the project root:
```env
FLASK_ENV=development
FLASK_DEBUG=True
DATABASE_URL=sqlite:///trident_sos.db
SECRET_KEY=your-secret-key-here
```

### Port Configuration
To change the port, modify the last line in `app.py`:
```python
app.run(debug=True, host='0.0.0.0', port=8080)  # Change 5000 to your desired port
```

## 🧪 Testing the System

### 1. Test SOS Submission
1. Go to http://localhost:5000
2. Fill out the emergency form
3. Submit the form
4. Check the dashboard to see the new request

### 2. Test Dashboard
1. Go to http://localhost:5000/dashboard
2. Verify statistics are displayed
3. Check that SOS requests appear in the table
4. Test the refresh functionality

### 3. Test Analytics
1. Go to http://localhost:5000/analytics
2. Navigate between different tabs
3. Verify charts are loading
4. Check data accuracy

## 🚨 Troubleshooting

### Common Issues:

#### 1. **Port Already in Use**
```bash
# Find process using port 5000
netstat -ano | findstr :5000
# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

#### 2. **Module Not Found Errors**
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

#### 3. **Database Issues**
```bash
# Delete database file to reset
del trident_sos.db
# Restart the application
python app.py
```

#### 4. **CORS Issues**
The application includes Flask-CORS, but if you encounter issues:
```python
# In app.py, ensure CORS is properly configured
from flask_cors import CORS
CORS(app)
```

## 📊 Sample Data

The system comes with sample data:
- **5 Emergency Contacts**: Police, Fire, Medical, etc.
- **5 Response Teams**: Various rescue teams in different cities
- **Sample SOS Requests**: Will be created as you test the form

## 🔒 Security Notes

### For Development:
- The system runs in debug mode
- Database is SQLite (file-based)
- No authentication required

### For Production:
- Set `debug=False` in `app.py`
- Use a proper database (PostgreSQL, MySQL)
- Implement authentication
- Use HTTPS
- Set up proper logging

## 📈 Performance

### System Requirements:
- **RAM**: Minimum 512MB, Recommended 1GB+
- **CPU**: Any modern processor
- **Storage**: 100MB for application + database growth
- **Network**: Local network or internet access

### Optimization Tips:
- Use production server (Gunicorn) for better performance
- Implement database indexing for large datasets
- Use CDN for static assets in production
- Enable gzip compression

## 🚀 Deployment Options

### 1. **Local Network**
```bash
# Run on all network interfaces
python app.py
# Access from other devices: http://[your-ip]:5000
```

### 2. **Cloud Deployment**
- **Heroku**: Use Procfile and requirements.txt
- **AWS**: Use EC2 with Gunicorn
- **DigitalOcean**: Use App Platform
- **Google Cloud**: Use App Engine

### 3. **Docker Deployment**
Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

## 📞 Support

If you encounter any issues:
1. Check the console output for error messages
2. Verify all dependencies are installed
3. Ensure Python version is 3.8+
4. Check if port 5000 is available
5. Review the troubleshooting section above

## 🎯 Quick Start Commands

```bash
# Complete setup and run
cd "c:\loopster\Akshay\Chennai_Weather_AI_System"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open: http://localhost:5000

---

**🎉 You're all set! The Trident Emergency Response System is now ready to use.**
