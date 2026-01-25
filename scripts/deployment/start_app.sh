#!/bin/bash

echo "========================================"
echo "  Trident Emergency Response System"
echo "========================================"
echo

echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.8+ and try again"
    exit 1
fi

echo "Python found! Checking virtual environment..."
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment"
        exit 1
    fi
fi

echo "Activating virtual environment..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to activate virtual environment"
    exit 1
fi

echo "Installing/updating dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo
echo "========================================"
echo "  Starting Trident Emergency System"
echo "========================================"
echo
echo "The application will start in a few seconds..."
echo
echo "Access URLs:"
echo "  Main App:    http://localhost:5000"
echo "  Dashboard:   http://localhost:5000/dashboard"
echo "  Analytics:   http://localhost:5000/analytics"
echo
echo "Press Ctrl+C to stop the server"
echo

python app.py

echo
echo "Application stopped."
