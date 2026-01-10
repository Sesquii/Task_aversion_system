# Phase 2B: OAuth Authentication & Secure Import Implementation Plan

## Overview

Implement Google OAuth authentication, secure data import (logged-in users only), and test everything locally with Docker PostgreSQL before server deployment.

## Why Phase 2B Before Phase 3?

**Phase 2B (Authentication) is CRITICAL and should be done BEFORE Phase 3 (Deployment Config) because:**
- Cannot safely deploy without authentication
- Deployment config needs to know auth requirements
- Local testing is easier before deployment complexity
- Authentication affects all deployment settings (environment variables, secrets, etc.)

**Phase 3 (Deployment Config) can be done in parallel or after Phase 2B** - it's mostly documentation and templates, but should reference authentication requirements.

## Implementation Strategy

### Part 1: OAuth Authentication (Google)
**Timeline: ~2-3 days**

#### 1.1 Setup Google OAuth App
- [ ] Create Google Cloud Project
- [ ] Enable Google+ API
- [ ] Create OAuth 2.0 credentials
- [ ] Set authorized redirect URIs:
  - Local: `http://localhost:8080/auth/callback`
  - Production: `https://yourdomain.com/auth/callback`
- [ ] Get Client ID and Client Secret
- [ ] Add to `.env.example` and `.env.local`

#### 1.2 Install Dependencies
```bash
pip install authlib python-jose[cryptography]  # OAuth library
```

Update `requirements.txt`:
- Add `authlib>=1.2.0`
- Add `python-jose[cryptography]>=3.3.0` for JWT tokens (optional, can use session cookies instead)

#### 1.3 Database Schema Update

**Migration 009: Create Users Table**

Create `PostgreSQL_migration/009_create_users_table.py`:
```sql
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE,
    google_id VARCHAR(255) UNIQUE,  -- Google OAuth ID
    oauth_provider VARCHAR(50) DEFAULT 'google',
    email_verified BOOLEAN DEFAULT TRUE,  -- Google emails are verified
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_google_id ON users(google_id);
```

**Migration 010: Add user_id Foreign Keys**

Update existing tables to add `user_id` foreign key:
- `tasks` table: Add `user_id INTEGER REFERENCES users(user_id)`
- `task_instances` table: Add `user_id INTEGER REFERENCES users(user_id)`
- `emotions` table: Add `user_id INTEGER REFERENCES users(user_id)` (if user-specific)
- `user_preferences` table: Change `user_id` from VARCHAR to INTEGER, add foreign key
- `survey_responses` table: Change `user_id` from VARCHAR to INTEGER, add foreign key
- `popup_triggers` table: Change `user_id` from VARCHAR to INTEGER, add foreign key
- `popup_responses` table: Change `user_id` from VARCHAR to INTEGER, add foreign key

#### 1.4 Implement Authentication Backend

**New File: `backend/auth.py`**
- Google OAuth flow handling
- Session management with NiceGUI
- User creation/lookup on first OAuth login
- JWT tokens or session cookies for authentication state

**New File: `backend/user_manager.py`**
- User CRUD operations
- Link existing anonymous data to authenticated users (migration utility)
- User profile management

#### 1.5 Update App Structure

**Modify: `app.py`**
- Add authentication middleware using NiceGUI's `ui.context`
- Protect routes (require login)
- Add login/logout pages
- Session management

**Modify: All backend managers**
- `TaskManager`, `InstanceManager`, `EmotionManager`, etc.
- Add `user_id` parameter to all methods
- Filter all queries by `user_id` (data isolation)

#### 1.6 Update UI

**New Files:**
- `ui/login.py` - Login page with Google OAuth button
- `ui/profile.py` - User profile/settings page

**Modify: All existing pages**
- Add user context checking
- Redirect to login if not authenticated
- Show current user info in navigation

### Part 2: Secure Import (Logged-In Users Only)
**Timeline: ~1 day**

#### 2.1 Modify Import Functionality

**Modify: `backend/csv_import.py`**
- Add `user_id` parameter to all import functions
- Filter imported data to match current user
- Update `import_from_zip()` to require authentication
- Ensure all imported records have `user_id` set to current user
- Keep existing abuse limits (already implemented):
  - MAX_ROWS_PER_CSV = 10,000
  - MAX_FILE_SIZE_MB = 50
  - MAX_FILES_PER_ZIP = 20
  - MAX_NEW_COLUMNS_PER_IMPORT = 10
  - Column name validation (SQL injection prevention)

#### 2.2 Update Import UI

**Modify: `ui/settings_page.py`**
- Re-enable import upload component (currently disabled)
- Add authentication check before allowing upload
- Show user-specific import status
- Display import results with user context

#### 2.3 Data Migration Strategy

**Anonymous Users → Authenticated Users:**

1. **Download Flow:**
   - Anonymous users can download their data (no auth required)
   - Export includes username/identifier in metadata
   - Users can download before creating account

