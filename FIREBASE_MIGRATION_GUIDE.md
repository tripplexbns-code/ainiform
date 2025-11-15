# Firebase Account Migration Guide

This guide will help you switch from your current Firebase account to a new Firebase account with the same structure.

## Prerequisites

- Access to your **new Firebase project** console
- Admin access to your **new Firebase project**
- The new Firebase project should have the same database structure as the current one

---

## Step-by-Step Process

### Step 1: Get Service Account Key from New Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your **new Firebase project**
3. Click on the **gear icon** (⚙️) next to "Project Overview" → **Project settings**
4. Go to the **"Service accounts"** tab
5. Click **"Generate new private key"** button
6. A JSON file will be downloaded (e.g., `your-project-firebase-adminsdk-xxxxx.json`)
7. **Save this file** - you'll need it in the next step

### Step 2: Replace the Service Account Key File

1. **Backup your current ServiceAccountKey.json** (optional but recommended):
   ```bash
   # Create a backup
   copy ServiceAccountKey.json ServiceAccountKey.json.backup
   ```

2. **Replace the file**:
   - Rename the downloaded JSON file from Step 1 to `ServiceAccountKey.json`
   - Replace the existing `ServiceAccountKey.json` in your project root directory
   - **OR** copy the contents from the new JSON file and paste them into your existing `ServiceAccountKey.json`

### Step 3: Update .firebaserc File

