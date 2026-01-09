---
name: OAuth Authentication with Anonymous Mode
overview: Update deployment plans to implement OAuth (Google) authentication with optional anonymous mode for initial website deployment. Replace username-only interim auth with secure OAuth, while maintaining anonymous mode for local/browser-only use.
todos:
  - id: db_users_table
    content: Create Users table migration with OAuth fields (id, email, oauth_provider, oauth_id, name, picture_url, timestamps)
    status: pending
  - id: db_user_id_columns
    content: Add user_id foreign key columns to tasks, task_instances, emotions, notes tables with migration script
    status: pending
    dependencies:
      - db_users_table
  - id: db_models_update
    content: Update database.py to add User model and user_id columns to existing models (Task, TaskInstance, Emotion, Note)
    status: pending
    dependencies:
      - db_users_table
      - db_user_id_columns
  - id: oauth_dependencies
    content: Add authlib and itsdangerous to requirements.txt
    status: pending
  - id: auth_module
    content: Create backend/auth.py with OAuth client, session management, and authentication functions
    status: pending
    dependencies:
      - oauth_dependencies
      - db_models_update
  - id: auth_routes
    content: Add OAuth routes to app.py (/auth/login, /auth/callback, /auth/logout) with session handling
    status: pending
    dependencies:
      - auth_module
  - id: anonymous_support
    content: Implement anonymous user creation and management in auth.py, link to localStorage IDs
    status: pending
    dependencies:
      - auth_module
  - id: auth_ui
    content: Create ui/auth_page.py with Google sign-in button and anonymous mode option with warnings
    status: pending
    dependencies:
      - auth_routes
      - anonymous_support
  - id: update_managers
    content: Update TaskManager, InstanceManager, EmotionManager to accept user_id parameter and filter queries
    status: pending
    dependencies:
      - db_models_update
  - id: update_ui_pages
    content: Update all UI page handlers to get user_id from session/localStorage and pass to backend managers
    status: pending
    dependencies:
      - auth_routes
      - update_managers
  - id: migration_tool
    content: Create migrate_anonymous_to_account.py utility to migrate anonymous user data to OAuth account
    status: pending
    dependencies:
      - update_managers
  - id: env_config
    content: Update .env.example with GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SECRET_KEY variables
    status: pending
  - id: deployment_plan_update
    content: Update deployment-2d421cbd.plan.md to replace username-only auth with OAuth strategy
    status: pending
  - id: user_profile_ui
    content: Add user profile display (name, email, picture) and logout button to dashboard/header
    status: pending
    dependencies:
      - auth_routes
---

# OAuth Authentication with Anonymous Mode - Updated Deployment Plan

## Overview

This plan updates the deployment strategy to use OAuth (Google) authentication for the initial website deployment, replacing the username-only interim approach. Anonymous mode remains available for local/browser-only use with clear warnings about data persistence limitations.

## Phase 1: Database Schema Updates for Multi-User Support

### 1.1 Add Users Table

**New Migration**: `SQLite_migration/XXX_add_users_table.py`

- Create `users` table with OAuth fields:
  - `id` (String, primary key, UUID)
  - `email` (String, unique, nullable=False) - from Google OAuth
  - `oauth_provider` (String, default='google') - for future multi-provider support
  - `oauth_id` (String, unique, nullable=False) - Google user ID
  - `name` (String, nullable=True) - display name from Google
  - `picture_url` (String, nullable=True) - profile picture URL
  - `created_at` (DateTime)
  - `last_login_at` (DateTime)
  - `is_active` (Boolean, default=True)
- Add indexes on `email`, `oauth_id`, `oauth_provider`

**File**: `task_aversion_app/backend/database.py`

- Add `User` model class following existing pattern (Task, TaskInstance, etc.)

### 1.2 Add user_id Foreign Keys to Existing Tables

**New Migration**: `SQLite_migration/XXX_add_user_id_to_tables.py`

- Add `user_id` column to:
  - `tasks` table (String, ForeignKey to users.id, nullable=True for migration)
  - `task_instances` table (String, ForeignKey to users.id, nullable=True)
  - `emotions` table (String, ForeignKey to users.id, nullable=True)
  - `notes` table (String, ForeignKey to users.id, nullable=True)
- Add indexes on `user_id` columns for query performance
- Set default to 'anonymous' for existing data during migration
- Update existing records to use 'anonymous' user_id

**Files to Modify**:

- `task_aversion_app/backend/database.py` - Add user_id columns to Task, TaskInstance, Emotion, Note models
- Update `to_dict()` methods to include user_id

### 1.3 Update Database Models

**File**: `task_aversion_app/backend/database.py`

- Add `User` model with OAuth fields
- Add `user_id` foreign key relationships to existing models
- Add `relationship()` definitions for SQLAlchemy ORM (optional, for convenience)

## Phase 2: OAuth Authentication Implementation

