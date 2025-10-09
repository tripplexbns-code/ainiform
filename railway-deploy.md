# 🚀 Railway Deployment Guide for AI-niform System

## Quick Deploy (5 minutes!)

### Step 1: Push to GitHub
```bash
# Initialize git (if not done)
git init
git add .
git commit -m "Ready for Railway deployment"

# Create GitHub repo at https://github.com/new
# Then push:
git remote add origin https://github.com/YOUR_USERNAME/ainiform-web.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy on Railway
1. Go to https://railway.app
2. Sign up with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your repository
5. Click "Deploy Now"

### Step 3: Add Environment Variables
In Railway dashboard → Variables tab:
```
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=False
FIREBASE_PROJECT_ID=ainiform-system-c42de
FIREBASE_STORAGE_BUCKET=ainiform-system-c42de.appspot.com
SECRET_KEY=your-secret-key-here
```

### Step 4: Access Your App!
Railway will give you a URL like:
`https://ainiform-web-production.up.railway.app`

## 🎉 Done! Your app is now live worldwide!

### Login Credentials:
- Username: guidance1 | Password: guidance123
- Username: guidance2 | Password: guidance123
- Username: admin1 | Password: guidance123

