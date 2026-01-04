# Commit Message

## Add Comprehensive CSV Export/Import with ZIP Support and Abuse Prevention

Add complete CSV export/import functionality with ZIP file support for data backup and restoration. Includes automatic schema evolution, abuse prevention measures, and comprehensive error handling. Import feature is temporarily disabled pending security testing.

### Features

- **CSV Export (`backend/csv_export.py`):**
  - Export all database tables to CSV files (tasks, instances, emotions, popup triggers/responses, notes)
  - Export user preferences CSV file
  - Create timestamped ZIP archives containing all data files
  - Browser download support via NiceGUI `ui.download()`
  - Comprehensive export summary with record counts

- **CSV Import (`backend/csv_import.py`):**
  - Import data from ZIP archives or individual CSV files
  - Automatic schema evolution: detects and adds missing columns to database
  - Handles missing CSV columns gracefully (uses database defaults)
  - Handles extra CSV columns (attempts to add to schema, falls back to backup CSV)
  - Type inference for dynamically added columns (INTEGER, REAL, TEXT)
  - Backup system for extra columns that can't be added to schema
  - Comprehensive error handling with detailed logging

- **Settings Page Integration:**
  - Export to CSV button (saves to data/ folder)
  - Download as ZIP button (browser download)
  - Import from ZIP upload component (currently disabled for security)
  - Clear abuse prevention limits displayed to users

- **Migration Script Integration:**
  - Automatic CSV export after migration completes
  - Creates backup of database state in CSV format
  - Integrated into `migrate_csv_to_database.py` and `migrate_instances_csv_to_database.py`

### Abuse Prevention Measures

- **Column Limits:**
  - Maximum 10 new columns per import
  - Maximum 100 total columns per table
  - Column name validation (alphanumeric + underscores only)
  - SQL injection prevention (blocks SQL keywords in column names)
  - Column name length limits (1-64 characters)

- **Row Limits:**
  - Maximum 10,000 rows per CSV file
  - Excess rows are truncated (first N rows processed)

- **File Size Limits:**
  - Maximum 50 MB per file (matches UI limit)
  - Applied to both CSV files and ZIP archives

- **ZIP Archive Limits:**
  - Maximum 20 files per ZIP archive

- **Validation:**
  - File size checks before processing
  - Column name validation with security checks
  - Type inference and validation for new columns

### Technical Details

- **Export System:**
  - `export_all_data_to_csv()`: Exports all database tables and user preferences
  - `create_data_zip()`: Creates timestamped ZIP file with all CSV exports
  - `get_export_summary()`: Generates human-readable export statistics
  - Supports all database models: Task, TaskInstance, Emotion, PopupTrigger, PopupResponse, Note

- **Import System:**
  - `import_from_zip()`: Main import function for ZIP archives
  - Individual import functions for each table type
  - `handle_extra_columns()`: Detects and adds missing columns to database schema
  - `validate_column_name()`: Security validation for column names
  - `check_file_size()`: File size validation
  - `safe_get()`, `safe_int()`, `safe_float()`: Safe data extraction helpers
  - Graceful error handling: continues processing valid data even when errors occur

- **Schema Evolution:**
  - Automatically detects CSV columns not in database
  - Infers column types from sample data
  - Attempts to add columns using ALTER TABLE
  - Falls back to backup CSV if schema update fails
  - Uses `setattr()` for dynamic column assignment

- **Error Handling:**
  - Row-level error handling (continues processing other rows)
  - File-level error handling (returns partial results)
  - Detailed logging with tracebacks
  - User-friendly error messages

### Security Status

⚠️ **IMPORT FEATURE TEMPORARILY DISABLED** ⚠️

The CSV import feature is currently **disabled in the UI** pending security testing. All code is preserved and functional, but the upload component is disabled to prevent use before security audit.

**To re-enable after security testing:**
1. Remove early return in `handle_upload()` in `ui/settings_page.py`
2. Remove `disabled` prop from upload component
3. Remove security warning card
4. Conduct thorough security testing

**Security concerns to test:**
- SQL injection via column names
- File path traversal in ZIP extraction
- Resource exhaustion (large files, many columns)
- Schema manipulation attacks
- Data integrity validation

### Files Changed

- `task_aversion_app/backend/csv_export.py` - New comprehensive export utility
- `task_aversion_app/backend/csv_import.py` - New comprehensive import utility with abuse prevention
- `task_aversion_app/ui/settings_page.py` - Added export/import UI with security warnings
- `task_aversion_app/migrate_csv_to_database.py` - Added automatic CSV export after migration
- `task_aversion_app/migrate_instances_csv_to_database.py` - Added automatic CSV export after migration
- `task_aversion_app/export_to_csv.py` - Updated to use new comprehensive export function

### Usage

**Export Data:**
- Click "Export Data to CSV" in Settings to save CSV files to data/ folder
- Click "Download Data as ZIP" in Settings to download ZIP archive via browser

**Import Data (Currently Disabled):**
- Upload ZIP file via "Import Data from ZIP" component (disabled pending security testing)
- System will automatically detect and add missing columns
- Extra columns that can't be added are saved to backup CSV files

### Migration

Export functionality is automatically integrated into migration scripts. After running migration, database state is automatically exported to CSV for backup.
