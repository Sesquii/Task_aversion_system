# Data Storage & Troubleshooting Guide

## How Your Data is Stored

### Username Storage (Browser localStorage)
- Your username is stored in your browser's **localStorage**
- This is a browser feature that persists data even after you close the browser or restart your computer
- The username is stored locally on your device, not on the server
- **Important**: If you clear your browser data or use a different browser, you'll need to re-enter your username

### Task Data Storage (Server)
- All your task data is stored on the server in CSV files
- Your data is organized in: `data/users/{your_username}/`
- Files include:
  - `tasks.csv` - Your task definitions
  - `task_instances.csv` - All your task instances and completion data
  - `user_preferences.csv` - Your app settings and preferences
  - `survey_responses.csv` - Your survey responses (if any)

### Data Persistence
- **Server data**: Persists permanently on the server, even if you close your browser
- **Browser localStorage**: Persists across browser sessions and computer restarts
- **Data is safe**: Your tasks and data remain on the server even if you lose access to your browser localStorage

---

## How to Access Your Data

### Normal Access
1. Open the app in your browser
2. Your username is automatically loaded from browser localStorage
3. Your data loads from the server automatically
4. Everything works seamlessly!

### If You Can't Access Your Data

**Check these things first:**
1. **Are you using the same browser?** - localStorage is browser-specific
2. **Did you clear browser data?** - This clears localStorage
3. **Are you in incognito/private mode?** - localStorage doesn't persist in private browsing
4. **Did you enter the correct username?** - Usernames are case-sensitive

**Solutions:**
- Try re-entering your username (if it's still available)
- Use the "Export My Data" feature to download your data as backup
- Contact support with your username for data recovery assistance

---

## Recovering Lost Access

### Scenario 1: Lost Browser localStorage (Username)
**Symptoms**: App doesn't remember your username, asks you to log in again

**Solution**:
1. Re-enter your username (if no one else has taken it)
2. Your data will still be on the server and will load automatically
3. The app will remember your username again in the new browser localStorage

**Prevention**: Use the "Export My Data" feature regularly to keep backups

### Scenario 2: Username Taken by Someone Else
**Symptoms**: You enter your username but see someone else's data

**Solution**:
1. Try a slightly different username (add numbers or underscore)
2. Contact support to recover your original username if needed
3. If you have exported data, you can import it to the new username

### Scenario 3: Can't Access on New Computer
**Symptoms**: You're on a different computer and can't see your data

**Solution**:
1. **Before switching computers**: Export your data using "Export My Data" in Settings
2. **On new computer**: 
   - Log in with the same username
   - Your data will load from the server automatically
   - If username doesn't work, use exported CSV files as backup

---

## Transferring Data to a New Computer

### Method 1: Automatic (Recommended)
1. On your **original computer**: Make sure you're logged in and can see your data
2. On your **new computer**: 
   - Open the app in your browser
   - Enter the same username you used before
   - Your data will automatically load from the server
   - The app will remember your username in the new browser's localStorage

**Note**: This works because your data is stored on the server, not on your computer!

### Method 2: Manual Export/Import (Backup Method)
1. **Export your data**:
   - Go to Settings
   - Click "Export My Data"
   - Download the ZIP file containing all your CSV files
   - Save it somewhere safe (cloud storage, USB drive, etc.)

2. **On new computer**:
   - Log in with your username
   - If data doesn't load automatically, contact support for manual import
   - Or continue using the app on your original computer

### Method 3: Continue on Original Computer
- If you prefer, you can continue using the app only on your original computer
- Your data will always be there when you log in with your username
- No need to transfer anything!

---

## Understanding Browser localStorage

### What is localStorage?
- A browser feature that stores data locally on your device
- Data persists even after closing the browser or restarting your computer
- Each website has its own localStorage space
- Data is stored in your browser's data directory

### Where is it stored?
- **Windows**: `%LOCALAPPDATA%\Google\Chrome\User Data\Default\Local Storage` (for Chrome)
- **Mac**: `~/Library/Application Support/Google/Chrome/Default/Local Storage` (for Chrome)
- **Linux**: `~/.config/google-chrome/Default/Local Storage` (for Chrome)
- Similar paths for other browsers (Firefox, Edge, Safari)

### When is localStorage cleared?
- You manually clear browser data
- You use incognito/private browsing mode
- You uninstall and reinstall the browser
- Browser settings are reset

### How to check your localStorage
1. Open browser Developer Tools (F12 or Right-click → Inspect)
2. Go to "Application" tab (Chrome) or "Storage" tab (Firefox)
3. Expand "Local Storage" in the left sidebar
4. Click on your app's domain
5. Look for `tas_username` or similar key

---

## Troubleshooting Common Issues

### "I can't see my tasks"
**Possible causes:**
- Wrong username entered
- Browser localStorage was cleared
- Using a different browser
- Username was taken by someone else

**Solutions:**
1. Check if you're using the correct username
2. Try re-entering your username
3. Check if you're using the same browser as before
4. Export your data as backup
5. Contact support with your username

### "My username doesn't work"
**Possible causes:**
- Username was taken by another user
- Typo in username
- Browser localStorage issue

**Solutions:**
1. Try a slightly different username
2. Check for typos (usernames are case-sensitive)
3. Clear browser cache and try again
4. Contact support if you believe your username was taken

### "Data disappeared"
**Possible causes:**
- Browser data was cleared
- Using a different browser
- Server issue (rare)

**Solutions:**
1. Check if you're using the same browser
2. Check if browser data was cleared
3. Try re-entering your username
4. Your data should still be on the server
5. Contact support if data is truly missing

### "Can't access on new computer"
**Possible causes:**
- Different browser
- Username not entered yet
- Network/server issue

**Solutions:**
1. Enter your username on the new computer
2. Make sure you're using the same username
3. Check your internet connection
4. If it still doesn't work, use exported CSV files as backup

---

## Best Practices

### Regular Backups
- Use "Export My Data" feature regularly (weekly or monthly)
- Save exported ZIP files to cloud storage or external drive
- Keep multiple backup copies

### Username Management
- Choose a memorable username
- Write down your username somewhere safe
- Don't share your username with others (they could access your data)

### Browser Management
- Use the same browser consistently
- Avoid clearing browser data unnecessarily
- Don't use incognito mode for regular use

### Multi-Device Usage
- You can use the same username on multiple devices
- Data syncs automatically from the server
- Each device remembers your username in its own localStorage

---

## Getting Help

If you're still having issues after trying these solutions:

1. **Check this guide again** - Make sure you've tried all relevant solutions
2. **Export your data** - Always export before troubleshooting
3. **Contact support** - Provide your username and describe the issue
4. **Check server status** - Make sure the app is accessible

---

## Quick Reference

| Issue | Quick Fix |
|-------|-----------|
| Can't see my data | Re-enter username, check browser |
| Username doesn't work | Try different username, check for typos |
| Data disappeared | Check browser, re-enter username |
| New computer | Enter same username, data loads automatically |
| Lost access | Export data first, then contact support |
| Need backup | Use "Export My Data" in Settings |

---

*Last updated: 2025-01-22*

