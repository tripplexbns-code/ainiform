#!/usr/bin/env bash
# Heroku deployment script

echo "🚀 Deploying AI Uniform System to Heroku..."

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo "❌ Heroku CLI not found. Please install it first:"
    echo "   https://devcenter.heroku.com/articles/heroku-cli"
    exit 1
fi

# Login to Heroku
echo "🔐 Logging into Heroku..."
heroku login

# Create Heroku app
echo "📱 Creating Heroku app..."
heroku create ai-uniform-system

# Set environment variables
echo "⚙️ Setting environment variables..."
heroku config:set FIREBASE_STORAGE_BUCKET=ainiform-system-c42de.appspot.com
heroku config:set FIREBASE_PROJECT_ID=ainiform-system-c42de
heroku config:set SECRET_KEY=ainiform-secret-key-2024
heroku config:set ENVIRONMENT=production

# Deploy
echo "🚀 Deploying to Heroku..."
git push heroku main

echo "✅ Deployment complete!"
echo "🌐 Your app is live at: https://ai-uniform-system.herokuapp.com"
