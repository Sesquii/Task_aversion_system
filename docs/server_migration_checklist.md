# Server Migration Checklist

## Current Status

- ✅ SSH access to VPS (Ubuntu 22.04)
- ✅ Local SQLite migration complete
- ✅ Codebase supports PostgreSQL via DATABASE_URL
- ✅ **Phase 1 Complete**: PostgreSQL installation on VPS
- ✅ **Phase 1 Complete**: Database setup (task_aversion_system)
- ✅ **Phase 1 Complete**: Backup script configured
- ✅ **Phase 2 Complete**: PostgreSQL migration scripts created
- ⏳ **Phase 2B**: User Authentication & Authorization (CRITICAL before publishing)
- ⏳ Code deployment to server
- ⏳ Nginx + TLS setup
- ⏳ Systemd service configuration

## Phase 1: Server Preparation ✅ COMPLETE

**Completed:**

- PostgreSQL installed and running on VPS
- Database `task_aversion_system` created
- User `task_aversion_user` created with secure password
- Backup script created and tested
- `.pgpass` configured for automated backups
- Cron job configured for daily backups

### 1.1 PostgreSQL Installation

```bash
# SSH into your VPS
ssh your-user@your-server-ip

# Update package list
sudo apt update

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Check PostgreSQL version
psql --version

# Start and enable PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**Note: Kernel Upgrade Notification**

- After `apt update && apt upgrade`, you may see a kernel upgrade notification
- Current kernel: 5.15.0-143-generic → New kernel: 5.15.0-164-generic
- **When to reboot:**
  - ✅ **Good time**: After completing Phase 1 (PostgreSQL setup) and before Phase 4 (deployment)
  - ✅ **Also fine**: After completing all server setup (Phase 1-3), before deploying code
  - ⚠️ **Wait if**: You're in the middle of database configuration or have unsaved work
- **To reboot later**: Click `<Ok>` to dismiss, then reboot when convenient:
  ```bash
  sudo reboot
  ```
- **To reboot now**: Click `<Ok>`, then:
  ```bash
  sudo reboot
  ```
  (You'll need to SSH back in after ~1-2 minutes)

### 1.2 Database Setup

```bash
# Switch to postgres user
sudo -u postgres psql

# IMPORTANT: Run each command separately, one at a time
# Each command must end with a semicolon (;)
# Press Enter after each command

# Step 1: Create database
CREATE DATABASE task_aversion_system;

# Step 2: Create user (replace password with your actual password)
CREATE USER task_aversion_user WITH PASSWORD 'your-secure-password-here';

# Step 3: Grant privileges on database
GRANT ALL PRIVILEGES ON DATABASE task_aversion_system TO task_aversion_user;

# Step 4: Connect to the new database
\c task_aversion_system

# Step 5: Grant schema privileges (for PostgreSQL 15+)
GRANT ALL ON SCHEMA public TO task_aversion_user;

# Step 6: Exit psql
\q
```

**Common Mistakes to Avoid:**

- ❌ **DON'T** run multiple commands on one line: `CREATE USER ...; GRANT ...` (will cause syntax error)
- ✅ **DO** run each command separately, pressing Enter after each one
- ⚠️ **Note**: If you use uppercase names like `TAS`, PostgreSQL will convert them to lowercase (`tas`) unless you use quotes: `"TAS"`
- ✅ **Recommended**: Use lowercase with underscores: `task_aversion`, `task_aversion_user`

**If You Forget a Semicolon:**

- If you see `postgres-#` or `database_name-#` (with a dash), you're in multi-line mode
- **To cancel and start fresh**: Press `Ctrl+C` or type `\c` and press Enter
- This will cancel the current command and return you to the normal prompt (`postgres=#`)
- Then retype your command with the semicolon

**What to customize:**

- ✅ **REQUIRED**: Replace `'your-secure-password-here'` with a strong password
  - Use a password manager to generate a secure password
  - Save this password - you'll need it for DATABASE_URL in Phase 3.1
  - Example: `CREATE USER task_aversion_user WITH PASSWORD 'MyStr0ng!P@ssw0rd123';`
- ⚠️ **OPTIONAL**: Database name `task_aversion_system` - can stay as-is or customize
  - Example: `CREATE DATABASE my_task_system;`