### 2.1 Install OAuth Dependencies

**File**: `task_aversion_app/requirements.txt`

- Add: `authlib>=1.2.0` (OAuth client library)
- Add: `itsdangerous>=2.1.0` (for session token signing)

### 2.2 Create Authentication Module

**New File**: `task_aversion_app/backend/auth.py`

- Implement OAuth client using Authlib
- Google OAuth configuration:
  - Client ID/Secret from environment variables
  - Redirect URI: `{base_url}/auth/callback`
  - Scopes: `openid email profile`
- Session management:
  - Use NiceGUI's session storage (FastAPI sessions)
  - Store user_id in session after OAuth callback
  - Session token signing with secret key
- Functions:
  - `get_oauth_client()` - Initialize OAuth client
  - `get_login_url()` - Generate Google login URL
  - `handle_oauth_callback(code, state)` - Process OAuth callback, create/update user
  - `get_current_user(session)` - Get authenticated user from session
  - `require_auth()` - Decorator/middleware for protected routes
  - `logout(session)` - Clear session

### 2.3 Google OAuth Setup

**External Setup** (Google Cloud Console):

- Create OAuth 2.0 credentials
- Add authorized redirect URI: `https://TaskAversionSystem.com/auth/callback` (production)
- Add authorized redirect URI: `http://localhost:8080/auth/callback` (development)
- Store Client ID and Secret in environment variables

**File**: `.env.example`

- Add:
  ```
  GOOGLE_CLIENT_ID=your_client_id_here
  GOOGLE_CLIENT_SECRET=your_client_secret_here
  SECRET_KEY=your_random_secret_key_here  # For session signing
  ```


## Phase 3: Anonymous Mode Support

### 3.1 Anonymous User Management

**File**: `task_aversion_app/backend/auth.py`

- Add anonymous user support:
  - `create_anonymous_user(local_storage_id)` - Create temporary user record
  - `get_or_create_anonymous_user(local_storage_id)` - Get existing or create new
  - Anonymous users have `oauth_provider='anonymous'` and `oauth_id=local_storage_id`
- Anonymous user limitations:
  - Data stored in database but tied to browser localStorage ID
  - Clear warnings in UI about browser-only access
  - Option to upgrade to OAuth account (migrate data)

### 3.2 Anonymous Mode UI

**New File**: `task_aversion_app/ui/auth_page.py`

- Landing page with two options:

  1. **"Sign in with Google"** button - OAuth flow
  2. **"Continue Anonymously"** button - Anonymous mode

- Clear warnings for anonymous mode:
  - "Data stored in this browser only"
  - "Not accessible from other devices"
  - "Data may be lost if browser data is cleared"
  - "Upgrade to account for multi-device access"
- After selection, store choice in session and redirect to dashboard

## Phase 4: Update Application Structure

### 4.1 Add Authentication Routes

**File**: `task_aversion_app/app.py`

- Add OAuth routes:
  - `@ui.page('/auth/login')` - Login page (redirects to Google OAuth)
  - `@ui.page('/auth/callback')` - OAuth callback handler
  - `@ui.page('/auth/logout')` - Logout handler
- Add authentication middleware:
  - Check session for authenticated user
  - Redirect to `/auth/login` if not authenticated (except anonymous mode)
  - Pass `user_id` to all page handlers

### 4.2 Update Page Handlers

**Files**: All `ui/*.py` page files

- Update all page functions to accept `user_id` parameter
- Get `user_id` from session (OAuth) or localStorage (anonymous)
- Pass `user_id` to all backend manager calls:
  - `TaskManager` methods
  - `InstanceManager` methods
  - `EmotionManager` methods
  - `Analytics` methods

**Key Files to Update**:

- `ui/dashboard.py` - Get user_id, pass to build_dashboard()
- `ui/create_task.py` - Pass user_id to task_manager.create_task()
- `ui/initialize_task.py` - Pass user_id to instance_manager
- `ui/complete_task.py` - Pass user_id to instance_manager
- `ui/analytics_page.py` - Pass user_id to analytics methods

### 4.3 Update Backend Managers

**Files**:

- `task_aversion_app/backend/task_manager.py`
- `task_aversion_app/backend/instance_manager.py`
- `task_aversion_app/backend/emotion_manager.py`

- Add `user_id` parameter to all CRUD methods
- Filter all queries by `user_id`
- Ensure data isolation between users
- Handle 'anonymous' user_id for anonymous mode

## Phase 5: User Data Migration

### 5.1 Anonymous to Account Migration

**New File**: `task_aversion_app/backend/migrate_anonymous_to_account.py`

- Function to migrate anonymous user data to OAuth account:
  - `migrate_anonymous_data(anonymous_user_id, oauth_user_id)`
  - Update all `user_id` references in:
    - tasks
    - task_instances
    - emotions
    - notes
    - popup_triggers
    - popup_responses
  - Merge user preferences
  - Delete anonymous user record after migration

