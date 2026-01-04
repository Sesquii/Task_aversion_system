# Commit Message

## Add Notes Feature for Behavioral and Emotional Pattern Observations

Add notes page to dashboard for capturing observations about behavioral patterns, emotional patterns, and analytics insights. Includes full database backend support with migration script.

### Features

- **Notes page (`/notes`):**
  - Create new notes via textarea input
  - View all notes sorted by timestamp (newest first)
  - Delete individual notes
  - Timestamp display for each note (formatted as YYYY-MM-DD HH:MM:SS)

- **Dashboard integration:**
  - Added "Notes" button in dashboard header navigation (between Summary and Analytics)
  - Uses Material Icon "note"

- **Default note initialization:**
  - Automatically creates default note "suno after music walks seems useful" when notes file/database is first created

- **Database backend support:**
  - Full database backend support (defaults to SQLite, can use PostgreSQL)
  - CSV fallback support for compatibility
  - Migration script to migrate existing CSV notes to database
  - Follows same pattern as TaskManager for consistency

### Technical Details

- **Storage:**
  - Database-backed storage using `Note` model (SQLAlchemy)
  - CSV fallback support via `NotesManager` class (similar pattern to `TaskManager` and `UserStateManager`)
  - Notes stored in database table `notes` with columns: `note_id`, `content`, `timestamp`
  - CSV storage uses `data/notes.csv` with same column structure

- **Database model:**
  - Added `Note` class to `backend/database.py`
  - Primary key: `note_id` (format: `note-{timestamp_ms}`)
  - Timestamp field indexed for efficient sorting
  - Supports both SQLite (default) and PostgreSQL

- **Migration:**
  - Added notes migration section to `migrate_csv_to_database.py`
  - Migrates notes from CSV to database with timestamp parsing
  - Handles ISO format timestamps with fallback to current time if parsing fails
  - Skips notes that already exist in database (idempotent)

- **NotesManager:**
  - Defaults to database backend (like TaskManager)
  - Falls back to CSV if database initialization fails (unless strict mode)
  - Respects `USE_CSV` environment variable for explicit CSV usage
  - Each note gets a unique ID with format `note-{timestamp_ms}`
  - Notes are persisted and reloaded on each operation for data consistency

### Files Changed

- `task_aversion_app/backend/database.py` - Added `Note` model
- `task_aversion_app/backend/notes_manager.py` - New backend manager for notes storage (database + CSV support)
- `task_aversion_app/ui/notes_page.py` - New notes page UI
- `task_aversion_app/ui/dashboard.py` - Added Notes button to header navigation
- `task_aversion_app/app.py` - Registered notes page route
- `task_aversion_app/migrate_csv_to_database.py` - Added notes migration section

### Route

- `/notes` - Notes page for viewing and creating behavioral/emotional pattern observations

### Migration

To migrate existing CSV notes to database, run:
```bash
cd task_aversion_app
python migrate_csv_to_database.py
```
