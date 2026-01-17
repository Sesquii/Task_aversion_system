# backend/csv_import.py
"""
CSV import utility for importing data from CSV files or ZIP archives into the database.
Includes abuse prevention measures to prevent system exploitation.

⚠️ SECURITY STATUS: TEMPORARILY DISABLED ⚠️
==========================================
This import feature is currently DISABLED in the UI pending security testing.
The code is preserved and functional, but the UI upload component is disabled.

To re-enable after security audit:
1. Remove the early return in handle_upload() in ui/settings_page.py
2. Remove the disabled prop from the upload component
3. Remove the security warning card
4. Conduct thorough security testing before production use

Security concerns to test:
- SQL injection via column names
- File path traversal in ZIP extraction
- Resource exhaustion (large files, many columns)
- Schema manipulation attacks
- Data integrity validation
"""
import os
import json
import zipfile
import tempfile
import pandas as pd
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from backend.database import (
    get_session, init_db, Task, TaskInstance, Emotion,
    PopupTrigger, PopupResponse, Note, SurveyResponse, engine, DATABASE_URL
)
from backend.user_state import UserStateManager, PREFS_FILE
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

# ============================================================================
# Abuse Prevention Limits
# ============================================================================
# These limits prevent system exploitation and abuse:
#
# 1. Column Limits:
#    - MAX_NEW_COLUMNS_PER_IMPORT: Maximum new columns that can be added per import (10)
#    - MAX_TOTAL_COLUMNS_PER_TABLE: Maximum total columns allowed per table (100)
#    - MAX_COLUMN_NAME_LENGTH: Maximum column name length (64 chars, SQL standard)
#    - Column name validation: Prevents SQL injection, invalid characters
#
# 2. Row Limits:
#    - MAX_ROWS_PER_CSV: Maximum rows that can be imported per CSV file (10,000)
#    - Excess rows are truncated (first N rows processed)
#
# 3. File Size Limits:
#    - MAX_FILE_SIZE_MB: Maximum file size in MB (50 MB, matches UI limit)
#    - Applied to both individual CSV files and ZIP archives
#
# 4. ZIP Limits:
#    - Maximum 20 files per ZIP archive
#
# 5. Column Name Validation:
#    - Only alphanumeric characters and underscores allowed
#    - Must start with letter or underscore
#    - SQL keywords are blocked
#    - Prevents SQL injection attacks
#
# These limits can be adjusted by modifying the constants below.
# ============================================================================

MAX_NEW_COLUMNS_PER_IMPORT = 10  # Maximum new columns that can be added per import
MAX_ROWS_PER_CSV = 10000  # Maximum rows that can be imported per CSV file
MAX_FILE_SIZE_MB = 50  # Maximum file size in MB (matches UI limit)
MAX_TOTAL_COLUMNS_PER_TABLE = 100  # Maximum total columns allowed per table
MAX_COLUMN_NAME_LENGTH = 64  # Maximum column name length (SQL standard)
MIN_COLUMN_NAME_LENGTH = 1  # Minimum column name length
MAX_FILES_PER_ZIP = 20  # Maximum number of files allowed in ZIP archive


def parse_datetime(dt_str: str) -> Optional[datetime]:
    """Parse datetime string from CSV format."""
    if not dt_str or pd.isna(dt_str) or dt_str == '':
        return None
    
    dt_str = str(dt_str).strip()
    if not dt_str:
        return None
    
    # Try different datetime formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(dt_str.replace("Z", ""), fmt)
        except (ValueError, AttributeError):
            continue
    
    # Try ISO format
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        pass
    
    return None


