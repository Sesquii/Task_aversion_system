---
name: Cloud Deployment & Database Migration Plan
overview: ""
todos:
  - id: 5ada1854-739b-461e-8fcc-adeee2117d4a
    content: Create database.py with SQLAlchemy models (User, Task, TaskInstance, Emotion, Survey) using PostgreSQL-compatible types
    status: pending
  - id: f142c54f-6d92-4768-b788-f953ca1c4292
    content: Create migrate_to_sqlite.py to migrate CSV data to database with verification
    status: pending
  - id: 2b920116-31b6-461f-9e8d-3a6e7d65ea91
    content: Update task_manager.py to use database instead of CSV (replace _reload/_save methods)
    status: pending
  - id: 4d75c17e-be18-4dbb-b09f-5e153bf739d2
    content: Update instance_manager.py to use database instead of CSV (replace _reload/_save methods)
    status: pending
  - id: a42f2c14-f604-437f-b707-cf1405fca4ec
    content: Update emotion_manager.py to use database instead of CSV (replace _reload/_save methods)
    status: pending
  - id: 42f4bd23-4ada-46f3-85a3-9b8ad2b0b771
    content: Update analytics.py to use database queries instead of CSV file reads
    status: pending
  - id: 647885f4-4ee2-4a9f-a6bb-13a0ca8da7ee
    content: Create .env.example and update requirements.txt with SQLAlchemy, python-dotenv, psycopg2-binary
    status: pending
  - id: f2fa345a-c244-4bc6-9424-316ede481fda
    content: Create Procfile, runtime.txt, railway.json/render.yaml, and update app.py for production deployment
    status: pending
  - id: 81fc2e18-946b-4527-9d0b-c233c7dc8706
    content: Test database migration, verify all CRUD operations, test analytics queries, deploy to cloud and verify
    status: pending
  - id: 2a2920c7-da6e-495e-9696-5dcd8ea5d221
    content: Add aversion-related attributes to TaskInstance model (recommendation_used, excitement_change, capacity_before/after, etc.)
    status: pending
  - id: 2851325c-5c7a-40c0-ba8c-4e37c7534e84
    content: Implement calculate_aversion_score(), get_capacity_patterns(), get_completion_frequency_patterns() in analytics.py
    status: pending
  - id: 7d3813dc-47cd-4472-909c-78fe269a150b
    content: Update dashboard.py to track recommendation usage and update analytics_page.py with new visualizations
    status: pending
  - id: 0d4a5e75-ab4c-4fed-971f-f971e012270a
    content: Create auth.py with registration, login, password hashing, session management, and guest user support
    status: pending
  - id: 3f299bd0-de02-42b5-a213-7df75ca384ec
    content: Add user_id foreign keys to TaskInstance and Task models, create migration for existing data to anonymous user
    status: pending
  - id: b27c13a2-bc32-41ff-9815-0b3c880df3f9
    content: Update task_manager.py, instance_manager.py, analytics.py to filter all queries by user_id
    status: pending
  - id: 74a2d063-cf40-45d6-973e-960bb10acbc8
    content: Create login.py UI and update app.py with authentication middleware
    status: pending
  - id: febee5f8-5d0a-40b4-b9e2-99d732beb89d
    content: Create data_collection.py for anonymous data export and survey.py for survey system
    status: pending
  - id: 2fc5b3d6-072d-408f-b2d8-102499e96ee8
    content: Create ml_recommender.py for ML model integration and update analytics.py/dashboard.py to use ML recommendations
    status: pending
---

# Cloud Deployment & Database Migration Plan

## Overview

This plan migrates the Task Aversion System from CSV-based storage to a cloud-deployable application with SQLite (PostgreSQL-ready) database, then progressively adds enhanced analytics, user accounts, and ML capabilities.

## Implementation Strategy

**Branch Strategy**: Create dedicated `feature/db-migration` branch for Phase 1. Merge to main after testing, then proceed with subsequent phases.

**Deployment Target**: Anonymous use initially (Phase 1), then multi-user (Phase 3).

---

## Phase 1: Database & Cloud Foundation

**Goal**: Get the app online with anonymous use, migrate from CSV to SQLite with PostgreSQL-ready schema.

### 1.1 Database Schema Design

**New File**: `backend/database.py`

- Create SQLAlchemy models with PostgreSQL-compatible types:
- `User` (id, username, email, created_at, data_sharing_consent, survey_completed) - for future use
- `Task` (migrate from tasks.csv: task_id, name, description, type, version, created_at, is_recurring, categories JSON, default_estimate_minutes)
- `TaskInstance` (migrate from task_instances.csv: all existing columns + new fields from enhanced analytics plan)
- `Emotion` (migrate from emotions.csv: emotion)
- `Survey` (user_id, mental_health_indicators JSON, challenges JSON, submitted_at) - for future use
- Use SQLAlchemy ORM with declarative base
- Configure connection pooling for SQLite
- Add database initialization function
- Support both SQLite (local/dev) and PostgreSQL (production) via DATABASE_URL env var

### 1.2 Database Migration Script

