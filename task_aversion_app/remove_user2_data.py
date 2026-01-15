#!/usr/bin/env python3
"""
Script to remove all data for user 2 from the database.
This is used for testing data isolation between users.

WARNING: This script permanently deletes data. Use with caution.
"""
import os
import sys
from pathlib import Path
import pandas as pd

# Add the parent directory to the path so we can import backend modules
sys.path.insert(0, str(Path(__file__).parent))

from backend.database import (
    get_session,
    init_db,
    User,
    Task,
    TaskInstance,
    Note,
    UserPreferences,
    SurveyResponse,
    PopupTrigger,
    PopupResponse,
)

# CSV file paths (if they still exist)
DATA_DIR = Path(__file__).parent / "data"
USER_PREFS_CSV = DATA_DIR / "user_preferences.csv"
SURVEY_RESPONSES_CSV = DATA_DIR / "survey_responses.csv"


def count_user_data(session, user_id: int, user_id_str: str) -> dict:
    """Count how many records exist for user 2 before deletion."""
    counts = {}
    
    # Integer user_id tables
    counts['tasks'] = session.query(Task).filter(Task.user_id == user_id).count()
    counts['task_instances'] = session.query(TaskInstance).filter(TaskInstance.user_id == user_id).count()
    counts['notes'] = session.query(Note).filter(Note.user_id == user_id).count()
    
    # String user_id tables
    counts['user_preferences'] = session.query(UserPreferences).filter(UserPreferences.user_id == user_id_str).count()
    counts['survey_responses'] = session.query(SurveyResponse).filter(SurveyResponse.user_id == user_id_str).count()
    counts['popup_triggers'] = session.query(PopupTrigger).filter(PopupTrigger.user_id == user_id_str).count()
    counts['popup_responses'] = session.query(PopupResponse).filter(PopupResponse.user_id == user_id_str).count()
    
    # User record itself
    counts['users'] = session.query(User).filter(User.user_id == user_id).count()
    
    return counts


def delete_user_data(session, user_id: int, user_id_str: str) -> dict:
    """Delete all data for user 2 from the database."""
    deleted = {}
    
    # Delete from tables with integer user_id (in order to respect foreign key constraints)
    # Note: Task and TaskInstance have CASCADE delete, but we'll delete explicitly for clarity
    
    # Delete task instances first (they reference tasks)
    task_instances = session.query(TaskInstance).filter(TaskInstance.user_id == user_id).all()
    deleted['task_instances'] = len(task_instances)
    for instance in task_instances:
        session.delete(instance)
    
    # Delete tasks
    tasks = session.query(Task).filter(Task.user_id == user_id).all()
    deleted['tasks'] = len(tasks)
    for task in tasks:
        session.delete(task)
    
    # Delete notes
    notes = session.query(Note).filter(Note.user_id == user_id).all()
    deleted['notes'] = len(notes)
    for note in notes:
        session.delete(note)
    
    # Delete from tables with string user_id
    user_prefs = session.query(UserPreferences).filter(UserPreferences.user_id == user_id_str).all()
    deleted['user_preferences'] = len(user_prefs)
    for pref in user_prefs:
        session.delete(pref)
    
    survey_responses = session.query(SurveyResponse).filter(SurveyResponse.user_id == user_id_str).all()
    deleted['survey_responses'] = len(survey_responses)
    for resp in survey_responses:
        session.delete(resp)
    
    popup_triggers = session.query(PopupTrigger).filter(PopupTrigger.user_id == user_id_str).all()
    deleted['popup_triggers'] = len(popup_triggers)
    for trigger in popup_triggers:
        session.delete(trigger)
    
    popup_responses = session.query(PopupResponse).filter(PopupResponse.user_id == user_id_str).all()
    deleted['popup_responses'] = len(popup_responses)
    for resp in popup_responses:
        session.delete(resp)
    
    # Optionally delete the User record itself (uncomment if desired)
    # users = session.query(User).filter(User.user_id == user_id).all()
    # deleted['users'] = len(users)
    # for user in users:
    #     session.delete(user)
    
    return deleted


def clean_csv_files(user_id_str: str) -> dict:
    """Remove user 2 data from CSV files if they exist."""
    cleaned = {}
    
    # Clean user_preferences.csv
    if USER_PREFS_CSV.exists():
        try:
            df = pd.read_csv(USER_PREFS_CSV, dtype=str)
            initial_count = len(df)
            df = df[df['user_id'] != user_id_str]
            cleaned['user_preferences_csv'] = initial_count - len(df)
            if cleaned['user_preferences_csv'] > 0:
                df.to_csv(USER_PREFS_CSV, index=False)
        except Exception as e:
            print(f"[WARNING] Error cleaning {USER_PREFS_CSV}: {e}")
            cleaned['user_preferences_csv'] = 0
    else:
        cleaned['user_preferences_csv'] = 0
    
    # Clean survey_responses.csv
    if SURVEY_RESPONSES_CSV.exists():
        try:
            df = pd.read_csv(SURVEY_RESPONSES_CSV, dtype=str)
            initial_count = len(df)
            df = df[df['user_id'] != user_id_str]
            cleaned['survey_responses_csv'] = initial_count - len(df)
            if cleaned['survey_responses_csv'] > 0:
                df.to_csv(SURVEY_RESPONSES_CSV, index=False)
        except Exception as e:
            print(f"[WARNING] Error cleaning {SURVEY_RESPONSES_CSV}: {e}")
            cleaned['survey_responses_csv'] = 0
    else:
        cleaned['survey_responses_csv'] = 0
    
    return cleaned


def main():
    """Main function to remove all user 2 data."""
    user_id = 2
    user_id_str = '2'
    
    print("=" * 60)
    print("User 2 Data Removal Script")
    print("=" * 60)
    print(f"Target user_id: {user_id} (integer) / '{user_id_str}' (string)")
    print()
    
    # Initialize database
    init_db()
    
    # Get database session
    session = get_session()
    
    try:
        # Count existing data
        print("[INFO] Counting existing data for user 2...")
        counts = count_user_data(session, user_id, user_id_str)
        
        print("\n[INFO] Current data counts:")
        for table, count in counts.items():
            if count > 0:
                print(f"  {table}: {count} record(s)")
        
        total_db_records = sum(counts.values())
        if total_db_records == 0:
            print("\n[INFO] No data found for user 2 in database.")
        else:
            # Confirm deletion
            print(f"\n[WARNING] About to delete {total_db_records} record(s) from database.")
            response = input("Continue? (yes/no): ").strip().lower()
            
            if response != 'yes':
                print("[INFO] Operation cancelled.")
                return
            
            # Delete from database
            print("\n[INFO] Deleting data from database...")
            deleted = delete_user_data(session, user_id, user_id_str)
            session.commit()
            
            print("\n[INFO] Database deletion summary:")
            for table, count in deleted.items():
                if count > 0:
                    print(f"  {table}: {count} record(s) deleted")
        
        # Clean CSV files
        print("\n[INFO] Checking CSV files...")
        cleaned = clean_csv_files(user_id_str)
        
        csv_changes = sum(cleaned.values())
        if csv_changes > 0:
            print("\n[INFO] CSV file cleanup summary:")
            for file, count in cleaned.items():
                if count > 0:
                    print(f"  {file}: {count} record(s) removed")
        else:
            print("[INFO] No changes needed in CSV files.")
        
        print("\n[SUCCESS] Data removal completed successfully!")
        
    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] An error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
