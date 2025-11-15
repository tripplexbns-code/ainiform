@echo off
echo ================================================
echo AI-niform Server with Storage Bucket Fix
echo ================================================
echo.
echo Setting environment variables...
set FIREBASE_STORAGE_BUCKET=ainiform-45224.appspot.com
set FIREBASE_PROJECT_ID=ainiform-45224
set SECRET_KEY=ainiform-secret-key-2024
echo.
echo Environment variables set successfully!
echo.
echo Starting server...
python web_server.py
pause
