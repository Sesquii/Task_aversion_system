# Server Migration Checklist

## Current Status
- ✅ SSH access to VPS (Ubuntu 22.04)
- ✅ Local SQLite migration complete
- ✅ Codebase supports PostgreSQL via DATABASE_URL
- ⏳ PostgreSQL installation on VPS
- ⏳ Code deployment to server
- ⏳ Nginx + TLS setup
- ⏳ Systemd service configuration

## Phase 1: Server Preparation (Do This First)

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

### 1.4 Basic Backup Script
Create `/home/your-user/backup_task_aversion.sh` on the server:
```bash
#!/bin/bash
BACKUP_DIR="/home/your-user/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup database
pg_dump -U task_aversion_user task_aversion_system > $BACKUP_DIR/task_aversion_system_$DATE.sql

# Keep only last 7 days of backups
find $BACKUP_DIR -name "task_aversion_system_*.sql" -mtime +7 -delete

echo "Backup completed: task_aversion_system_$DATE.sql"
```

Make it executable:
```bash
chmod +x /home/your-user/backup_task_aversion.sh
```

## Phase 2: Migration Script Conversion (Local Work)

### 2.1 Review Current Migrations
- Review all scripts in `task_aversion_app/SQLite_migration/`
- Note any SQLite-specific syntax that needs conversion

### 2.2 Create PostgreSQL Migration Script
- Create `task_aversion_app/PostgreSQL_migration/` folder
- Convert SQLite migrations to PostgreSQL-compatible SQL
- Test against local PostgreSQL (Docker is fine)

### 2.3 Key Differences to Watch For
- SQLite: `INTEGER PRIMARY KEY` → PostgreSQL: `SERIAL PRIMARY KEY` or `BIGSERIAL`
- SQLite: `TEXT` → PostgreSQL: `TEXT` (same, but check constraints)
- SQLite: `JSON` → PostgreSQL: `JSONB` (better performance)
- SQLite: No schema → PostgreSQL: Use `public` schema
- SQLite: Case-insensitive → PostgreSQL: Case-sensitive (use quotes if needed)

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
