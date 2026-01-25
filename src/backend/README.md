# Backend API Directory

This directory contains the Flask-based backend API for the TRIDENT emergency response system.

## Structure

- `main.py` - Main Flask application entry point
- `api/` - API endpoint handlers
  - `sos_handler.py` - SOS request management
  - `dashboard_handler.py` - Dashboard data serving
  - `analytics_handler.py` - Analytics and reporting
- `services/` - Business logic services
  - `priority_calculator.py` - Emergency priority calculation
  - `database_manager.py` - Database operations
  - `notification_service.py` - Alert and notification system
- `tests/` - Backend testing suite
- `utils/` - Utility scripts for database and team management

## Dependencies

See root `requirements.txt` for all Python dependencies.

## Configuration

Environment variables should be set in `config/` directory:
- `development.env` - Development configuration
- `production.env` - Production configuration

## API Endpoints

- `POST /api/sos` - Submit emergency SOS request
- `GET /api/dashboard` - Dashboard data
- `GET /api/analytics` - Analytics data
- `POST /api/rov/deploy` - ROV deployment command