**New File**: `backend/migrate_to_sqlite.py`

- Read existing CSV files (tasks.csv, task_instances.csv, emotions.csv)
- Transform CSV data to SQLAlchemy models
- Handle JSON columns (predicted, actual, categories)
- Preserve all existing data
- Add migration verification (row counts, sample data checks)
- Create rollback capability (export back to CSV if needed)

### 1.3 Update Data Access Layer

**Files to Modify**:

- `backend/task_manager.py` - Replace CSV operations with SQLAlchemy queries
- `backend/instance_manager.py` - Replace CSV operations with SQLAlchemy queries  
- `backend/emotion_manager.py` - Replace CSV operations with SQLAlchemy queries
- `backend/analytics.py` - Replace CSV file reads with database queries

**Implementation**:

- Create database session management (context manager)
- Update all `_reload()` methods to query database
- Update all `_save()` methods to commit to database
- Maintain backward-compatible method signatures
- Add connection error handling
- Keep CSV files as backup during transition

### 1.4 Environment Configuration

**New File**: `.env.example`

- `DATABASE_URL` (default: `sqlite:///./data/task_aversion.db` for local, PostgreSQL URL for production)
- `SECRET_KEY` (for future session management)
- `ENVIRONMENT` (development/production)

**Modified File**: `requirements.txt`

- Add: `sqlalchemy`, `python-dotenv`, `psycopg2-binary` (for PostgreSQL support)

### 1.5 Deployment Configuration

**New Files**:

- `Procfile` (for Heroku/Railway): `web: python -m task_aversion_app.app`
- `runtime.txt`: Python version specification
- `railway.json` or `render.yaml`: Deployment platform config
- `Dockerfile` (optional): Containerization for consistent deployment

**Modified File**: `app.py`

- Add environment-based configuration
- Update `ui.run()` with production settings (host, port from env vars)
- Add health check endpoint
- Configure static file serving
- Add basic error handling and logging

### 1.6 Testing & Verification

- Test database migration with existing CSV data
- Verify all CRUD operations work with database
- Test analytics queries return same results as CSV-based version
- Test deployment locally with SQLite
- Deploy to cloud platform (Railway/Render/Heroku) with PostgreSQL
- Verify app is accessible and functional in production

**Checkpoint**: App is live and accessible online with anonymous use, all data migrated to database.

---

## Phase 2: Enhanced Analytics

**Goal**: Implement enhanced analytics features from existing plan while app is live.

### 2.1 Time-Calibrated Relief Metrics

**File**: `backend/analytics.py`

- Add `relief_duration_score` calculation (already implemented, verify)
- Add `total_relief_score` calculation (already implemented, verify)
- Update `get_relief_summary()` to include new metrics (already done, verify)

**File**: `ui/dashboard.py`

- Display new metrics in summary section (verify if already present)

### 2.2 Enhanced Tracking System

**Reference**: `enhanced-analytics-and-tracking-system-5b010422.plan.md`

**Priority Implementation** (from existing plan):

- Add aversion-related attributes to `TaskInstance` model:
- `recommendation_used` (boolean)
- `excitement_change` (numeric)
- `capacity_before` (numeric 0-100)
- `capacity_after` (numeric 0-100)
- `time_since_last_completion` (numeric, days)
- `recommendation_viewed` (boolean)

**File**: `backend/database.py`

- Add new columns to `TaskInstance` model
- Create migration script to add columns to existing database

**File**: `backend/analytics.py`

- Implement `calculate_aversion_score()` method
- Add `get_capacity_patterns()` for bidirectional capacity analysis
- Add `get_completion_frequency_patterns()` for time-since-completion tracking
- Add recommendation effectiveness tracking

**File**: `ui/dashboard.py`

- Track recommendation usage when user clicks "init" from recommended task
- Store recommendation source in task instance

**File**: `ui/analytics_page.py`

- Display aversion score trends
- Show bidirectional capacity patterns
- Display time-since-completion patterns
- Show recommendation effectiveness metrics

**Checkpoint**: Enhanced analytics are working in production, collecting richer data.

---

## Phase 3: User Accounts & Authentication

**Goal**: Enable multi-user support with secure data separation.

### 3.1 Authentication System

**New File**: `backend/auth.py`

- User registration (username, email, password)
- Login/logout functionality
- Password hashing with bcrypt
- Session management (Flask sessions or JWT tokens)
- Guest/anonymous user support (default user for existing data)

**Modified File**: `app.py`

- Add authentication middleware
- Protect routes (optional: allow anonymous access initially)
- Add user context to all database operations

### 3.2 Database Schema Updates

**File**: `backend/database.py`

- Add `user_id` foreign key to `TaskInstance` and `Task` models
- Create migration script to assign existing data to default/anonymous user
- Add user preferences table (settings, mode preferences)

### 3.3 Update Data Access Layer

**Files**: `backend/task_manager.py`, `backend/instance_manager.py`, `backend/analytics.py`

- Filter all queries by `user_id`
- Ensure data isolation between users
- Update all methods to accept user context

