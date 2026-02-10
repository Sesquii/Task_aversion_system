---
name: Server Deployment with SQLite
overview: Deploy application to production server with PostgreSQL database. Production MUST use PostgreSQL. Includes Dockerfile, server setup, nginx, SSL. Choose systemd+venv or Docker (see docs/deployment_systemd_vs_docker.md). SQLite is for local dev only.
todos:
  - id: day1_server_prep
    content: "Day 1: Server preparation - SSH access, user setup, Python 3.11 installation, directory structure"
    status: pending
  - id: day2_dockerfile_sqlite
    content: "Day 2: Update Dockerfile for SQL migration, update docker-compose.yml for SQLite, copy SQLite database to server"
    status: pending
    dependencies:
      - day1_server_prep
  - id: day3_deployment
    content: "Day 3: Deploy code to server, configure environment variables, create systemd service, start application"
    status: pending
    dependencies:
      - day2_dockerfile_sqlite
  - id: day4_nginx_ssl
    content: "Day 4: Install and configure nginx, set up SSL certificates with Let's Encrypt (optional), configure firewall"
    status: pending
    dependencies:
      - day3_deployment
  - id: day5_hardening
    content: "Day 5: Security hardening, set up logging, create SQLite backup scripts, create deployment documentation"
    status: pending
    dependencies:
      - day4_nginx_ssl
---

# Server Deployment Plan (PostgreSQL Production)

**Created:** 2025-01-XX | **Status:** Planning | **Priority:** Medium  
**Timeline:** 4-5 days | **Production Database:** PostgreSQL (required)

## Overview

Deploy the Task Aversion System to a production server. **Production MUST use PostgreSQL.** The app supports both systemd+venv and Docker deployment; see `docs/deployment_systemd_vs_docker.md` for comparison. SQLite is for local development only.

## Current State