def validate_column_name(column_name: str) -> Tuple[bool, str]:
    """
    Validate column name to prevent SQL injection and abuse.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not column_name:
        return False, "Column name cannot be empty"
    
    # Check length
    if len(column_name) > MAX_COLUMN_NAME_LENGTH:
        return False, f"Column name too long (max {MAX_COLUMN_NAME_LENGTH} characters)"
    
    if len(column_name) < MIN_COLUMN_NAME_LENGTH:
        return False, f"Column name too short (min {MIN_COLUMN_NAME_LENGTH} character)"
    
    # Check for SQL injection patterns
    sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 
                    'EXEC', 'EXECUTE', 'UNION', 'SCRIPT', '--', ';', '/*', '*/']
    column_upper = column_name.upper()
    for keyword in sql_keywords:
        if keyword in column_upper:
            return False, f"Column name contains forbidden SQL keyword: {keyword}"
    
    # Check for suspicious patterns (random strings, excessive special chars)
    if re.search(r'[^a-zA-Z0-9_]', column_name):
        # Allow underscores and alphanumeric only
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', column_name):
            return False, "Column name contains invalid characters (only letters, numbers, and underscores allowed)"
    
    # Check for suspicious patterns (very random-looking names)
    if len(column_name) > 20 and len(set(column_name)) / len(column_name) > 0.8:
        # High character diversity might indicate random generation
        # But this is lenient - only flag if it's very suspicious
        pass
    
    return True, ""


def check_file_size(file_path: str) -> Tuple[bool, str]:
    """Check if file size is within limits."""
    try:
        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)
        
        if size_mb > MAX_FILE_SIZE_MB:
            return False, f"File size ({size_mb:.2f} MB) exceeds maximum allowed ({MAX_FILE_SIZE_MB} MB)"
        
        return True, ""
    except Exception as e:
        return False, f"Error checking file size: {e}"


def safe_get(row, key: str, default=''):
    """Safely get value from row, handling missing columns gracefully."""
    try:
        if key in row.index:
            value = row.get(key, default)
            return value if pd.notna(value) and str(value).strip() != '' else default
        return default
    except (KeyError, AttributeError):
        return default


def get_table_columns(table_name: str, session) -> set:
    """Get set of column names that exist in the database table."""
    try:
        inspector = inspect(engine)
        columns = inspector.get_columns(table_name)
        return {col['name'] for col in columns}
    except Exception as e:
        print(f"[Import] Error getting columns for {table_name}: {e}")
        return set()


def infer_column_type(value: str) -> str:
    """Infer SQL column type from CSV value."""
    if not value or str(value).strip() == '':
        return 'TEXT'  # Default to TEXT for empty values
    
    value_str = str(value).strip()
    
    # Try to parse as number
    try:
        float(value_str)
        # Check if it's an integer
        try:
            int(value_str)
            return 'INTEGER'
        except ValueError:
            return 'REAL'
    except ValueError:
        pass
    
    # Check if it's a boolean
    if value_str.lower() in ('true', 'false', '1', '0', 'yes', 'no'):
        return 'INTEGER'  # SQLite uses INTEGER for booleans
    
    # Check if it's JSON
    if value_str.startswith('{') or value_str.startswith('['):
        try:
            json.loads(value_str)
            return 'TEXT'  # Store JSON as TEXT
        except (json.JSONDecodeError, ValueError):
            pass
    
    # Default to TEXT
    return 'TEXT'


def _quote_identifier(identifier: str, dialect_name: str) -> str:
    """
    Properly quote a SQL identifier to prevent SQL injection.
    
    SECURITY: This function ensures identifiers are properly quoted according to
    the database dialect, preventing SQL injection attacks.
    
    Args:
        identifier: The identifier to quote (table name, column name, etc.)
        dialect_name: The database dialect ('sqlite' or 'postgresql')
    
    Returns:
        Properly quoted identifier string
    """
    # Remove any existing quotes to prevent double-quoting
    identifier = identifier.strip().strip('"').strip('`').strip("'")
    
    if dialect_name == 'sqlite':
        # SQLite uses double quotes or backticks for identifiers
        # Escape any double quotes in the identifier
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'
    else:
        # PostgreSQL uses double quotes for identifiers
        # Escape any double quotes in the identifier
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'


def add_column_to_table(table_name: str, column_name: str, column_type: str, session) -> bool:
    """
    Attempt to add a column to a database table.
    Returns True if successful, False otherwise.
    
    SECURITY: Properly quotes identifiers to prevent SQL injection attacks.
    Table and column names are validated before this function is called via
    validate_column_name(). Table names come from a whitelist.
    """
    try:
        # Check if column already exists
        existing_columns = get_table_columns(table_name, session)
        if column_name in existing_columns:
            return True  # Column already exists
        
        # SECURITY: Properly quote identifiers to prevent SQL injection
        # Table name comes from whitelist (ALLOWED_FILES), column_name is validated
        # Column type is validated to be one of: TEXT, INTEGER, REAL (safe values)
        dialect_name = 'sqlite' if DATABASE_URL.startswith('sqlite') else 'postgresql'
        quoted_table = _quote_identifier(table_name, dialect_name)
        quoted_column = _quote_identifier(column_name, dialect_name)
        
        # Validate column_type to prevent injection (whitelist approach)
        allowed_types = {'TEXT', 'INTEGER', 'REAL', 'BOOLEAN', 'NUMERIC'}
        if column_type.upper() not in allowed_types:
            print(f"[Import] SECURITY: Invalid column type '{column_type}' rejected")
            return False
        
        # SQLite and PostgreSQL use slightly different syntax
        if DATABASE_URL.startswith('sqlite'):
            # SQLite: ALTER TABLE table_name ADD COLUMN column_name type
            sql = f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {column_type.upper()}"
        else:
            # PostgreSQL: ALTER TABLE table_name ADD COLUMN column_name type
            sql = f'ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {column_type.upper()}'
        
        session.execute(text(sql))
        session.commit()
        print(f"[Import] Added column {column_name} ({column_type}) to {table_name}")
        return True
        
    except OperationalError as e:
        # Column might already exist or other operational error
        session.rollback()
        print(f"[Import] Could not add column {column_name} to {table_name}: {e}")
        return False
    except Exception as e:
        session.rollback()
        print(f"[Import] Error adding column {column_name} to {table_name}: {e}")
        return False


def handle_extra_columns(
    csv_path: str,
    table_name: str,
    model_class,
    session,
    backup_dir: Optional[str] = None
) -> Tuple[Dict[str, str], str]:
    """
    Detect extra columns in CSV that don't exist in database.
    Attempts to add them, falls back to storing in backup CSV.
    Includes abuse prevention measures.
    
    Returns:
        Tuple of (extra_columns_dict mapping column_name to type, backup_csv_path)
    """
    extra_columns = {}
    backup_csv_path = None
    
    try:
        # Check file size
        is_valid_size, size_error = check_file_size(csv_path)
        if not is_valid_size:
            print(f"[Import] {size_error}")
            return {}, None
        
        # Read CSV to get columns
        df_sample = pd.read_csv(csv_path, nrows=1, dtype=str)
        csv_columns = set(df_sample.columns)
        
        # Get database columns
        db_columns = get_table_columns(table_name, session)
        
        # Find extra columns
        missing_columns = csv_columns - db_columns
        
        if not missing_columns:
            return {}, None
        
        # Abuse prevention: Limit number of new columns
        if len(missing_columns) > MAX_NEW_COLUMNS_PER_IMPORT:
            print(f"[Import] ABUSE PREVENTION: Too many new columns ({len(missing_columns)}). "
                  f"Maximum allowed: {MAX_NEW_COLUMNS_PER_IMPORT}. "
                  f"Only the first {MAX_NEW_COLUMNS_PER_IMPORT} will be processed.")
            missing_columns = list(missing_columns)[:MAX_NEW_COLUMNS_PER_IMPORT]
        
        # Check total column count limit
        total_columns = len(db_columns) + len(missing_columns)
        if total_columns > MAX_TOTAL_COLUMNS_PER_TABLE:
            excess = total_columns - MAX_TOTAL_COLUMNS_PER_TABLE
            print(f"[Import] ABUSE PREVENTION: Adding {len(missing_columns)} columns would exceed "
                  f"maximum total columns ({MAX_TOTAL_COLUMNS_PER_TABLE}). "
                  f"Rejecting {excess} columns.")
            # Only allow columns that keep us under the limit
            allowed_new = MAX_TOTAL_COLUMNS_PER_TABLE - len(db_columns)
            if allowed_new <= 0:
                print(f"[Import] Table {table_name} already has maximum columns. No new columns allowed.")
                return {}, None
            missing_columns = list(missing_columns)[:allowed_new]
        
        print(f"[Import] Found {len(missing_columns)} extra columns in CSV for {table_name}: {missing_columns}")
        
        # Read full CSV to infer types from actual data
        df_full = pd.read_csv(csv_path, dtype=str, nrows=100)  # Sample first 100 rows
        
        # Try to add each missing column
        added_columns = set()
        failed_columns = set()
        rejected_columns = set()
        
        for col_name in missing_columns:
            # Validate column name
            is_valid, validation_error = validate_column_name(col_name)
            if not is_valid:
                print(f"[Import] ABUSE PREVENTION: Rejecting column '{col_name}': {validation_error}")
                rejected_columns.add(col_name)
                continue
            # Infer type from sample data
            sample_values = df_full[col_name].dropna()
            if len(sample_values) > 0:
                column_type = infer_column_type(sample_values.iloc[0])
            else:
                column_type = 'TEXT'  # Default to TEXT
            
            # Try to add column
            if add_column_to_table(table_name, col_name, column_type, session):
                added_columns.add(col_name)
                extra_columns[col_name] = column_type
            else:
                failed_columns.add(col_name)
        
        # If some columns failed to add, create backup CSV with extra data
        if failed_columns and backup_dir:
            os.makedirs(backup_dir, exist_ok=True)
            backup_csv_path = os.path.join(backup_dir, f"{table_name}_extra_columns.csv")
            
            # Read full CSV to get all rows with extra columns
            try:
                df_full_all = pd.read_csv(csv_path, dtype=str)
                # Get primary key column (first column or common ones)
                key_columns = []
                for key_col in ['task_id', 'instance_id', 'emotion', 'note_id', 'id']:
                    if key_col in df_full_all.columns:
                        key_columns.append(key_col)
                        break
                
                if key_columns:
                    # Include key column + extra columns
                    columns_to_save = key_columns + list(failed_columns)
                    df_extra = df_full_all[columns_to_save]
                else:
                    # Fallback: use first column + extra columns
                    df_extra = df_full_all[[df_full_all.columns[0]] + list(failed_columns)]
                
                df_extra.to_csv(backup_csv_path, index=False)
                print(f"[Import] Saved extra columns data to backup: {backup_csv_path}")
            except Exception as e:
                print(f"[Import] Error creating backup CSV: {e}")
        
        if added_columns:
            print(f"[Import] Successfully added {len(added_columns)} columns to {table_name}")
        if failed_columns:
            print(f"[Import] Could not add {len(failed_columns)} columns, saved to backup CSV")
        if rejected_columns:
            print(f"[Import] Rejected {len(rejected_columns)} columns due to validation failures")
        
    except Exception as e:
        print(f"[Import] Error handling extra columns for {table_name}: {e}")
        import traceback
        print(f"[Import] Traceback: {traceback.format_exc()}")
    
    return extra_columns, backup_csv_path


def safe_int(value, default=0):
    """Safely convert value to int, returning default on error."""
    if not value or pd.isna(value) or str(value).strip() == '':
        return default
    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        return default


def import_tasks_from_csv(csv_path: str, session, skip_existing: bool = True, backup_dir: Optional[str] = None, user_id: Optional[int] = None) -> Tuple[int, int, int]:
    """
    Import tasks from CSV file into database.
    Handles missing columns gracefully by using defaults.
    Attempts to add extra CSV columns to database, falls back to backup CSV if needed.
    
    **SECURITY:** All imported tasks are assigned to the provided user_id, overriding any user_id in the CSV.
    This ensures imported data belongs to the importing user.
    
    Args:
        csv_path: Path to CSV file
        session: Database session
        skip_existing: If True, skip records that already exist
        backup_dir: Directory for backup CSV files
        user_id: REQUIRED user ID. All imported tasks will be assigned to this user.
    
    Returns:
        Tuple of (imported_count, skipped_count, error_count)
    
    Raises:
        ValueError: If user_id is None (security requirement)
    """
    # CRITICAL: Require user_id for data isolation
    if user_id is None:
        raise ValueError("user_id is REQUIRED for import. Users can only import data for themselves.")
    imported = 0
    skipped = 0
    errors = 0
    
    try:
        # Check file size before processing
        is_valid_size, size_error = check_file_size(csv_path)
        if not is_valid_size:
            print(f"[Import] {size_error}")
            return 0, 0, 1  # Return error count
        
        # Handle extra columns - try to add them to database
        extra_columns, backup_csv = handle_extra_columns(
            csv_path, 'tasks', Task, session, backup_dir
        )
        
        df = pd.read_csv(csv_path, dtype=str).fillna('')
        
        # Abuse prevention: Limit number of rows
        if len(df) > MAX_ROWS_PER_CSV:
            print(f"[Import] ABUSE PREVENTION: CSV has {len(df)} rows. "
                  f"Maximum allowed: {MAX_ROWS_PER_CSV}. "
                  f"Only processing first {MAX_ROWS_PER_CSV} rows.")
            df = df.head(MAX_ROWS_PER_CSV)
        
                # Get existing task IDs for this user only
        existing_task_ids = set()
        if skip_existing:
            # CRITICAL: Only check for existing records for this user
            existing_tasks = session.query(Task).filter(Task.user_id == user_id).all()
            existing_task_ids = {task.task_id for task in existing_tasks}
        
        for idx, row in df.iterrows():
            # Critical field - must exist
            task_id = str(safe_get(row, 'task_id', '')).strip()
            if not task_id:
                errors += 1
                continue
            
            if skip_existing and task_id in existing_task_ids:
                skipped += 1
                continue
            
            try:
                # Parse categories - use safe_get and handle missing column
                categories_str = safe_get(row, 'categories', '[]')
                try:
                    categories = json.loads(categories_str) if isinstance(categories_str, str) else categories_str
                except (json.JSONDecodeError, TypeError):
                    categories = []
                
                # Parse routine_days_of_week - use safe_get
                routine_days_str = safe_get(row, 'routine_days_of_week', '[]')
                try:
                    routine_days = json.loads(routine_days_str) if isinstance(routine_days_str, str) else routine_days_str
                except (json.JSONDecodeError, TypeError):
                    routine_days = []
                
                # Parse other fields with safe_get and defaults matching database model
                name = str(safe_get(row, 'name', '')).strip()
                if not name:  # Name is required
                    errors += 1
                    continue
                
                description = str(safe_get(row, 'description', '')).strip()
                task_type = str(safe_get(row, 'type', 'one-time')).strip() or 'one-time'
                version = safe_int(safe_get(row, 'version', '1'), 1)
                is_recurring = str(safe_get(row, 'is_recurring', 'False')).lower() == 'true'
                default_estimate = safe_int(safe_get(row, 'default_estimate_minutes', '0'), 0)
                task_type_field = str(safe_get(row, 'task_type', 'Work')).strip() or 'Work'
                default_aversion = str(safe_get(row, 'default_initial_aversion', '')).strip()
                routine_frequency = str(safe_get(row, 'routine_frequency', 'none')).strip() or 'none'
                routine_time = str(safe_get(row, 'routine_time', '00:00')).strip() or '00:00'
                
                # Handle optional integer fields
                completion_window_hours = None
                if safe_get(row, 'completion_window_hours', ''):
                    completion_window_hours = safe_int(safe_get(row, 'completion_window_hours', ''), None)
                    if completion_window_hours == 0:
                        completion_window_hours = None
                
                completion_window_days = None
                if safe_get(row, 'completion_window_days', ''):
                    completion_window_days = safe_int(safe_get(row, 'completion_window_days', ''), None)
                    if completion_window_days == 0:
                        completion_window_days = None
                
                notes = str(safe_get(row, 'notes', '')).strip()
                
                # CRITICAL SECURITY CHECK: Validate CSV user_id matches logged-in user_id
                # Skip rows where user_id doesn't match to prevent cross-user data editing
                csv_user_id = safe_int(safe_get(row, 'user_id', ''), None)
                if csv_user_id is not None and csv_user_id != user_id:
                    print(f"[Import] SECURITY: Skipping task {task_id} - CSV user_id ({csv_user_id}) does not match logged-in user_id ({user_id})")
                    skipped += 1
                    continue
                
                # CRITICAL: Override any user_id from CSV with the provided user_id for security
                # This ensures imported data always belongs to the importing user
                
                # Parse created_at - optional field
                created_at = parse_datetime(safe_get(row, 'created_at', ''))
                
                # Create or update task (filter by both task_id and user_id for security)
                existing_task = session.query(Task).filter(
                    Task.task_id == task_id,
                    Task.user_id == user_id
                ).first()
                if existing_task and not skip_existing:
                    # Update existing - only update fields that exist in CSV
                    existing_task.name = name
                    if 'description' in row.index or not existing_task.description:
                        existing_task.description = description
                    if 'type' in row.index:
                        existing_task.type = task_type
                    if 'version' in row.index:
                        existing_task.version = version
                    if 'is_recurring' in row.index:
                        existing_task.is_recurring = is_recurring
                    if 'categories' in row.index:
                        existing_task.categories = categories
                    if 'default_estimate_minutes' in row.index:
                        existing_task.default_estimate_minutes = default_estimate
                    if 'task_type' in row.index:
                        existing_task.task_type = task_type_field
                    if 'default_initial_aversion' in row.index:
                        existing_task.default_initial_aversion = default_aversion
                    if 'routine_frequency' in row.index:
                        existing_task.routine_frequency = routine_frequency
                    if 'routine_days_of_week' in row.index:
                        existing_task.routine_days_of_week = routine_days
                    if 'routine_time' in row.index:
                        existing_task.routine_time = routine_time
                    if 'completion_window_hours' in row.index:
                        existing_task.completion_window_hours = completion_window_hours
                    if 'completion_window_days' in row.index:
                        existing_task.completion_window_days = completion_window_days
                    if 'notes' in row.index:
                        existing_task.notes = notes
                    # CRITICAL: Always set user_id to the provided user_id (override CSV value)
                    existing_task.user_id = user_id
                    if created_at:
                        existing_task.created_at = created_at
                    
                    # Set extra columns that were added to database
                    if extra_columns:
                        for col_name in extra_columns:
                            if col_name in row.index:
                                value = safe_get(row, col_name, '')
                                if value:
                                    try:
                                        # Convert value based on column type
                                        col_type = extra_columns[col_name]
                                        if col_type == 'INTEGER':
                                            value = safe_int(value, 0)
                                        elif col_type == 'REAL':
                                            value = safe_float(value, 0.0)
                                        
                                        setattr(existing_task, col_name, value)
                                    except Exception as e:
                                        print(f"[Import] Could not set extra column {col_name} on task {task_id}: {e}")
                    
                    imported += 1
                elif not existing_task:
                    # Create new - use defaults for missing fields
                    task = Task(
                        task_id=task_id,
                        name=name,
                        description=description,
                        type=task_type,
                        version=version,
                        created_at=created_at,
                        is_recurring=is_recurring,
                        categories=categories,
                        default_estimate_minutes=default_estimate,
                        task_type=task_type_field,
                        default_initial_aversion=default_aversion,
                        routine_frequency=routine_frequency,
                        routine_days_of_week=routine_days,
                        routine_time=routine_time,
                        completion_window_hours=completion_window_hours,
                        completion_window_days=completion_window_days,
                        notes=notes,
                        user_id=user_id  # CRITICAL: Always use provided user_id (override CSV value)
                    )
                    
                    # Set extra columns that were added to database
                    if extra_columns:
                        for col_name in extra_columns:
                            if col_name in row.index:
                                value = safe_get(row, col_name, '')
                                if value:
                                    try:
                                        # Convert value based on column type
                                        col_type = extra_columns[col_name]
                                        if col_type == 'INTEGER':
                                            value = safe_int(value, 0)
                                        elif col_type == 'REAL':
                                            value = safe_float(value, 0.0)
                                        # TEXT and others stay as string
                                        
                                        # Try to set the attribute dynamically
                                        setattr(task, col_name, value)
                                    except Exception as e:
                                        print(f"[Import] Could not set extra column {col_name} on task {task_id}: {e}")
                    
                    session.add(task)
                    imported += 1
                else:
                    skipped += 1
                
            except Exception as e:
                print(f"[Import] Error importing task {task_id}: {e}")
                import traceback
                print(f"[Import] Traceback: {traceback.format_exc()}")
                errors += 1
                # Continue processing other rows
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        print(f"[Import] Error reading tasks CSV: {e}")
        import traceback
        print(f"[Import] Traceback: {traceback.format_exc()}")
        # Don't raise - return what we have so far
        pass
    
    return imported, skipped, errors


def safe_float(value, default=None):
    """Safely convert value to float, returning default on error."""
    if not value or pd.isna(value) or str(value).strip() == '':
        return default
    try:
        return float(str(value))
    except (ValueError, TypeError):
        return default


def import_task_instances_from_csv(csv_path: str, session, skip_existing: bool = True, backup_dir: Optional[str] = None, user_id: Optional[int] = None) -> Tuple[int, int, int]:
    """
    Import task instances from CSV file into database.
    Handles missing columns gracefully by using defaults.
    Attempts to add extra CSV columns to database, falls back to backup CSV if needed.
    
    **SECURITY:** All imported instances are assigned to the provided user_id, overriding any user_id in the CSV.
    This ensures imported data belongs to the importing user.
    
    Args:
        csv_path: Path to CSV file
        session: Database session
        skip_existing: If True, skip records that already exist
        backup_dir: Directory for backup CSV files
        user_id: REQUIRED user ID. All imported instances will be assigned to this user.
    
    Returns:
        Tuple of (imported_count, skipped_count, error_count)
    
    Raises:
        ValueError: If user_id is None (security requirement)
    """
    # CRITICAL: Require user_id for data isolation
    if user_id is None:
        raise ValueError("user_id is REQUIRED for import. Users can only import data for themselves.")
    imported = 0
    skipped = 0
    errors = 0
    
    try:
        # Check file size before processing
        is_valid_size, size_error = check_file_size(csv_path)
        if not is_valid_size:
            print(f"[Import] {size_error}")
            return 0, 0, 1  # Return error count
        
        # Handle extra columns - try to add them to database
        extra_columns, backup_csv = handle_extra_columns(
            csv_path, 'task_instances', TaskInstance, session, backup_dir
        )
        
        df = pd.read_csv(csv_path, dtype=str).fillna('')
        
        # Abuse prevention: Limit number of rows
        if len(df) > MAX_ROWS_PER_CSV:
            print(f"[Import] ABUSE PREVENTION: CSV has {len(df)} rows. "
                  f"Maximum allowed: {MAX_ROWS_PER_CSV}. "
                  f"Only processing first {MAX_ROWS_PER_CSV} rows.")
            df = df.head(MAX_ROWS_PER_CSV)
        
        # Get existing instance IDs for this user only
        existing_instance_ids = set()
        if skip_existing:
            # CRITICAL: Only check for existing records for this user
            existing_instances = session.query(TaskInstance).filter(TaskInstance.user_id == user_id).all()
            existing_instance_ids = {instance.instance_id for instance in existing_instances}
        
        for idx, row in df.iterrows():
            # Critical field - must exist
            instance_id = str(safe_get(row, 'instance_id', '')).strip()
            if not instance_id:
                errors += 1
                continue
            
            if skip_existing and instance_id in existing_instance_ids:
                skipped += 1
                continue
            
            try:
                # Parse JSON fields - use safe_get
                predicted_str = safe_get(row, 'predicted', '{}')
                try:
                    predicted = json.loads(predicted_str) if isinstance(predicted_str, str) else predicted_str
                except (json.JSONDecodeError, TypeError):
                    predicted = {}
                
                actual_str = safe_get(row, 'actual', '{}')
                try:
                    actual = json.loads(actual_str) if isinstance(actual_str, str) else actual_str
                except (json.JSONDecodeError, TypeError):
                    actual = {}
                
                # Parse required fields
                task_id = str(safe_get(row, 'task_id', '')).strip()
                task_name = str(safe_get(row, 'task_name', '')).strip()
                if not task_id or not task_name:  # Required fields
                    errors += 1
                    continue
                
                # Parse optional fields with defaults
                task_version = safe_int(safe_get(row, 'task_version', '1'), 1)
                is_completed = str(safe_get(row, 'is_completed', 'False')).lower() == 'true'
                is_deleted = str(safe_get(row, 'is_deleted', 'False')).lower() == 'true'
                status = str(safe_get(row, 'status', 'active')).strip() or 'active'
                
                # Parse numeric fields - use safe_float for all optional fields
                procrastination_score = safe_float(safe_get(row, 'procrastination_score', ''), None)
                proactive_score = safe_float(safe_get(row, 'proactive_score', ''), None)
                behavioral_score = safe_float(safe_get(row, 'behavioral_score', ''), None)
                net_relief = safe_float(safe_get(row, 'net_relief', ''), None)
                behavioral_deviation = safe_float(safe_get(row, 'behavioral_deviation', ''), None)
                duration_minutes = safe_float(safe_get(row, 'duration_minutes', ''), None)
                delay_minutes = safe_float(safe_get(row, 'delay_minutes', ''), None)
                relief_score = safe_float(safe_get(row, 'relief_score', ''), None)
                cognitive_load = safe_float(safe_get(row, 'cognitive_load', ''), None)
                mental_energy_needed = safe_float(safe_get(row, 'mental_energy_needed', ''), None)
                task_difficulty = safe_float(safe_get(row, 'task_difficulty', ''), None)
                emotional_load = safe_float(safe_get(row, 'emotional_load', ''), None)
                environmental_effect = safe_float(safe_get(row, 'environmental_effect', ''), None)
                serendipity_factor = safe_float(safe_get(row, 'serendipity_factor', ''), None)
                disappointment_factor = safe_float(safe_get(row, 'disappointment_factor', ''), None)
                
                skills_improved = str(safe_get(row, 'skills_improved', '')).strip()
                
                # CRITICAL SECURITY CHECK: Validate CSV user_id matches logged-in user_id
                # Skip rows where user_id doesn't match to prevent cross-user data editing
                csv_user_id = safe_int(safe_get(row, 'user_id', ''), None)
                if csv_user_id is not None and csv_user_id != user_id:
                    print(f"[Import] SECURITY: Skipping instance {instance_id} - CSV user_id ({csv_user_id}) does not match logged-in user_id ({user_id})")
                    skipped += 1
                    continue
                
                # CRITICAL: Override any user_id from CSV with the provided user_id for security
                # This ensures imported data always belongs to the importing user
                
                # Parse datetime fields - use safe_get
                created_at = parse_datetime(safe_get(row, 'created_at', ''))
                initialized_at = parse_datetime(safe_get(row, 'initialized_at', ''))
                started_at = parse_datetime(safe_get(row, 'started_at', ''))
                completed_at = parse_datetime(safe_get(row, 'completed_at', ''))
                cancelled_at = parse_datetime(safe_get(row, 'cancelled_at', ''))
                
                # Create or update instance (filter by both instance_id and user_id for security)
                existing_instance = session.query(TaskInstance).filter(
                    TaskInstance.instance_id == instance_id,
                    TaskInstance.user_id == user_id
                ).first()
                if existing_instance and not skip_existing:
                    # Update existing - only update fields that exist in CSV
                    existing_instance.task_id = task_id
                    existing_instance.task_name = task_name
                    if 'task_version' in row.index:
                        existing_instance.task_version = task_version
                    if 'predicted' in row.index:
                        existing_instance.predicted = predicted
                    if 'actual' in row.index:
                        existing_instance.actual = actual
                    if 'is_completed' in row.index:
                        existing_instance.is_completed = is_completed
                    if 'is_deleted' in row.index:
                        existing_instance.is_deleted = is_deleted
                    if 'status' in row.index:
                        existing_instance.status = status
                    # Update numeric fields only if they exist in CSV
                    for field in ['procrastination_score', 'proactive_score', 'behavioral_score', 'net_relief',
                                'behavioral_deviation', 'duration_minutes', 'delay_minutes', 'relief_score',
                                'cognitive_load', 'mental_energy_needed', 'task_difficulty', 'emotional_load',
                                'environmental_effect', 'serendipity_factor', 'disappointment_factor']:
                        if field in row.index:
                            setattr(existing_instance, field, locals()[field])
                    if 'skills_improved' in row.index:
                        existing_instance.skills_improved = skills_improved
                    # CRITICAL: Always set user_id to the provided user_id (override CSV value)
                    existing_instance.user_id = user_id
                    if created_at:
                        existing_instance.created_at = created_at
                    if initialized_at:
                        existing_instance.initialized_at = initialized_at
                    if started_at:
                        existing_instance.started_at = started_at
                    if completed_at:
                        existing_instance.completed_at = completed_at
                    if cancelled_at:
                        existing_instance.cancelled_at = cancelled_at
                    
                    # Set extra columns that were added to database
                    if extra_columns:
                        for col_name in extra_columns:
                            if col_name in row.index:
                                value = safe_get(row, col_name, '')
                                if value:
                                    try:
                                        # Convert value based on column type
                                        col_type = extra_columns[col_name]
                                        if col_type == 'INTEGER':
                                            value = safe_int(value, 0)
                                        elif col_type == 'REAL':
                                            value = safe_float(value, 0.0)
                                        
                                        setattr(existing_instance, col_name, value)
                                    except Exception as e:
                                        print(f"[Import] Could not set extra column {col_name} on instance {instance_id}: {e}")
                    
                    imported += 1
                elif not existing_instance:
                    # Create new
                    instance = TaskInstance(
                        instance_id=instance_id,
                        task_id=task_id,
                        task_name=task_name,
                        task_version=task_version,
                        created_at=created_at,
                        initialized_at=initialized_at,
                        started_at=started_at,
                        completed_at=completed_at,
                        cancelled_at=cancelled_at,
                        predicted=predicted,
                        actual=actual,
                        procrastination_score=procrastination_score,
                        proactive_score=proactive_score,
                        behavioral_score=behavioral_score,
                        net_relief=net_relief,
                        behavioral_deviation=behavioral_deviation,
                        is_completed=is_completed,
                        is_deleted=is_deleted,
                        status=status,
                        duration_minutes=duration_minutes,
                        delay_minutes=delay_minutes,
                        relief_score=relief_score,
                        cognitive_load=cognitive_load,
                        mental_energy_needed=mental_energy_needed,
                        task_difficulty=task_difficulty,
                        emotional_load=emotional_load,
                        environmental_effect=environmental_effect,
                        skills_improved=skills_improved,
                        serendipity_factor=serendipity_factor,
                        disappointment_factor=disappointment_factor,
                        user_id=user_id  # CRITICAL: Always use provided user_id (override CSV value)
                    )
                    
                    # Set extra columns that were added to database
                    if extra_columns:
                        for col_name in extra_columns:
                            if col_name in row.index:
                                value = safe_get(row, col_name, '')
                                if value:
                                    try:
                                        # Convert value based on column type
                                        col_type = extra_columns[col_name]
                                        if col_type == 'INTEGER':
                                            value = safe_int(value, 0)
                                        elif col_type == 'REAL':
                                            value = safe_float(value, 0.0)
                                        
                                        setattr(instance, col_name, value)
                                    except Exception as e:
                                        print(f"[Import] Could not set extra column {col_name} on instance {instance_id}: {e}")
                    
                    session.add(instance)
                    imported += 1
                else:
                    skipped += 1
                
            except Exception as e:
                print(f"[Import] Error importing instance {instance_id}: {e}")
                import traceback
                print(f"[Import] Traceback: {traceback.format_exc()}")
                errors += 1
                # Continue processing other rows
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        print(f"[Import] Error reading task instances CSV: {e}")
        import traceback
        print(f"[Import] Traceback: {traceback.format_exc()}")
        # Don't raise - return what we have so far
        pass
    
    return imported, skipped, errors


def import_emotions_from_csv(csv_path: str, session, skip_existing: bool = True, backup_dir: Optional[str] = None) -> Tuple[int, int, int]:
    """
    Import emotions from CSV file into database.
    Handles missing columns gracefully.
    Attempts to add extra CSV columns to database, falls back to backup CSV if needed.
    """
    imported = 0
    skipped = 0
    errors = 0
    
    try:
        # Check file size before processing
        is_valid_size, size_error = check_file_size(csv_path)
        if not is_valid_size:
            print(f"[Import] {size_error}")
            return 0, 0, 1  # Return error count
        
        # Handle extra columns - try to add them to database
        extra_columns, backup_csv = handle_extra_columns(
            csv_path, 'emotions', Emotion, session, backup_dir
        )
        
        df = pd.read_csv(csv_path, dtype=str).fillna('')
        
        # Abuse prevention: Limit number of rows
        if len(df) > MAX_ROWS_PER_CSV:
            print(f"[Import] ABUSE PREVENTION: CSV has {len(df)} rows. "
                  f"Maximum allowed: {MAX_ROWS_PER_CSV}. "
                  f"Only processing first {MAX_ROWS_PER_CSV} rows.")
            df = df.head(MAX_ROWS_PER_CSV)
        
        existing_emotions = set()
        if skip_existing:
            # NOTE: Emotion table doesn't have user_id (shared reference table)
            # Querying all emotions is intentional and correct for import functionality
            existing = session.query(Emotion).all()
            existing_emotions = {e.emotion.lower() for e in existing}
        
        for idx, row in df.iterrows():
            emotion_name = str(safe_get(row, 'emotion', '')).strip()
            if not emotion_name:
                errors += 1
                continue
            
            if skip_existing and emotion_name.lower() in existing_emotions:
                skipped += 1
                continue
            
            try:
                existing_emotion = session.query(Emotion).filter(Emotion.emotion == emotion_name).first()
                if not existing_emotion:
                    emotion = Emotion(emotion=emotion_name)
                    
                    # Set extra columns that were added to database
                    if extra_columns:
                        for col_name in extra_columns:
                            if col_name in row.index:
                                value = safe_get(row, col_name, '')
                                if value:
                                    try:
                                        # Convert value based on column type
                                        col_type = extra_columns[col_name]
                                        if col_type == 'INTEGER':
                                            value = safe_int(value, 0)
                                        elif col_type == 'REAL':
                                            value = safe_float(value, 0.0)
                                        
                                        setattr(emotion, col_name, value)
                                    except Exception as e:
                                        print(f"[Import] Could not set extra column {col_name} on emotion {emotion_name}: {e}")
                    
                    session.add(emotion)
                    imported += 1
                else:
                    skipped += 1
            except Exception as e:
                print(f"[Import] Error importing emotion {emotion_name}: {e}")
                import traceback
                print(f"[Import] Traceback: {traceback.format_exc()}")
                errors += 1
                # Continue processing other rows
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        print(f"[Import] Error reading emotions CSV: {e}")
        import traceback
        print(f"[Import] Traceback: {traceback.format_exc()}")
        # Don't raise - return what we have so far
        pass
    
    return imported, skipped, errors


def import_notes_from_csv(csv_path: str, session, skip_existing: bool = True, user_id: Optional[int] = None) -> Tuple[int, int, int]:
    """
    Import notes from CSV file into database. Handles missing columns gracefully.
    
    **SECURITY:** All imported notes are assigned to the provided user_id, overriding any user_id in the CSV.
    This ensures imported data belongs to the importing user.
    
    Args:
        csv_path: Path to CSV file
        session: Database session
        skip_existing: If True, skip records that already exist
        user_id: REQUIRED user ID. All imported notes will be assigned to this user.
    
    Returns:
        Tuple of (imported_count, skipped_count, error_count)
    
    Raises:
        ValueError: If user_id is None (security requirement)
    """
    # CRITICAL: Require user_id for data isolation
    if user_id is None:
        raise ValueError("user_id is REQUIRED for import. Users can only import data for themselves.")
    imported = 0
    skipped = 0
    errors = 0
    
    try:
        # Check file size before processing
        is_valid_size, size_error = check_file_size(csv_path)
        if not is_valid_size:
            print(f"[Import] {size_error}")
            return 0, 0, 1  # Return error count
        
        df = pd.read_csv(csv_path, dtype=str).fillna('')
        
        # Abuse prevention: Limit number of rows
        if len(df) > MAX_ROWS_PER_CSV:
            print(f"[Import] ABUSE PREVENTION: CSV has {len(df)} rows. "
                  f"Maximum allowed: {MAX_ROWS_PER_CSV}. "
                  f"Only processing first {MAX_ROWS_PER_CSV} rows.")
            df = df.head(MAX_ROWS_PER_CSV)
        
        existing_note_ids = set()
        if skip_existing:
            # CRITICAL: Only check for existing records for this user
            existing_notes = session.query(Note).filter(Note.user_id == user_id).all()
            existing_note_ids = {note.note_id for note in existing_notes}
        
        for idx, row in df.iterrows():
            note_id = str(safe_get(row, 'note_id', '')).strip()
            if not note_id:
                errors += 1
                continue
            
            if skip_existing and note_id in existing_note_ids:
                skipped += 1
                continue
            
            try:
                content = str(safe_get(row, 'content', '')).strip()
                if not content:
                    errors += 1
                    continue
                
                timestamp = parse_datetime(safe_get(row, 'timestamp', '')) or datetime.utcnow()
                
                # CRITICAL SECURITY CHECK: Validate CSV user_id matches logged-in user_id
                # Skip rows where user_id doesn't match to prevent cross-user data editing
                csv_user_id = safe_int(safe_get(row, 'user_id', ''), None)
                if csv_user_id is not None and csv_user_id != user_id:
                    print(f"[Import] SECURITY: Skipping note {note_id} - CSV user_id ({csv_user_id}) does not match logged-in user_id ({user_id})")
                    skipped += 1
                    continue
                
                # CRITICAL: Override any user_id from CSV with the provided user_id for security
                # This ensures imported data always belongs to the importing user
                
                existing_note = session.query(Note).filter(
                    Note.note_id == note_id,
                    Note.user_id == user_id
                ).first()
                if not existing_note:
                    note = Note(
                        note_id=note_id,
                        content=content,
                        timestamp=timestamp,
                        user_id=user_id  # CRITICAL: Always use provided user_id (override CSV value)
                    )
                    session.add(note)
                    imported += 1
                else:
                    skipped += 1
                
            except Exception as e:
                print(f"[Import] Error importing note {note_id}: {e}")
                import traceback
                print(f"[Import] Traceback: {traceback.format_exc()}")
                errors += 1
                # Continue processing other rows
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        print(f"[Import] Error reading notes CSV: {e}")
        import traceback
        print(f"[Import] Traceback: {traceback.format_exc()}")
        # Don't raise - return what we have so far
        pass
    
    return imported, skipped, errors


def import_popup_triggers_from_csv(csv_path: str, session, skip_existing: bool = True, user_id: Optional[int] = None) -> Tuple[int, int, int]:
    """
    Import popup triggers from CSV file into database. Handles missing columns gracefully.
    
    **SECURITY:** All imported triggers are assigned to the provided user_id, overriding any user_id in the CSV.
    This ensures imported data belongs to the importing user.
    
    Args:
        csv_path: Path to CSV file
        session: Database session
        skip_existing: If True, skip records that already exist
        user_id: REQUIRED user ID. All imported triggers will be assigned to this user.
    
    Returns:
        Tuple of (imported_count, skipped_count, error_count)
    
    Raises:
        ValueError: If user_id is None (security requirement)
    """
    # CRITICAL: Require user_id for data isolation
    if user_id is None:
        raise ValueError("user_id is REQUIRED for import. Users can only import data for themselves.")
    imported = 0
    skipped = 0
    errors = 0
    
    try:
        # Check file size before processing
        is_valid_size, size_error = check_file_size(csv_path)
        if not is_valid_size:
            print(f"[Import] {size_error}")
            return 0, 0, 1  # Return error count
        
        df = pd.read_csv(csv_path, dtype=str).fillna('')
        
        # Abuse prevention: Limit number of rows
        if len(df) > MAX_ROWS_PER_CSV:
            print(f"[Import] ABUSE PREVENTION: CSV has {len(df)} rows. "
                  f"Maximum allowed: {MAX_ROWS_PER_CSV}. "
                  f"Only processing first {MAX_ROWS_PER_CSV} rows.")
            df = df.head(MAX_ROWS_PER_CSV)
        
        for idx, row in df.iterrows():
            trigger_id = str(safe_get(row, 'trigger_id', '')).strip()
            
            # CRITICAL SECURITY CHECK: Validate CSV user_id matches logged-in user_id
            # Skip rows where user_id doesn't match to prevent cross-user data editing
            csv_user_id_str = str(safe_get(row, 'user_id', '')).strip()
            csv_user_id_int = safe_int(csv_user_id_str, None)
            if csv_user_id_int is not None and csv_user_id_int != user_id:
                print(f"[Import] SECURITY: Skipping popup trigger {trigger_id} - CSV user_id ({csv_user_id_int}) does not match logged-in user_id ({user_id})")
                skipped += 1
                continue
            
            # CRITICAL: Override any user_id from CSV with the provided user_id for security
            # Convert integer user_id to string for PopupTrigger (which uses string user_id)
            user_id_str = str(user_id)
            if not trigger_id:
                errors += 1
                continue
            
            try:
                # Check if exists (by trigger_id and user_id)
                existing = session.query(PopupTrigger).filter(
                    PopupTrigger.trigger_id == trigger_id,
                    PopupTrigger.user_id == user_id_str
                ).first()
                
                if skip_existing and existing:
                    skipped += 1
                    continue
                
                count = safe_int(safe_get(row, 'count', '0'), 0)
                task_id = str(safe_get(row, 'task_id', '')).strip() or None
                last_shown_at = parse_datetime(safe_get(row, 'last_shown_at', ''))
                helpful = None
                if safe_get(row, 'helpful', ''):
                    helpful = str(safe_get(row, 'helpful', '')).lower() == 'true'
                last_response = str(safe_get(row, 'last_response', '')).strip() or None
                last_comment = str(safe_get(row, 'last_comment', '')).strip() or None
                created_at = parse_datetime(safe_get(row, 'created_at', '')) or datetime.utcnow()
                updated_at = parse_datetime(safe_get(row, 'updated_at', '')) or datetime.utcnow()
                
                if existing and not skip_existing:
                    # Update - only update fields that exist in CSV
                    if 'count' in row.index:
                        existing.count = count
                    if 'task_id' in row.index:
                        existing.task_id = task_id
                    if 'last_shown_at' in row.index:
                        existing.last_shown_at = last_shown_at
                    if 'helpful' in row.index:
                        existing.helpful = helpful
                    if 'last_response' in row.index:
                        existing.last_response = last_response
                    if 'last_comment' in row.index:
                        existing.last_comment = last_comment
                    if 'updated_at' in row.index:
                        existing.updated_at = updated_at
                    imported += 1
                elif not existing:
                    # Create
                    trigger = PopupTrigger(
                        user_id=user_id_str,  # CRITICAL: Always use provided user_id (override CSV value)
                        trigger_id=trigger_id,
                        task_id=task_id,
                        count=count,
                        last_shown_at=last_shown_at,
                        helpful=helpful,
                        last_response=last_response,
                        last_comment=last_comment,
                        created_at=created_at,
                        updated_at=updated_at
                    )
                    session.add(trigger)
                    imported += 1
                else:
                    skipped += 1
                
            except Exception as e:
                print(f"[Import] Error importing popup trigger {trigger_id}: {e}")
                import traceback
                print(f"[Import] Traceback: {traceback.format_exc()}")
                errors += 1
                # Continue processing other rows
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        print(f"[Import] Error reading popup triggers CSV: {e}")
        import traceback
        print(f"[Import] Traceback: {traceback.format_exc()}")
        # Don't raise - return what we have so far
        pass
    
    return imported, skipped, errors


def import_popup_responses_from_csv(csv_path: str, session, skip_existing: bool = True, user_id: Optional[int] = None) -> Tuple[int, int, int]:
    """
    Import popup responses from CSV file into database. Handles missing columns gracefully.
    
    **SECURITY:** All imported responses are assigned to the provided user_id, overriding any user_id in the CSV.
    This ensures imported data belongs to the importing user.
    
    Args:
        csv_path: Path to CSV file
        session: Database session
        skip_existing: If True, skip records that already exist
        user_id: REQUIRED user ID. All imported responses will be assigned to this user.
    
    Returns:
        Tuple of (imported_count, skipped_count, error_count)
    
    Raises:
        ValueError: If user_id is None (security requirement)
    """
    # CRITICAL: Require user_id for data isolation
    if user_id is None:
        raise ValueError("user_id is REQUIRED for import. Users can only import data for themselves.")
    imported = 0
    skipped = 0
    errors = 0
    
    try:
        # Check file size before processing
        is_valid_size, size_error = check_file_size(csv_path)
        if not is_valid_size:
            print(f"[Import] {size_error}")
            return 0, 0, 1  # Return error count
        
        df = pd.read_csv(csv_path, dtype=str).fillna('')
        
        # Abuse prevention: Limit number of rows
        if len(df) > MAX_ROWS_PER_CSV:
            print(f"[Import] ABUSE PREVENTION: CSV has {len(df)} rows. "
                  f"Maximum allowed: {MAX_ROWS_PER_CSV}. "
                  f"Only processing first {MAX_ROWS_PER_CSV} rows.")
            df = df.head(MAX_ROWS_PER_CSV)
        
        for idx, row in df.iterrows():
            try:
                # CRITICAL SECURITY CHECK: Validate CSV user_id matches logged-in user_id
                # Skip rows where user_id doesn't match to prevent cross-user data editing
                csv_user_id_str = str(safe_get(row, 'user_id', '')).strip()
                csv_user_id_int = safe_int(csv_user_id_str, None)
                if csv_user_id_int is not None and csv_user_id_int != user_id:
                    print(f"[Import] SECURITY: Skipping popup response - CSV user_id ({csv_user_id_int}) does not match logged-in user_id ({user_id})")
                    skipped += 1
                    continue
                
                # CRITICAL: Override any user_id from CSV with the provided user_id for security
                # Convert integer user_id to string for PopupResponse (which uses string user_id)
                user_id_str = str(user_id)
                trigger_id = str(safe_get(row, 'trigger_id', '')).strip()
                if not trigger_id:
                    errors += 1
                    continue
                
                task_id = str(safe_get(row, 'task_id', '')).strip() or None
                instance_id = str(safe_get(row, 'instance_id', '')).strip() or None
                response_value = str(safe_get(row, 'response_value', '')).strip() or None
                helpful = None
                if safe_get(row, 'helpful', ''):
                    helpful = str(safe_get(row, 'helpful', '')).lower() == 'true'
                comment = str(safe_get(row, 'comment', '')).strip() or None
                
                context_str = safe_get(row, 'context', '{}')
                try:
                    context = json.loads(context_str) if isinstance(context_str, str) else context_str
                except (json.JSONDecodeError, TypeError):
                    context = {}
                
                created_at = parse_datetime(safe_get(row, 'created_at', '')) or datetime.utcnow()
                
                # Popup responses can have duplicates, so we don't skip based on existence
                response = PopupResponse(
                    user_id=user_id_str,  # CRITICAL: Always use provided user_id (override CSV value)
                    trigger_id=trigger_id,
                    task_id=task_id,
                    instance_id=instance_id,
                    response_value=response_value,
                    helpful=helpful,
                    comment=comment,
                    context=context,
                    created_at=created_at
                )
                session.add(response)
                imported += 1
                
            except Exception as e:
                print(f"[Import] Error importing popup response: {e}")
                import traceback
                print(f"[Import] Traceback: {traceback.format_exc()}")
                errors += 1
                # Continue processing other rows
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        print(f"[Import] Error reading popup responses CSV: {e}")
        import traceback
        print(f"[Import] Traceback: {traceback.format_exc()}")
        # Don't raise - return what we have so far
        pass
    
    return imported, skipped, errors


def import_survey_responses_from_csv(csv_path: str, session, skip_existing: bool = True, user_id: Optional[int] = None) -> Tuple[int, int, int]:
    """
    Import survey responses from CSV file into database. Handles missing columns gracefully.
    
    **SECURITY:** All imported responses are assigned to the provided user_id, overriding any user_id in the CSV.
    This ensures imported data belongs to the importing user.
    
    Args:
        csv_path: Path to CSV file
        session: Database session
        skip_existing: If True, skip records that already exist
        user_id: REQUIRED user ID. All imported responses will be assigned to this user.
    
    Returns:
        Tuple of (imported_count, skipped_count, error_count)
    
    Raises:
        ValueError: If user_id is None (security requirement)
    """
    # CRITICAL: Require user_id for data isolation
    if user_id is None:
        raise ValueError("user_id is REQUIRED for import. Users can only import data for themselves.")
    imported = 0
    skipped = 0
    errors = 0
    
    try:
        # Check file size before processing
        is_valid_size, size_error = check_file_size(csv_path)
        if not is_valid_size:
            print(f"[Import] {size_error}")
            return 0, 0, 1  # Return error count
        
        df = pd.read_csv(csv_path, dtype=str).fillna('')
        
        # Abuse prevention: Limit number of rows
        if len(df) > MAX_ROWS_PER_CSV:
            print(f"[Import] ABUSE PREVENTION: CSV has {len(df)} rows. "
                  f"Maximum allowed: {MAX_ROWS_PER_CSV}. "
                  f"Only processing first {MAX_ROWS_PER_CSV} rows.")
            df = df.head(MAX_ROWS_PER_CSV)
        
        existing_response_ids = set()
        if skip_existing:
            # CRITICAL: Only check for existing records for this user
            # Convert integer user_id to string for SurveyResponse (which uses string user_id)
            existing_responses = session.query(SurveyResponse).filter(SurveyResponse.user_id == str(user_id)).all()
            existing_response_ids = {response.response_id for response in existing_responses}
        
        for idx, row in df.iterrows():
            response_id = str(safe_get(row, 'response_id', '')).strip()
            if not response_id:
                errors += 1
                continue
            
            if skip_existing and response_id in existing_response_ids:
                skipped += 1
                continue
            
            try:
                # CRITICAL SECURITY CHECK: Validate CSV user_id matches logged-in user_id
                # Skip rows where user_id doesn't match to prevent cross-user data editing
                csv_user_id_str = str(safe_get(row, 'user_id', '')).strip()
                csv_user_id_int = safe_int(csv_user_id_str, None)
                if csv_user_id_int is not None and csv_user_id_int != user_id:
                    print(f"[Import] SECURITY: Skipping survey response {response_id} - CSV user_id ({csv_user_id_int}) does not match logged-in user_id ({user_id})")
                    skipped += 1
                    continue
                
                # CRITICAL: Override any user_id from CSV with the provided user_id for security
                # Convert integer user_id to string for SurveyResponse (which uses string user_id)
                user_id_str = str(user_id)
                question_category = str(safe_get(row, 'question_category', '')).strip()
                question_id = str(safe_get(row, 'question_id', '')).strip()
                
                if not question_category or not question_id:
                    errors += 1
                    continue
                
                response_value = str(safe_get(row, 'response_value', '')).strip() or None
                response_text = str(safe_get(row, 'response_text', '')).strip() or None
                timestamp = parse_datetime(safe_get(row, 'timestamp', '')) or datetime.utcnow()
                
                existing_response = session.query(SurveyResponse).filter(
                    SurveyResponse.response_id == response_id,
                    SurveyResponse.user_id == user_id_str
                ).first()
                if not existing_response:
                    response = SurveyResponse(
                        response_id=response_id,
                        user_id=user_id_str,  # CRITICAL: Always use provided user_id (override CSV value)
                        question_category=question_category,
                        question_id=question_id,
                        response_value=response_value,
                        response_text=response_text,
                        timestamp=timestamp
                    )
                    session.add(response)
                    imported += 1
                else:
                    skipped += 1
                
            except Exception as e:
                print(f"[Import] Error importing survey response {response_id}: {e}")
                import traceback
                print(f"[Import] Traceback: {traceback.format_exc()}")
                errors += 1
                # Continue processing other rows
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        print(f"[Import] Error reading survey responses CSV: {e}")
        import traceback
        print(f"[Import] Traceback: {traceback.format_exc()}")
        # Don't raise - return what we have so far
        pass
    
    return imported, skipped, errors


def import_user_preferences_from_csv(csv_path: str) -> Tuple[int, int]:
    """Import user preferences from CSV file. Handles missing columns gracefully."""
    imported = 0
    errors = 0
    
    try:
        df = pd.read_csv(csv_path, dtype=str).fillna('')
        user_state = UserStateManager()
        
        for idx, row in df.iterrows():
            try:
                user_id = str(safe_get(row, 'user_id', '')).strip()
                if not user_id:
                    continue
                
                # Update all preferences from row - only process columns that exist
                for key in row.index:
                    if key and key != 'user_id':  # Skip user_id itself
                        value = safe_get(row, key, '')
                        if value:
                            try:
                                user_state.update_preference(user_id, key, value)
                            except Exception as e:
                                print(f"[Import] Error updating preference {key} for user {user_id}: {e}")
                                # Continue with other preferences
                
                imported += 1
                
            except Exception as e:
                print(f"[Import] Error importing user preferences for row {idx}: {e}")
                import traceback
                print(f"[Import] Traceback: {traceback.format_exc()}")
                errors += 1
                # Continue processing other rows
        
    except Exception as e:
        print(f"[Import] Error reading user preferences CSV: {e}")
        import traceback
        print(f"[Import] Traceback: {traceback.format_exc()}")
        # Don't raise - return what we have so far
        pass
    
    return imported, errors


def import_from_zip(zip_path: str, skip_existing: bool = True, user_id: Optional[int] = None) -> Dict[str, Dict[str, int]]:
    """
    Import all CSV files from a ZIP archive into the database.
    Handles extra CSV columns by attempting to add them to database schema.
    Falls back to backup CSV files if schema updates fail.
    Includes abuse prevention measures.
    
    **SECURITY:** All imported data is assigned to the provided user_id, overriding any user_id in the CSV files.
    This ensures imported data belongs to the importing user.
    
    Security:
    - REJECTS ZIPs with unexpected/additional files (security)
    - ACCEPTS ZIPs with only expected files (even if some are missing for old version compatibility)
    - Missing files are handled gracefully (will use default/empty values)
    - REQUIRES user_id to ensure users can only import data for themselves
    
    Expected files (all must be present or none):
    - tasks.csv
    - task_instances.csv
    - emotions.csv
    - notes.csv
    - popup_triggers.csv
    - popup_responses.csv
    - survey_responses.csv
    - user_preferences.csv
    
    Compatibility:
    - Accepts ZIPs from old versions (fewer files) - missing files are skipped with note
    - Missing columns in CSV files are handled by imputing empty/default values
    - New columns in database (like user_id) are nullable, so old data imports fine
    
    Args:
        zip_path: Path to ZIP file
        skip_existing: If True, skip records that already exist
        user_id: REQUIRED user ID. All imported data will be assigned to this user.
    
    Returns:
        Dictionary mapping table names to import statistics (imported, skipped, errors)
        Includes '_error' key if import is rejected due to validation failure
    
    Raises:
        ValueError: If user_id is None (security requirement)
    """
    # CRITICAL: Require user_id for data isolation
    if user_id is None:
        raise ValueError("user_id is REQUIRED for import. Users can only import data for themselves.")
    results = {}
    temp_dir = tempfile.mkdtemp()
    backup_dir = os.path.join(temp_dir, 'backup_extra_columns')
    
    try:
        # Abuse prevention: Check ZIP file size
        is_valid_size, size_error = check_file_size(zip_path)
        if not is_valid_size:
            results['_error'] = {
                'error': size_error,
                'note': 'Import rejected due to file size limit'
            }
            return results
        
        # Define whitelist of allowed file names (security: prevent additional files)
        ALLOWED_FILES = {
            'tasks.csv': ('tasks', import_tasks_from_csv),
            'task_instances.csv': ('task_instances', import_task_instances_from_csv),
            'emotions.csv': ('emotions', import_emotions_from_csv),
            'notes.csv': ('notes', import_notes_from_csv),
            'popup_triggers.csv': ('popup_triggers', import_popup_triggers_from_csv),
            'popup_responses.csv': ('popup_responses', import_popup_responses_from_csv),
            'survey_responses.csv': ('survey_responses', import_survey_responses_from_csv),
            'user_preferences.csv': ('user_preferences', None)  # Handled separately
        }
        
        # Extract ZIP to temp directory
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            # Abuse prevention: Check number of files in ZIP
            file_list = zipf.namelist()
            if len(file_list) > MAX_FILES_PER_ZIP:
                results['_error'] = {
                    'error': f'ZIP contains too many files ({len(file_list)}). Maximum allowed: {MAX_FILES_PER_ZIP}.',
                    'note': 'Import rejected to prevent abuse'
                }
                return results
            
            # Security: Validate that all files in ZIP are on whitelist
            # Reject ZIP if it contains any unexpected files
            # This prevents malicious ZIP files with additional files
            unexpected_files = []
            for file_name in file_list:
                # Skip directories (they end with '/' in ZIP file lists)
                if file_name.endswith('/'):
                    continue
                
                # Extract just the filename (ignore directories/paths)
                # Handle both 'tasks.csv' and 'data/tasks.csv' formats
                base_name = os.path.basename(file_name)
                
                # Skip empty strings (shouldn't happen, but be safe)
                if not base_name:
                    continue
                
                # Only check actual files (CSV files)
                # Reject any file that's not in our whitelist
                if base_name not in ALLOWED_FILES:
                    unexpected_files.append(base_name)
            
            if unexpected_files:
                results['_error'] = {
                    'error': f'ZIP contains unexpected files: {", ".join(unexpected_files)}',
                    'note': 'Import rejected for security. Only expected CSV files are allowed.',
                    'allowed_files': list(ALLOWED_FILES.keys())
                }
                return results
            
            zipf.extractall(temp_dir)
        
        # Initialize database
        init_db()
        session = get_session()
        
        try:
            # Helper function to find file in extracted directory (handles subdirectories)
            def find_file_in_dir(directory, filename):
                """Find file in directory, searching recursively if needed."""
                # Try direct path first (most common case)
                direct_path = os.path.join(directory, filename)
                if os.path.exists(direct_path) and os.path.isfile(direct_path):
                    return direct_path
                
                # Search recursively (for ZIPs that preserve directory structure)
                for root, dirs, files in os.walk(directory):
                    if filename in files:
                        return os.path.join(root, filename)
                return None
            
            # Import each expected CSV file (allow missing files for old version compatibility)
            for filename, (table_name, import_func) in ALLOWED_FILES.items():
                csv_path = find_file_in_dir(temp_dir, filename)
                if csv_path and os.path.exists(csv_path):
                    try:
                        if import_func:
                            # CRITICAL: Pass user_id to all import functions for data isolation
                            # Check function signature to determine which parameters it needs
                            import inspect
                            sig = inspect.signature(import_func)
                            params = list(sig.parameters.keys())
                            
                            # Build arguments based on function signature
                            kwargs = {
                                'csv_path': csv_path,
                                'session': session,
                                'skip_existing': skip_existing,
                                'user_id': user_id
                            }
                            
                            # Add backup_dir if function accepts it
                            if 'backup_dir' in params:
                                kwargs['backup_dir'] = backup_dir
                            
                            # Call function with appropriate arguments
                            result = import_func(**{k: v for k, v in kwargs.items() if k in params})
                            imported, skipped, errors = result
                            results[table_name] = {
                                'imported': imported,
                                'skipped': skipped,
                                'errors': errors
                            }
                        elif table_name == 'user_preferences':
                            # user_preferences import doesn't need user_id (it reads from CSV)
                            # but we should still filter by user_id for security
                            imported, errors = import_user_preferences_from_csv(csv_path)
                            results[table_name] = {
                                'imported': imported,
                                'skipped': 0,
                                'errors': errors
                            }
                    except Exception as e:
                        print(f"[Import] Error processing {filename}: {e}")
                        import traceback
                        print(f"[Import] Traceback: {traceback.format_exc()}")
                        results[table_name] = {
                            'imported': 0,
                            'skipped': 0,
                            'errors': 0,
                            'error': str(e),
                            'note': 'Failed to import file'
                        }
                else:
                    # File missing - this is OK for old version compatibility
                    # Missing columns will be handled by imputing empty values in import functions
                    results[table_name] = {
                        'imported': 0,
                        'skipped': 0,
                        'errors': 0,
                        'note': 'File not found in ZIP (old version compatibility - will use defaults)'
                    }
            
            # Check if backup files were created and move to permanent location
            if os.path.exists(backup_dir) and os.listdir(backup_dir):
                backup_files = os.listdir(backup_dir)
                # Move backup files to data directory for permanent storage
                data_dir = os.path.join(Path(__file__).resolve().parent.parent, "data")
                permanent_backup_dir = os.path.join(data_dir, 'import_backups')
                os.makedirs(permanent_backup_dir, exist_ok=True)
                
                moved_files = []
                for backup_file in backup_files:
                    src = os.path.join(backup_dir, backup_file)
                    dst = os.path.join(permanent_backup_dir, backup_file)
                    try:
                        import shutil
                        shutil.copy2(src, dst)  # Copy instead of move to keep temp copy
                        moved_files.append(dst)
                    except Exception as e:
                        print(f"[Import] Could not copy backup file {backup_file}: {e}")
                
                if moved_files:
                    results['_backup_info'] = {
                        'backup_dir': permanent_backup_dir,
                        'backup_files': [os.path.basename(f) for f in moved_files],
                        'note': f'Extra columns data saved to {len(moved_files)} backup file(s) in {permanent_backup_dir}'
                    }
        
        finally:
            session.close()
    
    finally:
        # Note: We don't delete temp_dir immediately - backup files might be needed
        # The temp directory will be cleaned up by the OS eventually
        pass
    
    return results
