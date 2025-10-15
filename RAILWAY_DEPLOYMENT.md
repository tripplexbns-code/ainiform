# Railway Deployment Guide

## Overview
This guide will help you deploy your AI-niform web server to Railway.

## Prerequisites
1. Railway account (sign up at https://railway.app)
2. Git repository with your code
3. Firebase project with service account key
4. Cloudinary account for image uploads

## Required Environment Variables

Set these environment variables in your Railway project dashboard:

### Firebase Configuration
```
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_PRIVATE_KEY_ID=your-private-key-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=your-service-account@your-project.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=your-client-id
FIREBASE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
FIREBASE_TOKEN_URI=https://oauth2.googleapis.com/token
FIREBASE_AUTH_PROVIDER_X509_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
FIREBASE_CLIENT_X509_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40your-project.iam.gserviceaccount.com
```

### Cloudinary Configuration
```
CLOUDINARY_CLOUD_NAME=your-cloudinary-cloud-name
CLOUDINARY_API_KEY=your-cloudinary-api-key
CLOUDINARY_API_SECRET=your-cloudinary-api-secret
```

### Flask Configuration
```
SECRET_KEY=your-super-secret-key-here
FLASK_DEBUG=False
ENVIRONMENT=production
```

## Deployment Steps

### 1. Connect Repository
1. Go to Railway dashboard
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository

### 2. Configure Environment Variables
1. In your Railway project dashboard
2. Go to "Variables" tab
3. Add all the environment variables listed above
4. Make sure to use the exact variable names

### 3. Deploy
1. Railway will automatically detect your Python app
2. It will install dependencies from `requirements.txt`
3. It will use the `railway.json` configuration
4. Your app will be available at `https://your-project-name.railway.app`

## File Structure
```
├── web_server.py          # Main Flask application
├── requirements.txt       # Python dependencies
├── runtime.txt           # Python version specification
├── railway.json          # Railway deployment configuration
├── Procfile             # Process file (alternative to railway.json)
├── firebase_config.py   # Firebase configuration
├── cloudinary_config.py # Cloudinary configuration
├── ServiceAccountKey.json # Firebase service account (for local development)
└── templates/           # HTML templates
```

## Troubleshooting

### Common Issues
1. **Port binding errors**: Railway automatically sets the PORT environment variable
2. **Firebase connection issues**: Check your service account credentials
3. **Cloudinary upload failures**: Verify your API credentials
4. **Static files not loading**: Ensure all static files are in the correct directories

### Logs
- View logs in Railway dashboard under "Deployments" tab
- Check for any error messages during startup
- Verify environment variables are set correctly

### Health Check
- Your app should respond to GET requests at the root URL
- The login page should load without errors
- Firebase connection should be established on startup

## Security Notes
- Never commit `ServiceAccountKey.json` to your repository
- Use strong, unique secret keys
- Regularly rotate your API keys
- Monitor your Railway usage and costs

## Custom Domain (Optional)
1. In Railway dashboard, go to "Settings"
2. Click "Domains"
3. Add your custom domain
4. Configure DNS records as instructed
5. Enable SSL certificate

## Monitoring
- Railway provides basic monitoring in the dashboard
- Set up alerts for deployment failures
- Monitor resource usage and costs
- Check application logs regularly