- ⚠️ **OPTIONAL**: Username `task_aversion_user` - can stay as-is or customize
  - Example: `CREATE USER my_app_user WITH PASSWORD '...';`

**Important:** If you customize the database name or username, remember to update:

- The DATABASE_URL in Phase 3.1 (environment variables)
- The backup script in Phase 1.4
- All references in Phase 4.2 (migrations)

### 1.3 Test Connection (From Local Machine)

**First, find your server's IP address:**

On the server (via SSH), run one of these commands:

```bash
# Option 1: Show all IP addresses
ip addr show

# Option 2: Show just the main IP (usually eth0 or ens3)
ip addr show eth0
# or
ip addr show ens3

# Option 3: Quick one-liner to get the main IP
hostname -I | awk '{print $1}'

# Option 4: Using ifconfig (if installed)
ifconfig | grep "inet " | grep -v 127.0.0.1
```

**What to look for:**

- The IP address will look like: `192.168.1.100` or `203.0.113.45`
- Ignore `127.0.0.1` (that's localhost)
- The main IP is usually on `eth0`, `ens3`, or `enp0s3` interface

**Alternative: Check your VPS provider dashboard**

- Most VPS providers (DigitalOcean, Linode, AWS, etc.) show the IP in their control panel
- Look for "IP Address", "Public IP", or "IPv4 Address"

**Then test the connection:**

```bash
# Install PostgreSQL client tools locally (if not already installed)
# Windows: Download from https://www.postgresql.org/download/windows/
# Or use WSL: sudo apt install postgresql-client

# Test connection from your local machine (replace with your actual IP)
psql -h your-server-ip -U task_aversion_user -d task_aversion_system

# If connection works, you're ready for Phase 2
```

**Windows PowerShell: If `psql` command not found after installing PostgreSQL:**

PostgreSQL installs to a specific directory that may not be in your PATH. Try these options:

**Option 1: Use full path (quick test)**

```powershell
# Typical PostgreSQL installation path
& "C:\Program Files\PostgreSQL\15\bin\psql.exe" -h your-server-ip -U task_aversion_user -d task_aversion_system
# Or try version 14, 16, etc. if 15 doesn't work
```

**Option 2: Add PostgreSQL to PATH (permanent fix)**

1. Find PostgreSQL installation:
  - Usually: `C:\Program Files\PostgreSQL\15\bin` (or 14, 16, etc.)
  - Or search for `psql.exe` in File Explorer
2. Add to PATH:
  - Press `Win + R`, type `sysdm.cpl`, press Enter
  - Click "Environment Variables"
  - Under "User variables", select "Path" → "Edit"
  - Click "New" → Add: `C:\Program Files\PostgreSQL\15\bin` (adjust version number)
  - Click OK on all dialogs
  - **Restart PowerShell** (close and reopen)
3. Test:
  ```powershell
   psql --version
  ```

**Option 3: Use WSL (if you have it)**

```bash
# In WSL terminal
sudo apt install postgresql-client
psql -h your-server-ip -U task_aversion_user -d task_aversion_system
```

### 1.4 Basic Backup Script

Create `/home/your-user/backup_task_aversion.sh` on the server:

```bash
#!/bin/bash
BACKUP_DIR="/home/your-user/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup database
# Use -h localhost to force TCP/IP connection (password auth) instead of peer auth
pg_dump -h localhost -U task_aversion_user task_aversion_system > $BACKUP_DIR/task_aversion_system_$DATE.sql

# Keep only last 7 days of backups
find $BACKUP_DIR -name "task_aversion_system_*.sql" -mtime +7 -delete

echo "Backup completed: task_aversion_system_$DATE.sql"
```

Make it executable:

```bash
chmod +x /home/your-user/backup_task_aversion.sh
```

**Optional: Set up passwordless authentication for cron jobs**

To avoid password prompts when running backups via cron, create a `.pgpass` file:

```bash
# Create .pgpass file in your home directory
nano ~/.pgpass
```

Add this line (replace with your actual password):

```
localhost:5432:task_aversion_system:task_aversion_user:your-password-here
```

Format: `hostname:port:database:username:password`

Set secure permissions (required for .pgpass to work):

```bash
chmod 600 ~/.pgpass
```

**Now the backup script will work without password prompts!**

**Optional: Set up automatic backups (cron job)**

To run backups automatically (e.g., daily at 2 AM):

```bash
# Edit crontab (will open in default editor, usually nano)
crontab -e

# Add this line (runs daily at 2 AM)
0 2 * * * /home/your-user/backup_task_aversion.sh

# Save and exit (Ctrl+O, Enter, Ctrl+X if using nano)
```

**Cron editor notes:**

- `crontab -e` opens your default editor (usually `nano` or `vi`)
- If it asks which editor, choose `nano` (easier) by typing `nano` and pressing Enter
- To change default editor: `export EDITOR=nano` (add to `~/.bashrc` to make permanent)

## Phase 2: Migration Script Conversion (Local Work) ✅ COMPLETE

### 2.1 Review Current Migrations ✅

- ✅ Reviewed all scripts in `task_aversion_app/SQLite_migration/`
- ✅ Noted SQLite-specific syntax that needs conversion
- ✅ Identified key differences: JSON → JSONB, INTEGER → SERIAL, etc.

### 2.2 Create PostgreSQL Migration Script ✅

- ✅ Created `task_aversion_app/PostgreSQL_migration/` folder
- ✅ Converted all SQLite migrations to PostgreSQL-compatible SQL
- ✅ Created 10 migration scripts (001-010) matching SQLite migrations
- ✅ Added `check_migration_status.py` for PostgreSQL
- ✅ SQLite migration scripts preserved as backup in `SQLite_migration/`
- ✅ Created migrations 009 (users table) and 010 (user_id foreign keys) for OAuth

**Created Migration Scripts:**

- `001_initial_schema.py` - Creates initial database schema
- `002_add_routine_scheduling_fields.py` - Adds routine scheduling fields
- `003_create_task_instances_table.py` - Creates task_instances table
- `004_create_emotions_table.py` - Creates emotions table
- `005_add_indexes_and_foreign_keys.py` - Adds indexes and foreign keys
- `006_add_notes_column.py` - Adds notes column to tasks
- `007_create_user_preferences_table.py` - Creates user_preferences table
- `008_create_survey_responses_table.py` - Creates survey_responses table
- `009_create_users_table.py` - Creates users table for OAuth authentication
- `010_add_user_id_foreign_keys.py` - Adds user_id foreign keys to existing tables

### 2.3 Key Differences Implemented ✅

- ✅ SQLite: `INTEGER PRIMARY KEY` → PostgreSQL: `SERIAL PRIMARY KEY` or `BIGSERIAL`
- ✅ SQLite: `TEXT` for JSON → PostgreSQL: `JSONB` (better performance)
- ✅ SQLite: `JSON` → PostgreSQL: `JSONB` with GIN indexes (Migration 005)
- ✅ Added proper foreign key constraints (PostgreSQL enforces these)
- ✅ Added GIN indexes on JSONB columns for efficient JSON queries
- ✅ Used PostgreSQL-specific syntax (VARCHAR with length, JSONB defaults)

### 2.4 Testing (Next Steps)

**Local Testing with Docker:**

```bash
# Start PostgreSQL container
docker run --name test-postgres \
  -e POSTGRES_PASSWORD=testpassword \
  -e POSTGRES_DB=task_aversion_test \
  -p 5432:5432 \
  -d postgres:15

# Set DATABASE_URL
export DATABASE_URL="postgresql://postgres:testpassword@localhost:5432/task_aversion_test"

# Check migration status
python PostgreSQL_migration/check_migration_status.py

# Run migrations in order
python PostgreSQL_migration/001_initial_schema.py
python PostgreSQL_migration/002_add_routine_scheduling_fields.py
python PostgreSQL_migration/003_create_task_instances_table.py
python PostgreSQL_migration/004_create_emotions_table.py
python PostgreSQL_migration/005_add_indexes_and_foreign_keys.py
python PostgreSQL_migration/006_add_notes_column.py
python PostgreSQL_migration/007_create_user_preferences_table.py
python PostgreSQL_migration/008_create_survey_responses_table.py
python PostgreSQL_migration/009_create_users_table.py
python PostgreSQL_migration/010_add_user_id_foreign_keys.py

# Clean up
docker stop test-postgres
docker rm test-postgres
```

**Notes:**

- All migrations are idempotent (safe to run multiple times)
- SQLite migration scripts kept in `SQLite_migration/` as backup
- PostgreSQL migrations are separate scripts for clarity

## Phase 2B: User Authentication & Authorization ⚠️ CRITICAL

**Status**: ⏳ **PENDING** - Must complete before publishing to production

**Why This is Critical:**

- Current system uses anonymous username-based identification (localStorage)
- **No security**: Anyone can access any user's data if they know/guess the username
- **No verification**: No way to verify who owns what data
- **Legal risk**: Publishing without authentication violates privacy/data protection requirements
- **User trust**: Users need secure access to their personal task/mental health data

### 2B.1 Choose Authentication Strategy

**Option A: OAuth (Recommended for better UX)**

- Pros: No password management, better security, trusted providers (Google, GitHub, Microsoft)
- Cons: More complex setup, requires OAuth app registration
- Providers: Google, GitHub, Microsoft Azure AD
- Libraries: `authlib` or `python-social-auth`

**Option B: Email/Password (Simpler for MVP)**

- Pros: Full control, simpler implementation, no external dependencies
- Cons: Password management, password reset flow, email verification needed
- Libraries: `bcrypt` for password hashing, `itsdangerous` for tokens

**Option C: Hybrid (Best of both worlds)**

- OAuth for primary login (Google/GitHub)
- Email/password as fallback option
- Recommended for production

**Recommendation**: Start with **Option A (OAuth)** for MVP, add email/password later if needed.

### 2B.2 Database Schema Updates

**New Migration: 007_create_users_table.py**

Create `users` table:

```sql
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255),  -- NULL if OAuth only
    oauth_provider VARCHAR(50),  -- 'google', 'github', 'microsoft', NULL
    oauth_id VARCHAR(255),       -- OAuth provider's user ID
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_oauth ON users(oauth_provider, oauth_id);
```

**Update existing tables to add user_id foreign key:**

- `tasks` table: Add `user_id INTEGER REFERENCES users(user_id)`
- `task_instances` table: Add `user_id INTEGER REFERENCES users(user_id)`
- `emotions` table: Add `user_id INTEGER REFERENCES users(user_id)`
- All other user-specific tables

### 2B.3 Implement Authentication System

**New File: `backend/auth.py**`

- User registration/login
- OAuth flow handling
- Session management with NiceGUI
- Password hashing (if using email/password)
- JWT tokens or session cookies

**New File: `backend/user_manager.py**`

- User CRUD operations
- Link existing anonymous data to authenticated users
- User profile management

### 2B.4 Update App Structure

**Modify: `app.py**`

- Add authentication middleware
- Protect routes (require login)
- Add login/register pages
- Session management with NiceGUI's `ui.page()` session support

**Modify: All backend managers**

- `TaskManager`, `InstanceManager`, `EmotionManager`, etc.
- Add user_id filtering to all queries
- Ensure data isolation (users can only see their own data)

### 2B.5 Update UI for Authentication

**New Files:**

- `ui/login.py` - Login page
- `ui/register.py` - Registration page  
- `ui/profile.py` - User profile/settings

**Modify: All existing pages**

- Add user context checking
- Redirect to login if not authenticated
- Show current user info in navigation

### 2B.6 Data Migration Strategy

**Important**: Existing users with anonymous usernames need migration path

1. **Option 1: Invite existing users to create accounts**
  - Show migration prompt on first login after auth is added
  - Link existing data to new account via username matching
  - Require email verification to link data
2. **Option 2: Allow account creation with existing username**
  - During registration, check if username exists in old system
  - Prompt: "This username has existing data. Create account to secure it?"
  - Link data automatically after email verification

### 2B.7 Security Considerations

- **Password requirements**: Minimum 8 chars, complexity rules
- **Rate limiting**: Prevent brute force attacks on login
- **Session security**: Secure cookies, HTTP-only, SameSite
- **CSRF protection**: Token-based CSRF protection
- **SQL injection**: Already handled by SQLAlchemy ORM
- **XSS protection**: NiceGUI handles this, but verify input sanitization

### 2B.8 Implementation Steps

1. ✅ Choose authentication strategy (OAuth vs Email/Password)
2. ⏳ Create database migration 007 (users table)
3. ⏳ Implement `backend/auth.py` with chosen strategy
4. ⏳ Add authentication middleware to `app.py`
5. ⏳ Create login/register UI pages
6. ⏳ Update all backend managers to filter by user_id
7. ⏳ Test authentication flow end-to-end
8. ⏳ Implement data migration for existing users
9. ⏳ Security audit and penetration testing
10. ⏳ Update documentation with authentication requirements

### 2B.9 Testing Checklist

- User can register with OAuth provider
- User can login/logout
- Sessions persist across page refreshes
- Users can only see their own data
- Unauthenticated users are redirected to login
- Existing anonymous data migration works
- Password reset flow works (if using email/password)
- Rate limiting prevents brute force attacks
- Sessions expire after inactivity
- CSRF protection works correctly

### 2B.10 OAuth Setup Instructions (If chosen)

**Google OAuth:**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project or select existing
3. Enable Google+ API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URIs: `https://yourdomain.com/auth/callback`
6. Get Client ID and Client Secret
7. Add to environment variables: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`

**GitHub OAuth:**

1. Go to GitHub Settings > Developer settings > OAuth Apps
2. Create new OAuth App
3. Set Authorization callback URL: `https://yourdomain.com/auth/callback`
4. Get Client ID and Client Secret
5. Add to environment variables: `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`

## Phase 3: Deployment Configuration (Documentation)

### 3.1 Environment Variables

Create `.env.production` template:

```bash
DATABASE_URL=postgresql://task_aversion_user:password@localhost:5432/task_aversion_system
NICEGUI_HOST=0.0.0.0
NICEGUI_PORT=8080
# Add other environment variables as needed
```

### 3.2 Systemd Service File

Create `/etc/systemd/system/task-aversion-app.service`:

```ini
[Unit]
Description=Task Aversion System
After=network.target postgresql.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/home/your-user/task_aversion_app
Environment="PATH=/home/your-user/.local/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/home/your-user/task_aversion_app/.env.production
ExecStart=/usr/bin/python3 /home/your-user/task_aversion_app/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3.3 Nginx Configuration

Create `/etc/nginx/sites-available/task-aversion-system`:

```nginx
server {
    listen 80;
    server_name TaskAversionSystem.com www.TaskAversionSystem.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/task-aversion-system /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl reload nginx
```

### 3.4 TLS/SSL Setup (Let's Encrypt)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain certificate
sudo certbot --nginx -d TaskAversionSystem.com -d www.TaskAversionSystem.com

# Auto-renewal is set up automatically
```

## Phase 4: Code Deployment (When Ready)

### 4.1 Initial Deployment

```bash
# On your local machine
# Push code to git repository (if using version control)

# On server
cd /home/your-user
git clone your-repo-url task_aversion_app
# Or use rsync/scp to copy files

# Install dependencies
cd task_aversion_app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4.2 Run Migrations

```bash
# Set DATABASE_URL
export DATABASE_URL="postgresql://task_aversion_user:password@localhost:5432/task_aversion_system"

# Run PostgreSQL migrations
python PostgreSQL_migration/001_initial_schema.py
# ... run other migrations in order
```

### 4.3 Start Service

```bash
# Enable and start systemd service
sudo systemctl enable task-aversion-app
sudo systemctl start task-aversion-app

# Check status
sudo systemctl status task-aversion-app

# View logs
sudo journalctl -u task-aversion-app -f
```

## Phase 5: Post-Deployment

### 5.1 Smoke Tests

- Access via domain name
- Test login/authentication
- Create a test task
- Verify data persistence

### 5.2 Monitoring

- Set up log rotation
- Monitor disk space
- Set up automated backups (cron job)
- Monitor service health

## Notes

- **Don't rush deployment**: Complete Phases 1-3 first, then deploy when ready
- **Test locally first**: Use Docker PostgreSQL to test migrations before server
- **Backup before changes**: Always backup database before migrations
- **Keep local dev separate**: Don't break your local development environment
- **Document issues**: Keep notes on any problems encountered

## When to Deploy

**Good time to deploy:**

- ✅ Phases 1-3 complete
- ✅ Migrations tested locally
- ✅ You have a stable feature set you want to share
- ✅ You have time to monitor and fix issues

**Wait to deploy if:**

- ❌ Actively developing major features
- ❌ System is unstable
- ❌ Migrations not tested
- ❌ No time to monitor deployment