2. **Import Flow:**
   - **REQUIRED**: User must be logged in (OAuth authentication)
   - Import only works for authenticated users
   - All imported data is automatically assigned to logged-in user's `user_id`
   - Cannot import data for other users
   - Import limits prevent abuse (already implemented)

3. **Linking Existing Data:**
   - On first OAuth login, prompt: "Do you have existing anonymous data to migrate?"
   - If yes, allow user to upload their exported ZIP
   - System automatically links imported data to new account
   - One-time migration, then regular import flow

### Part 3: Local Testing with Docker PostgreSQL
**Timeline: ~1 day**

#### 3.1 Docker Setup

**Create: `docker-compose.test.yml`**
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: testuser
      POSTGRES_PASSWORD: testpassword
      POSTGRES_DB: task_aversion_test
    ports:
      - "5433:5432"  # Use 5433 to avoid conflict with existing PostgreSQL
    volumes:
      - postgres_test_data:/var/lib/postgresql/data
volumes:
  postgres_test_data:
```

#### 3.2 Testing Checklist

- [ ] Start Docker PostgreSQL: `docker-compose -f docker-compose.test.yml up -d`
- [ ] Test all PostgreSQL migrations (001-010) locally
- [ ] Verify schema is correct for all tables
- [ ] Test OAuth flow locally (Google OAuth with localhost callback)
- [ ] Test user registration via OAuth
- [ ] Test data isolation (users can only see their own data)
- [ ] Test authenticated import (logged-in user only)
- [ ] Test import limits (abuse prevention)
- [ ] Test anonymous data export → authenticated import flow
- [ ] Verify all indexes are created correctly
- [ ] Test foreign key constraints
- [ ] Performance test with sample data

#### 3.3 Local Testing Environment Variables

Create `.env.local`:
```bash
# Database (Docker PostgreSQL)
DATABASE_URL=postgresql://testuser:testpassword@localhost:5433/task_aversion_test

# OAuth (Google - use localhost redirect)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
NICEGUI_SECRET_KEY=your-secret-key-for-sessions  # Generate random key

# NiceGUI
NICEGUI_HOST=127.0.0.1
NICEGUI_PORT=8080
```

### Part 4: Documentation Updates

#### 4.1 Update Server Migration Checklist

Add Phase 2B details:
- OAuth setup instructions
- User migration strategy
- Import security requirements
- Local testing steps

#### 4.2 Update README

Add authentication section:
- How to set up Google OAuth
- How to test locally
- Data migration guide for anonymous users

## Implementation Order

**Recommended Order:**

1. ✅ **Phase 2: PostgreSQL Migrations** (DONE)
2. 🔄 **Phase 2B: OAuth Authentication** (IN PROGRESS)
   - Database migrations (009, 010)
   - OAuth implementation
   - Secure import modifications
   - Local testing
3. ⏳ **Phase 3: Deployment Configuration** (After Phase 2B)
   - Update with auth requirements
   - Server deployment configs
   - Environment variable templates
4. ⏳ **Phase 4: Server Deployment** (After Phase 3)
   - Deploy to VPS
   - Test on production server

## Security Considerations

- ✅ OAuth 2.0 with Google (secure, trusted provider)
- ✅ Session security (HTTP-only cookies, SameSite)
- ✅ CSRF protection (NiceGUI handles this)
- ✅ SQL injection prevention (SQLAlchemy ORM + column validation)
- ✅ Rate limiting on import (already implemented)
- ✅ File size limits (already implemented)
- ✅ User data isolation (critical - all queries filter by user_id)
- ✅ Import limits (already implemented)

## Testing Strategy

### Local Testing (Before Deployment)

1. **Unit Tests:**
   - Authentication flow
   - User creation/lookup
   - Data isolation (queries filter by user_id)
   - Import with authentication

2. **Integration Tests:**
   - Full OAuth flow (login → callback → session)
   - Data import with user isolation
   - Anonymous export → authenticated import

3. **Security Tests:**
   - Unauthenticated access blocked
   - Users cannot access other users' data
   - Import limits enforced
   - SQL injection attempts blocked

### Server Testing (After Deployment)

1. **Production OAuth Flow**
2. **HTTPS requirements**
3. **Session persistence**
4. **Load testing**

## Timeline Estimate

- **OAuth Implementation**: 2-3 days
- **Import Modifications**: 1 day
- **Database Migrations**: 1 day
- **Local Testing**: 1 day
- **Documentation**: 0.5 days
- **Total**: ~5-6 days

## Next Steps

1. ✅ Review and approve plan
2. ⏳ Set up Google OAuth credentials
3. ⏳ Create database migration 009 (users table)
4. ⏳ Create database migration 010 (user_id foreign keys)
5. ⏳ Implement OAuth authentication
6. ⏳ Modify import to require authentication
7. ⏳ Set up local Docker PostgreSQL testing
8. ⏳ Test everything locally
9. ⏳ Update documentation
