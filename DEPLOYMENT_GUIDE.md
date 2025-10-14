# AI Uniform System - Deployment Guide

## Current Issue
The application is a Flask web application that requires Python to run, but Firebase Hosting only serves static files. This is why you're seeing unrendered Jinja2 template syntax (`{{ ... }}`) instead of processed content.

## Solutions

### Option 1: Deploy to Python-Compatible Hosting (Recommended)

#### Railway (Free tier available)
1. Connect your GitHub repository to Railway
2. Railway will automatically detect it's a Python/Flask app
3. Add environment variables:
   - `FIREBASE_STORAGE_BUCKET=ainiform-system-c42de.appspot.com`
   - `FIREBASE_PROJECT_ID=ainiform-system-c42de`
   - `SECRET_KEY=ainiform-secret-key-2024`
4. Deploy automatically

#### Heroku
1. Create a `Procfile` (already exists)
2. Deploy using Git or Heroku CLI
3. Add environment variables in Heroku dashboard

#### Google Cloud Run
1. Create a Dockerfile
2. Deploy using `gcloud run deploy`

### Option 2: Local Development
For local development, use the provided batch files:
- `start_web_app.bat` - Starts the application locally
- `run_with_storage_fix.bat` - Runs with proper environment variables

### Option 3: Firebase Functions (Advanced)
Convert the Flask app to Firebase Functions (requires significant refactoring)

## Fixed Issues
1. ✅ Added missing JavaScript functions (`showAlert`, `refreshDataOnly`, `refreshViolationCounts`)
2. ✅ Removed conflicting static HTML file from public directory
3. ✅ Updated start_web_app.py to use correct Flask app
4. ✅ Fixed template rendering issues

## Next Steps
1. Choose a Python-compatible hosting service
2. Deploy using the hosting service's instructions
3. Test all functionality after deployment

## Demo Credentials
- Username: `guidance1`
- Password: `guidance123`