- ✅ SQLite migration complete locally
- ✅ Database models and dual-backend pattern implemented
- ✅ Application works with `DATABASE_URL` environment variable
- ❌ Dockerfile is out of date (doesn't account for SQL migration)
- ❌ No production server configuration
- ❌ No deployment automation

## Goals

1. Update Dockerfile to support SQL migration and SQLite
2. Deploy SQLite database to server
3. Configure nginx reverse proxy
4. Set up SSL certificates (Let's Encrypt)
5. Create systemd service for app management
6. Deploy application to server
7. Test production deployment

## Day-by-Day Breakdown

### Day 1: Server Preparation and Environment Setup

**Goal:** Prepare server environment and verify access**Tasks:**

1. **Server Access Verification**

- SSH into server
- Verify Ubuntu 22.04 (or current version)
- Update system packages: `sudo apt update && sudo apt upgrade -y`
- Install basic tools: `git`, `curl`, `wget`

2. **Create Application User**

- Create non-root user for app: `sudo adduser taskaversion`
- Add to sudo group if needed: `sudo usermod -aG sudo taskaversion`
- Set up SSH keys for passwordless access

3. **Create Application Directory Structure**
   ```bash
         sudo mkdir -p /opt/task-aversion-system
         sudo chown taskaversion:taskaversion /opt/task-aversion-system
         cd /opt/task-aversion-system
   ```




4. **Install Python and Dependencies**

- Install Python 3.11: `sudo apt install python3.11 python3.11-venv python3-pip -y`
- Install build dependencies: `sudo apt install build-essential python3-dev -y`

5. **Clone Repository**

- Clone codebase to server
- Verify code is accessible

**Deliverable:** Server is ready with Python 3.11 and application directory---

### Day 2: Dockerfile Update and SQLite Deployment

**Goal:** Update Dockerfile for SQL migration and deploy SQLite database**Tasks:**

1. **Update Dockerfile**

- Remove outdated CSV-only assumptions
- Ensure SQLite support is included
- Set up environment variables for database connection
- Update data directory handling for SQLite
- Ensure `sqlalchemy` and dependencies are installed

2. **Update docker-compose.yml (if using Docker)**

- Configure SQLite database file location
- Set up volumes for data persistence
- Configure environment variables

3. **Create Environment Configuration**

- Create `.env.example` with all required variables
- Document `DATABASE_URL` format for SQLite: `sqlite:///data/task_aversion.db`
- Add production environment variables

4. **Copy SQLite Database to Server**

- Copy existing SQLite database file from local machine
- Place in `/opt/task-aversion-system/data/` directory
- Set proper permissions: `chmod 644 data/task_aversion.db`
- Verify database is accessible

5. **Test Docker Build Locally (optional)**

- Build Docker image: `docker build -t task-aversion-system .`
- Test with SQLite database
- Verify database connection works
- Test app startup

**Files to Create/Modify:**

- `Dockerfile` - Update for SQL migration
- `docker-compose.yml` - Update for SQLite (if using Docker)
- `.env.example` - Environment variable template
- `.dockerignore` - Exclude unnecessary files

**Deliverable:** Updated Dockerfile and SQLite database on server---

### Day 3: Application Deployment to Server

**Goal:** Deploy application to server and configure systemd service**Tasks:**

1. **Deploy Code to Server**

- Push code to server (git pull or rsync)
- Create virtual environment: `python3.11 -m venv venv`
- Install dependencies: `./venv/bin/pip install -r requirements.txt`

2. **Configure Environment Variables**

- Create `.env` file on server with:
        - `DATABASE_URL=sqlite:///data/task_aversion.db`
        - `NICEGUI_HOST=0.0.0.0`
        - `NICEGUI_PORT=8080`
        - Production-specific settings

3. **Verify Database Access**

- Test database connection
- Verify tables exist
- Test basic queries

4. **Create Systemd Service**

- Create `/etc/systemd/system/task-aversion-system.service`
- Configure service to:
        - Run app with virtual environment Python
        - Load environment variables from `.env`
        - Restart on failure
        - Set proper working directory

5. **Start and Test Service**

- Enable service: `sudo systemctl enable task-aversion-system`
- Start service: `sudo systemctl start task-aversion-system`
- Check status: `sudo systemctl status task-aversion-system`
- View logs: `sudo journalctl -u task-aversion-system -f`

**Files to Create:**

- `/etc/systemd/system/task-aversion-system.service` - Systemd service file
- `/opt/task-aversion-system/.env` - Production environment variables

**Deliverable:** Application running on server via systemd---

### Day 4: Nginx Configuration and SSL Setup

**Goal:** Set up reverse proxy and SSL certificates**Tasks:**

1. **Install Nginx**
   ```bash
         sudo apt install nginx -y
         sudo systemctl start nginx
         sudo systemctl enable nginx
   ```




2. **Configure Nginx Reverse Proxy**

- Create `/etc/nginx/sites-available/task-aversion-system`
- Configure proxy to `http://localhost:8080`
- Set up proper headers
- Configure static file serving if needed
- Add timeouts for long-running requests (analytics page)

3. **Set Up Domain (if applicable)**

- Point domain A/AAAA records to server IP
- Verify DNS propagation
- Or use IP address initially

4. **Install Certbot and Get SSL Certificate**
   ```bash
         sudo apt install certbot python3-certbot-nginx -y
         sudo certbot --nginx -d taskaversionsystem.com
   ```




- Follow prompts to configure SSL
- Set up automatic renewal
- Or skip SSL if using IP address

5. **Test Nginx Configuration**

- Test config: `sudo nginx -t`
- Reload nginx: `sudo systemctl reload nginx`
- Verify app accessible via domain/IP
- Test SSL certificate (if configured)

6. **Configure Firewall**
   ```bash
         sudo ufw allow 22/tcp    # SSH
         sudo ufw allow 80/tcp    # HTTP
         sudo ufw allow 443/tcp   # HTTPS
         sudo ufw enable
   ```


**Files to Create:**

- `/etc/nginx/sites-available/task-aversion-system` - Nginx configuration
- Symlink: `/etc/nginx/sites-enabled/task-aversion-system`

**Deliverable:** Application accessible via HTTPS (or HTTP if no domain)---

### Day 5: Production Hardening and Documentation

**Goal:** Secure and document production deployment**Tasks:**

1. **Security Hardening**

- Review file permissions
- Ensure `.env` file is not world-readable: `chmod 600 .env`
- Review database file permissions: `chmod 644 data/task_aversion.db`
- Set up fail2ban for SSH protection (optional)

2. **Set Up Logging**

- Configure application logging to files
- Set up log rotation
- Configure systemd journal retention

3. **Database Backup Setup**

- Create backup script: `backup_database.sh`
- Set up daily cron job for backups
- Test backup and restore process
- SQLite backup is simple: just copy the file

4. **Monitoring Setup**

- Set up basic health check endpoint (if not exists)
- Configure uptime monitoring (optional: UptimeRobot, etc.)
- Set up email alerts for service failures

5. **Create Deployment Documentation**

- Document server setup process
- Document update/deployment procedure
- Create troubleshooting guide
- Document when to migrate to PostgreSQL

**Files to Create:**

- `scripts/backup_database.sh` - SQLite database backup script
- `scripts/restore_database.sh` - SQLite database restore script
- `docs/DEPLOYMENT.md` - Deployment documentation
- `docs/SERVER_SETUP.md` - Server setup guide

**Deliverable:** Production-ready, monitored, and documented system

## Technical Details

### Updated Dockerfile Structure

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY task_aversion_app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY task_aversion_app/ .

# Create data directory (for SQLite database)
RUN mkdir -p data

# Expose port
EXPOSE 8080

# Environment variables (can be overridden)
ENV NICEGUI_HOST=0.0.0.0
ENV NICEGUI_PORT=8080
ENV DATABASE_URL=sqlite:///data/task_aversion.db

# Run database initialization and start app
CMD ["python", "app.py"]
```



### Docker Compose with SQLite

```yaml
# docker-compose.yml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
            - "8080:8080"
    environment:
            - DATABASE_URL=sqlite:///data/task_aversion.db
            - NICEGUI_HOST=0.0.0.0
    volumes:
            - ./data:/app/data  # SQLite database file
    restart: unless-stopped
```



### Systemd Service File

```ini
# /etc/systemd/system/task-aversion-system.service
[Unit]
Description=Task Aversion System Application
After=network.target

[Service]
Type=simple
User=taskaversion
Group=taskaversion
WorkingDirectory=/opt/task-aversion-system
Environment="PATH=/opt/task-aversion-system/venv/bin"
EnvironmentFile=/opt/task-aversion-system/.env
ExecStart=/opt/task-aversion-system/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```



### Nginx Configuration

```nginx
# /etc/nginx/sites-available/task-aversion-system
server {
    listen 80;
    server_name taskaversionsystem.com www.taskaversionsystem.com;

    # Redirect to HTTPS (if SSL configured)
    # return 301 https://$server_name$request_uri;
    
    # Or serve directly on HTTP
    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts for long-running requests (analytics page)
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```



### SQLite Backup Script

```bash
#!/bin/bash
# scripts/backup_database.sh

BACKUP_DIR="/opt/task-aversion-system/backups"
DB_FILE="/opt/task-aversion-system/data/task_aversion.db"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"
cp "$DB_FILE" "$BACKUP_DIR/task_aversion_${DATE}.db"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "task_aversion_*.db" -mtime +7 -delete

echo "Backup completed: task_aversion_${DATE}.db"
```



## SQLite Considerations

### Advantages for This Deployment

- **Simple Setup:** No separate database service to manage
- **Low Resource Usage:** ~1-2MB vs ~50-100MB for PostgreSQL
- **Fast Deployment:** Just copy database file
- **Works for Single User:** Perfect for personal use or very low traffic
- **Easy Backup:** Just copy the file

### Limitations to Be Aware Of

- **Concurrent Writes:** SQLite handles 5-10 concurrent writes max
- **File Locking:** Can get "database is locked" errors with high concurrency
- **No Network Access:** Database must be on same server as app
- **Scaling:** Will need PostgreSQL migration when scaling beyond single user

### When to Migrate to PostgreSQL

Consider migrating to PostgreSQL when:

- You see "database is locked" errors
- You have >5 concurrent users
- You need better performance under load
- You want to scale horizontally later

See separate "PostgreSQL Migration Plan" for migration steps.

## Testing Strategy

1. **Local Testing:**

- Test Docker build locally
- Verify SQLite database works
- Test all application features

2. **Server Testing:**

- Test all application features in production
- Verify database operations work
- Test analytics page loads correctly
- Verify all pages accessible

3. **Performance Testing:**

- Verify analytics page loads in acceptable time
- Check database query performance
- Monitor resource usage

## Success Criteria

- ✅ Application accessible via HTTPS (or HTTP)
- ✅ SQLite database operational
- ✅ All features working correctly
- ✅ Analytics page loads in acceptable time (< 5 seconds)
- ✅ Database backups configured
- ✅ Systemd service manages application
- ✅ Nginx reverse proxy working
- ✅ SSL certificate valid and auto-renewing (if configured)

## Dependencies

- Existing SQLite migration complete
- Server access (SSH)
- Domain name (optional, can use IP initially)
- Performance optimization plan (for analytics page speed)

## Notes

- Can start with IP address access before domain setup
- Can use Docker Compose for easier deployment initially
- SQLite is perfect for single-user or very low traffic scenarios