1. Open `.firebaserc` file in your project
2. Find the `project_id` in your new `ServiceAccountKey.json` (it's in the `"project_id"` field)
3. Update `.firebaserc` with the new project ID:
   ```json
   {
     "projects": {
       "default": "YOUR-NEW-PROJECT-ID"
     }
   }
   ```
   Replace `YOUR-NEW-PROJECT-ID` with the actual project ID from your new service account key.

### Step 4: Update Environment Variables (If Using Local Scripts)

If you're using local scripts that set Firebase environment variables, update them:

#### A. Update `set_env_and_run.py`:

Open `set_env_and_run.py` and update these lines:
```python
# Line 16: Update storage bucket
os.environ['FIREBASE_STORAGE_BUCKET'] = 'YOUR-NEW-PROJECT-ID.appspot.com'

# Line 21: Update project ID
os.environ['FIREBASE_PROJECT_ID'] = 'YOUR-NEW-PROJECT-ID'
```

#### B. Update `run_with_storage_fix.bat`:

Open `run_with_storage_fix.bat` and update these lines:
```batch
set FIREBASE_STORAGE_BUCKET=YOUR-NEW-PROJECT-ID.appspot.com
set FIREBASE_PROJECT_ID=YOUR-NEW-PROJECT-ID
```

Replace `YOUR-NEW-PROJECT-ID` with your actual new project ID.

### Step 5: Update Railway Environment Variables (If Deployed on Railway)

If your application is deployed on Railway, update the environment variables in Railway dashboard:

1. Go to your Railway project dashboard
2. Navigate to your service → **Variables** tab
3. Update or add these environment variables:
   - `FIREBASE_PROJECT_ID` = Your new project ID
   - `FIREBASE_PRIVATE_KEY_ID` = From new ServiceAccountKey.json
   - `FIREBASE_PRIVATE_KEY` = From new ServiceAccountKey.json (keep the `\n` characters)
   - `FIREBASE_CLIENT_EMAIL` = From new ServiceAccountKey.json
   - `FIREBASE_CLIENT_ID` = From new ServiceAccountKey.json
   - `FIREBASE_AUTH_URI` = `https://accounts.google.com/o/oauth2/auth` (usually same)
   - `FIREBASE_TOKEN_URI` = `https://oauth2.googleapis.com/token` (usually same)
   - `FIREBASE_AUTH_PROVIDER_X509_CERT_URL` = From new ServiceAccountKey.json
   - `FIREBASE_CLIENT_X509_CERT_URL` = From new ServiceAccountKey.json
   - `FIREBASE_STORAGE_BUCKET` = `YOUR-NEW-PROJECT-ID.appspot.com`

### Step 6: Verify Firebase Services in New Project

Ensure your new Firebase project has the same services enabled:

1. **Firestore Database**:
   - Go to Firebase Console → **Firestore Database**
   - Make sure it's enabled and in the same mode (Native mode or Datastore mode) as your old project

2. **Firebase Storage** (if used):
   - Go to Firebase Console → **Storage**
   - Make sure it's enabled
   - Note: Storage requires a **Blaze (paid) plan**

3. **Firebase Authentication** (if used):
   - Go to Firebase Console → **Authentication**
   - Make sure it's enabled

### Step 7: Test the Connection

1. **Test locally**:
   ```bash
   python firebase_config.py
   ```
   This will test the Firebase connection and should show:
   - `[OK] Firebase initialized with service account key file`
   - `[OK] Firestore database connected`
   - `[OK] Storage bucket configured` (if Storage is enabled)

2. **Start your server**:
   ```bash
   python web_server.py
   ```
   Check the console output for Firebase connection messages.

3. **Test database operations**:
   - Try accessing your application
   - Test creating, reading, updating, and deleting data
   - Verify that data appears in your new Firebase console

### Step 8: Migrate Data (If Needed)

If you need to copy data from your old Firebase to the new one:

1. **Option A: Manual Export/Import** (for small datasets):
   - Export data from old Firebase Console → Firestore → Export
   - Import to new Firebase Console → Firestore → Import

2. **Option B: Use a migration script** (for large datasets):
   - Write a script that reads from old Firebase and writes to new Firebase
   - Run it with both service account keys configured temporarily

---

## Quick Reference: Files to Update

| File | What to Update |
|------|----------------|
| `ServiceAccountKey.json` | Replace entire file with new service account key |
| `.firebaserc` | Update `project_id` in the `default` field |
| `set_env_and_run.py` | Update `FIREBASE_STORAGE_BUCKET` and `FIREBASE_PROJECT_ID` |
| `run_with_storage_fix.bat` | Update `FIREBASE_STORAGE_BUCKET` and `FIREBASE_PROJECT_ID` |
| Railway Variables | Update all `FIREBASE_*` environment variables |

---

## Troubleshooting

### Issue: "Firebase not initialized" error
- **Solution**: Check that `ServiceAccountKey.json` is in the project root and has valid JSON format
- Verify the file name is exactly `ServiceAccountKey.json` (case-sensitive)

### Issue: "Storage bucket not configured" warning
- **Solution**: 
  - Update `FIREBASE_STORAGE_BUCKET` environment variable
  - Ensure Storage is enabled in Firebase Console
  - Check if you're on Blaze plan (required for Storage)

### Issue: "Permission denied" errors
- **Solution**: 
  - Verify the service account has proper permissions in Firebase Console
  - Check Firestore rules allow read/write access
  - Ensure Storage rules allow uploads

### Issue: Data not appearing
- **Solution**: 
  - Verify you're connected to the correct project (check project ID)
  - Check Firestore database in Firebase Console
  - Verify collection names match between old and new projects

---

## Summary Checklist

- [ ] Downloaded new service account key from new Firebase project
- [ ] Replaced `ServiceAccountKey.json` with new credentials
- [ ] Updated `.firebaserc` with new project ID
- [ ] Updated `set_env_and_run.py` (if used)
- [ ] Updated `run_with_storage_fix.bat` (if used)
- [ ] Updated Railway environment variables (if deployed)
- [ ] Verified Firestore is enabled in new project
- [ ] Verified Storage is enabled in new project (if used)
- [ ] Tested Firebase connection locally
- [ ] Tested application functionality
- [ ] Migrated data (if needed)

---

## Need Help?

If you encounter any issues during the migration:
1. Check the console output for specific error messages
2. Verify all file paths and names are correct
3. Ensure your new Firebase project has the same structure as the old one
4. Review Firebase Console for any service-specific errors