### 3.4 User Interface Updates

**New File**: `ui/login.py` - Login/registration page

**Modified Files**: `ui/*.py`

- Add user profile/settings page
- Add logout functionality
- Show current user in UI
- Add data privacy controls

**Modified File**: `requirements.txt`

- Add: `bcrypt`, `flask` (if using Flask sessions) or `pyjwt` (if using JWT)

**Checkpoint**: Multi-user support is live, existing data migrated to anonymous user account.

---

## Phase 4: ML Training Pipeline

**Goal**: Operationalize data collection and ML recommendation system.

### 4.1 Data Collection Infrastructure

**New File**: `backend/data_collection.py`

- Opt-in anonymous data export (aggregate statistics only)
- Privacy-preserving data anonymization
- Data export for ML training (CSV/JSON format)
- User consent management

### 4.2 Survey System

**New File**: `backend/survey.py`

- Mental health indicators questionnaire
- Task completion challenges survey
- Survey data linked to task performance
- Store survey responses in database

**New File**: `ui/survey_page.py`

- Onboarding survey UI
- Periodic check-in surveys
- Survey results visualization

### 4.3 ML Model Integration

**New File**: `backend/ml_recommender.py`

- Load trained ML model (scikit-learn, PyTorch, or LightFM)
- Generate personalized recommendations based on user history
- Fallback to rule-based recommendations if model unavailable
- Model versioning and A/B testing support

**File**: `backend/analytics.py`

- Integrate ML recommendations alongside rule-based
- Track recommendation source (ML vs rule-based)
- Measure ML recommendation effectiveness

**File**: `ui/dashboard.py`

- Display ML-powered recommendations
- Show recommendation confidence scores
- Allow user feedback on recommendations

**Checkpoint**: ML pipeline is operational, collecting training data, and providing personalized recommendations.

---

## Files Summary

### New Files (Phase 1)

- `backend/database.py` - SQLAlchemy models and database setup
- `backend/migrate_to_sqlite.py` - CSV to database migration
- `.env.example` - Environment variables template
- `Procfile` - Deployment configuration
- `runtime.txt` - Python version
- `railway.json` or `render.yaml` - Platform-specific config
- `Dockerfile` (optional) - Containerization

### Modified Files (Phase 1)

- `backend/task_manager.py` - Replace CSV with database
- `backend/instance_manager.py` - Replace CSV with database
- `backend/emotion_manager.py` - Replace CSV with database
- `backend/analytics.py` - Replace CSV reads with database queries
- `app.py` - Production configuration, environment setup
- `requirements.txt` - Add SQLAlchemy, python-dotenv, psycopg2-binary

### New Files (Phase 2)

- Database migration script for new analytics columns

### Modified Files (Phase 2)

- `backend/database.py` - Add new TaskInstance columns
- `backend/analytics.py` - Enhanced analytics methods
- `ui/dashboard.py` - Recommendation tracking
- `ui/analytics_page.py` - New visualizations

### New Files (Phase 3)

- `backend/auth.py` - Authentication system
- `ui/login.py` - Login/registration UI

### Modified Files (Phase 3)

- `backend/database.py` - Add user_id foreign keys
- `backend/task_manager.py` - User-scoped queries
- `backend/instance_manager.py` - User-scoped queries
- `backend/analytics.py` - User-scoped queries
- `app.py` - Authentication middleware
- `requirements.txt` - Add bcrypt, flask or pyjwt

### New Files (Phase 4)

- `backend/data_collection.py` - Anonymous data export
- `backend/survey.py` - Survey system
- `backend/ml_recommender.py` - ML model integration
- `ui/survey_page.py` - Survey UI

### Modified Files (Phase 4)

- `backend/analytics.py` - ML recommendation integration
- `ui/dashboard.py` - ML recommendations display

---

## Dependencies by Phase

**Phase 1**: `sqlalchemy`, `python-dotenv`, `psycopg2-binary`

**Phase 3**: `bcrypt`, `flask` (or `pyjwt`)

**Phase 4**: `scikit-learn` (or `pytorch`, `lightfm`), `numpy`

---

## Critical Success Factors

1. **Data Migration**: Zero data loss during CSV → Database migration
2. **Backward Compatibility**: Existing UI and functionality continues to work
3. **Performance**: Database queries are as fast or faster than CSV reads
4. **Deployment**: App is accessible and stable in cloud environment
5. **User Experience**: No disruption to existing workflows during migration

---

## Risk Mitigation

- Keep CSV files as backup during Phase 1 migration
- Test database migration on copy of production data
- Implement database connection retry logic
- Add comprehensive error logging
- Create rollback procedures for each phase
- Test each phase thoroughly before proceeding to next

---

## Next Steps

1. Create `feature/db-migration` branch
2. Implement Phase 1 (Database & Cloud Foundation)
3. Test locally with SQLite
4. Deploy to cloud with PostgreSQL
5. Verify all functionality works in production
6. Merge to main
7. Proceed with Phase 2 (Enhanced Analytics)
8. Continue with Phase 3 and 4 as planned