### 5.2 Upgrade UI

**File**: `task_aversion_app/ui/settings_page.py` or new component

- Add "Upgrade to Account" button for anonymous users
- Show migration progress
- After migration, redirect to OAuth login
- Link anonymous localStorage ID to OAuth account

## Phase 6: Deployment Configuration Updates

### 6.1 Environment Variables

**File**: `.env.example` (update)

- Add OAuth variables:
  ```
  GOOGLE_CLIENT_ID=
  GOOGLE_CLIENT_SECRET=
  SECRET_KEY=  # Random string for session signing
  ```

- Keep existing:
  ```
  DATABASE_URL=
  NICEGUI_HOST=0.0.0.0  # For production
  ```


### 6.2 Update Deployment Plan

**File**: `.cursor/plans/deployment-2d421cbd.plan.md` (update)

- Remove: "Auth interim: Enforce unique usernames (case-insensitive)"
- Add: "Auth: OAuth (Google) with optional anonymous mode"
- Update step 3: "OAuth setup & UI" instead of "Username policy & UI notice"
- Add step: "Google Cloud Console OAuth credentials setup"

### 6.3 Production Deployment Steps

**Updated Steps**:

1. **Postgres setup** - Install Postgres, create DB/user, configure env vars
2. **Database migration** - Run SQLite migrations on PostgreSQL
3. **OAuth setup**:

   - Register app in Google Cloud Console
   - Get Client ID and Secret
   - Add to environment variables on VPS
   - Test OAuth flow locally first

4. **Nginx + TLS** - Reverse proxy, Let's Encrypt cert
5. **Systemd service** - Run app with environment variables
6. **Smoke & load checks** - Test OAuth flow, test anonymous mode
7. **Release cadence** - Tag releases, run migrations per release

## Phase 7: UI/UX Updates

### 7.1 User Profile Display

**File**: `ui/dashboard.py` or new component

- Show user info (name, email, picture) in header/navbar
- "Logout" button
- For anonymous users: Show "Upgrade to Account" button prominently

### 7.2 Session Management

**File**: `task_aversion_app/backend/auth.py`

- Session timeout handling
- Automatic session refresh
- Clear session on logout

## Implementation Order

1. **Phase 1** (Database schema) - Foundation for multi-user
2. **Phase 2** (OAuth implementation) - Core authentication
3. **Phase 3** (Anonymous mode) - Maintain backward compatibility
4. **Phase 4** (Update app structure) - Wire authentication into app
5. **Phase 5** (Migration tools) - Enable anonymous-to-account upgrade
6. **Phase 6** (Deployment config) - Production setup
7. **Phase 7** (UI/UX) - Polish user experience

## Files to Create/Modify

**New Files**:

- `task_aversion_app/backend/auth.py` - OAuth authentication module
- `task_aversion_app/ui/auth_page.py` - Login/landing page
- `task_aversion_app/backend/migrate_anonymous_to_account.py` - Data migration utility
- `SQLite_migration/XXX_add_users_table.py` - Users table migration
- `SQLite_migration/XXX_add_user_id_to_tables.py` - user_id columns migration

**Modified Files**:

- `task_aversion_app/backend/database.py` - Add User model, user_id columns
- `task_aversion_app/app.py` - Add auth routes, middleware
- `task_aversion_app/requirements.txt` - Add authlib, itsdangerous
- `task_aversion_app/backend/task_manager.py` - Add user_id filtering
- `task_aversion_app/backend/instance_manager.py` - Add user_id filtering
- `task_aversion_app/backend/emotion_manager.py` - Add user_id filtering
- All `ui/*.py` files - Pass user_id to backend methods
- `.env.example` - Add OAuth environment variables
- `.cursor/plans/deployment-2d421cbd.plan.md` - Update auth strategy

## Dependencies to Add

- `authlib>=1.2.0` - OAuth client library
- `itsdangerous>=2.1.0` - Session token signing

## Security Considerations

- Store OAuth credentials in environment variables (never commit)
- Use HTTPS in production (required for OAuth)
- Sign session tokens with SECRET_KEY
- Validate OAuth state parameter to prevent CSRF
- Rate limit OAuth callback endpoint
- Log authentication events for security monitoring

## Testing Strategy

1. **Local Testing**:

   - Test OAuth flow with localhost redirect URI
   - Test anonymous mode
   - Test data isolation between users
   - Test anonymous-to-account migration

2. **Production Testing**:

   - Verify OAuth callback with production domain
   - Test session persistence
   - Verify HTTPS requirement
   - Load test authentication endpoints

## Notes

- OAuth is free (Google, GitHub, Microsoft all offer free OAuth)
- Anonymous mode provides backward compatibility for local use
- Users can start anonymous and upgrade to account later
- All data migration happens automatically when upgrading
- Session management uses NiceGUI's built-in FastAPI session support