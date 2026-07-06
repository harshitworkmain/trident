import sys
import os

# Ensure the project root and src/ are in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.backend.main import app, init_database, init_ai_model

# Initialize database and AI model on startup
init_database()
init_ai_model()

if __name__ == '__main__':
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000)
