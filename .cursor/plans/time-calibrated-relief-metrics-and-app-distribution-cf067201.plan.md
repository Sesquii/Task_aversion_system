<!-- cf067201-9b88-4ade-9a21-d10da46e8491 db4129a1-b945-4ce5-bd4c-9239de10cb8a -->
# Time-Calibrated Relief Metrics & App Distribution Plan

## Overview

This plan adds time-calibrated relief metrics, makes the app distributable online with user accounts, implements data collection infrastructure, and migrates from CSV to SQLite (with PostgreSQL-ready schema).

## Phase 1: Time-Calibrated Relief Metrics

### 1.1 Add Relief × Duration Metric

- **File**: `backend/analytics.py`
- Add `relief_duration_score` calculation: `relief_score × duration_minutes` per task instance
- Update `get_relief_summary()` to include:
- `relief_duration_score` per completed task
- `total_relief_duration_score` (sum across all tasks)
- `avg_relief_duration_score` (average per task)

### 1.2 Add Total Relief Score Metric

- **File**: `backend/analytics.py`
- Add `total_relief_score` calculation: sum of `relief_score × duration_minutes` across all completed tasks
- Include in relief summary and dashboard displays

### 1.3 Update Dashboard UI

- **File**: `ui/dashboard.py`
- Display new metrics in summary section:
- Relief × Duration Score (per task and total)
- Total Relief Score
- Add to analytics page visualizations

## Phase 2: Database Migration (SQLite with PostgreSQL-Ready Schema)

### 2.1 Create Database Schema

- **New File**: `backend/database.py`
- Create SQLite database with tables:
- `users` (id, username, email, created_at, data_sharing_consent, survey_completed)
- `tasks` (migrate from tasks.csv)
- `task_instances` (migrate from task_instances.csv)
- `emotions` (migrate from emotions.csv)
- `surveys` (user_id, mental_health_indicators, challenges, submitted_at)
- Use SQLAlchemy ORM for PostgreSQL compatibility
- Schema designed to be PostgreSQL-compatible from the start

### 2.2 Create Migration Script

- **New File**: `backend/migrate_to_sqlite.py`
- Migrate existing CSV data to SQLite
- Preserve all existing data
- Add migration verification

### 2.3 Update Data Access Layer

- **Files**: `backend/task_manager.py`, `backend/instance_manager.py`, `backend/emotion_manager.py`
- Replace CSV operations with database queries
- Maintain backward compatibility during transition
- Add connection pooling for SQLite

## Phase 3: User Authentication & Accounts

### 3.1 Add Authentication System

- **New File**: `backend/auth.py`
- Implement user registration/login
- Session management
- Password hashing (bcrypt)
- Guest/anonymous user support

### 3.2 Update App Structure

- **File**: `app.py`
- Add authentication middleware
- Route protection
- User context in all operations

### 3.3 Update UI for Multi-User

- **Files**: `ui/*.py`
- Add login/register pages
- User profile/settings
- Data privacy controls

## Phase 4: Data Collection Infrastructure

### 4.1 Anonymous Data Collection

- **File**: `backend/data_collection.py`
- Opt-in anonymous data export
- Aggregate statistics collection
- Privacy-preserving data anonymization

### 4.2 Survey System

- **New File**: `backend/survey.py`
- Mental health indicators questionnaire
- Task completion challenges survey
- Optional user surveys linked to accounts
- Survey data linked to task performance for ML training

### 4.3 Survey UI

- **New File**: `ui/survey_page.py`
- Onboarding survey
- Periodic check-in surveys
- Survey results visualization

## Phase 5: Deployment Configuration

### 5.1 Environment Configuration

- **New File**: `.env.example`
- Environment variables for:
- Database URL (SQLite local, PostgreSQL for production)
- Secret keys
- Deployment settings

### 5.2 Deployment Files

- **New File**: `requirements.txt` (update with new dependencies)
- **New File**: `Procfile` (for Heroku/Railway)
- **New File**: `railway.json` or `render.yaml` (deployment config)
- **New File**: `Dockerfile` (optional, for containerization)

### 5.3 Production Readiness

- **File**: `app.py`
- Add production server configuration
- Environment-based settings
- Error handling and logging

## Phase 6: Recommendation Engine Enhancement

### 6.1 Data Aggregation for ML

- **File**: `backend/analytics.py`
- Aggregate anonymous data for pattern analysis
- Feature engineering for ML models
- Data export for training

### 6.2 Survey Integration with Recommendations

- **File**: `backend/analytics.py`
- Use survey data to personalize recommendations
- Mental health indicators → task filtering
- Challenge patterns → task suggestions

## Implementation Order Recommendation

1. **Phase 1** (Time-calibrated metrics) - Quick win, no dependencies
2. **Phase 2** (Database migration) - Foundation for everything else
3. **Phase 5** (Deployment config) - Get it online quickly
4. **Phase 3** (User accounts) - Enable multi-user
5. **Phase 4** (Data collection) - Start gathering data
6. **Phase 6** (ML enhancements) - Use collected data

## Files to Create/Modify

**New Files:**

- `backend/database.py` - Database schema and connection
- `backend/migrate_to_sqlite.py` - CSV to SQLite migration
- `backend/auth.py` - Authentication system
- `backend/data_collection.py` - Anonymous data collection
- `backend/survey.py` - Survey system
- `ui/survey_page.py` - Survey UI
- `.env.example` - Environment template
- `Procfile` - Deployment config
- `railway.json` or `render.yaml` - Deployment config

**Modified Files:**

- `backend/analytics.py` - Add time-calibrated metrics
- `ui/dashboard.py` - Display new metrics
- `backend/task_manager.py` - Database operations
- `backend/instance_manager.py` - Database operations
- `backend/emotion_manager.py` - Database operations
- `app.py` - Authentication middleware, production config
- `requirements.txt` - Add SQLAlchemy, bcrypt, python-dotenv

## Dependencies to Add

- `sqlalchemy` - Database ORM
- `bcrypt` - Password hashing
- `python-dotenv` - Environment variables
- `flask` or `fastapi` (optional) - If needed for auth middleware