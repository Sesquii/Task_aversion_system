# Migrations 009 & 010: OAuth Authentication Schema

## Summary

Migrations 009 and 010 prepare the database for OAuth authentication by:
1. Creating a `users` table for authenticated user accounts
2. Adding `user_id` foreign keys to existing tables for data isolation

## Migration 009: Create Users Table

**File**: `009_create_users_table.py`

Creates the `users` table with:
- `user_id` SERIAL PRIMARY KEY (INTEGER, auto-increment)
- `email` VARCHAR(255) UNIQUE NOT NULL (for OAuth login)
- `google_id` VARCHAR(255) UNIQUE (Google OAuth ID)
- `oauth_provider` VARCHAR(50) DEFAULT 'google'
- `email_verified` BOOLEAN DEFAULT TRUE (Google emails are pre-verified)
- `is_active` BOOLEAN DEFAULT TRUE
- `created_at` TIMESTAMP (indexed)
- `last_login` TIMESTAMP

**Indexes**:
- Index on `email` for OAuth lookups
- Index on `google_id` for OAuth lookups

## Migration 010: Add user_id Foreign Keys

**File**: `010_add_user_id_foreign_keys.py`

This migration adds `user_id` INTEGER foreign keys to existing tables for user data isolation.

### Tables Updated

**New user_id columns (added):**
- `tasks` - Links tasks to users
- `task_instances` - Links task instances to users
- `notes` - Links notes to users

**VARCHAR to INTEGER conversion (adds `user_id_new` column):**
- `survey_responses` - Will have both VARCHAR `user_id` (old) and INTEGER `user_id_new` (new)
- `popup_triggers` - Will have both VARCHAR `user_id` (old) and INTEGER `user_id_new` (new)
- `popup_responses` - Will have both VARCHAR `user_id` (old) and INTEGER `user_id_new` (new)

**Special case - PRIMARY KEY conversion needed:**
- `user_preferences` - Has VARCHAR `user_id` as PRIMARY KEY
  - **Requires separate migration (010b)** for PRIMARY KEY conversion
  - Cannot easily convert PRIMARY KEY from VARCHAR to INTEGER
  - Will need: 1) Create new table, 2) Migrate data, 3) Drop old table, 4) Rename new table

### Important Notes

1. **All new `user_id` columns are nullable initially** to allow existing anonymous data to remain in the database.

2. **Tables with VARCHAR `user_id` get `user_id_new` INTEGER column** - Original VARCHAR column kept temporarily for data migration.

3. **Data Migration Required**: After migration 010, a separate script will:
   - Create User records for existing anonymous users (or link to system user)
   - Populate INTEGER `user_id` from VARCHAR `user_id` where applicable
   - Handle the `user_preferences` PRIMARY KEY conversion

4. **Foreign Key Constraints**: New `user_id` columns have `ON DELETE CASCADE` constraints to automatically delete related data when a user is deleted.

## Data Import Clarification

**IMPORTANT**: The CSV import functionality (`backend/csv_import.py`) **writes to the DATABASE**, not CSV files!

- Despite the name "csv_import", it:
  - Reads data FROM CSV/ZIP files
  - Writes data TO the database using SQLAlchemy (`session.add()`, `session.commit()`)
  - Does NOT modify or write CSV files

- CSV files are only used as:
  - **Export format** for data portability
  - **Import source** for data migration

- When importing data:
  1. User uploads ZIP file containing CSV files
  2. System extracts CSV files from ZIP
  3. System reads CSV files
  4. System writes data to database (PostgreSQL/SQLite) via SQLAlchemy models
  5. CSV files are temporary - not stored or used by the app

## Next Steps After Migrations 009 & 010

1. ✅ Create migrations 009 and 010 (DONE)
2. ⏳ Implement OAuth authentication backend (`backend/auth.py`)
3. ⏳ Create data migration script (010b) for `user_preferences` PRIMARY KEY conversion
4. ⏳ Create data migration script to populate INTEGER `user_id` from VARCHAR `user_id`
5. ⏳ Update all backend managers to filter queries by `user_id`
6. ⏳ Modify import functions to require authentication and filter by `user_id`
7. ⏳ Test OAuth flow locally
8. ⏳ Test authenticated import with user isolation
