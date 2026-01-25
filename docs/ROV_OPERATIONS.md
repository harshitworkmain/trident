🌊 HOW TO TEST ROV INTEGRATION SYSTEM
=====================================

## 🚀 Quick Test Steps:

### Step 1: Verify Flask Server
✅ Your Flask server is running on http://127.0.0.1:5000
   (I can see it's active in your terminal)

### Step 2: Open Emergency Form
1. Open your web browser
2. Go to: http://127.0.0.1:5000
3. You should see the water emergency form with anchor icon

### Step 3: Submit Test Emergency
Fill out the form with test data:

📋 **Test Data:**
- Name: Test Emergency
- Age: 30
- Phone: 9876543210
- Address: Marina Beach, Chennai
- City: Chennai
- Pincode: 600001
- People to Rescue: 2
- People Injured: 1
- Food Availability: Critical
- Water Availability: None
- Emergency Type: **TSUNAMI** (select this!)
- Special Conditions: Check "Elderly" and "Children"
- Additional Info: "Test ROV deployment system"

### Step 4: Watch for ROV Activation
After clicking "Send SOS Request":

🔍 **What to Look For:**

1. **In Flask Terminal (your current terminal):**
   ```
   INFO:__main__:ROV deployment initiated for emergency TRD-xxxxx
   INFO:__main__:Path calculated: 2.4km, 12 min ETA
   INFO:__main__:Opening ROV console for emergency control...
   INFO:__main__:Path planning complete. ROV deployment in 12 seconds...
   INFO:__main__:🚀 ACTIVATING ROV THRUSTERS - MISSION START!
   INFO:__main__:ROV THRUSTERS: ONLINE ✅
   INFO:__main__:Mission ID: TRD-xxxxx
   INFO:__main__:Thruster Power: 75%
   INFO:__main__:Auto-pilot: ENABLED
   ```

2. **ROV Console Window Should Pop Up:**
   - Title: "🚨 EMERGENCY ROV CONTROL - MISSION ACTIVE"
   - Window stays on top
   - Shows mission ID
   - Has emergency stop button

3. **Expected Timing:**
   - Console opens: IMMEDIATELY
   - Countdown: 12 seconds
   - Thrusters activate: Automatically after countdown

### Step 5: Manual ROV Console Test
You can also test the ROV console independently:

```cmd
cd "C:\Users\shtan\Downloads\Akshay\Chennai_Weather_AI_System"
python ROVER_Console\importserial.py --emergency-mode --mission-id=TEST-123
```

This should:
- Open ROV console in emergency mode
- Show "🚨 EMERGENCY ROV CONTROL - MISSION ACTIVE"
- Auto-activate thrusters after 12 seconds

## 🔧 Troubleshooting:

### If ROV Console Doesn't Open:
- Check if PyQt6 is installed: `pip install PyQt6`
- Try running manually: `python ROVER_Console\importserial.py`

### If No Flask Logs Appear:
- Make sure you submitted a WATER emergency type (not fire/earthquake)
- Check the terminal running app.py for error messages

### If Form Submission Fails:
- Check Flask server is running on http://127.0.0.1:5000
- Try refreshing the webpage

## 📊 Success Indicators:
✅ Emergency form submits successfully
✅ Reference ID returned (TRD-YYYYMMDD-XXXXXX format)
✅ Flask logs show ROV deployment messages
✅ ROV console opens with emergency title
✅ 12-second countdown completes
✅ Thrusters activate automatically

## 🚨 Emergency Stop:
- Click "EMERGENCY STOP" button in ROV console anytime
- This will halt all ROV operations immediately

---
💡 The ROV console may require PyQt6. If it doesn't open, the deployment will still be logged in Flask terminal.