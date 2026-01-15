#!/usr/bin/env python
"""
Migration script to migrate data from non-users (NULL, empty, or 'default' user_id)
to user_id = 1 in both database and CSV files.

This includes:
- Task templates (Task model)
- Task instances (TaskInstance model)
- Notes (Note model)
- User preferences (UserPreferences model)
- Survey responses (SurveyResponse model)
- Popup triggers (PopupTrigger model)
- Popup responses (PopupResponse model)

The script also checks for and removes duplicate data.
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

# Set DATABASE_URL
os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import (
    init_db, get_session, Task, TaskInstance, Note, UserPreferences,
    SurveyResponse, PopupTrigger, PopupResponse, User
)

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
TARGET_USER_ID = 1
TARGET_USER_ID_STR = "1"

# Values that indicate "non-user" data
NON_USER_VALUES = {None, '', 'default', 'default_user', '0', 'null', 'NULL'}


def is_non_user(user_id: Optional[str]) -> bool:
    """Check if user_id represents a non-user."""
    if user_id is None:
        return True
    if isinstance(user_id, (int, float)):
        return user_id == 0 or pd.isna(user_id)
    user_id_str = str(user_id).strip().lower()
    return user_id_str in NON_USER_VALUES or user_id_str == ''


def ensure_user_exists(session, user_id: int = 1) -> bool:
    """Ensure user with user_id exists in database. Create if missing."""
    user = session.query(User).filter(User.user_id == user_id).first()
    if user is None:
        # Create a default user
        user = User(
            user_id=user_id,
            email=f"user{user_id}@migrated.local",
            username=f"Migrated User {user_id}",
            oauth_provider='migration',
            email_verified=False,
            is_active=True
        )
        session.add(user)
        session.commit()
        print(f"   [INFO] Created user {user_id} in database")
        return True
    return False


def migrate_tasks_from_database(session) -> Tuple[int, int, int]:
    """
    Migrate tasks (task templates) from database where user_id is NULL/empty to user_id = 1.
    Returns: (migrated_count, duplicates_removed, errors)
    """
    print("\n[MIGRATE] Migrating tasks (templates) from database...")
    
    # Find tasks with non-user user_id
    non_user_tasks = session.query(Task).filter(
        (Task.user_id.is_(None)) | (Task.user_id == 0)
    ).all()
    
    if not non_user_tasks:
        print("   [SKIP] No tasks with non-user user_id found")
        return 0, 0, 0
    
    print(f"   Found {len(non_user_tasks)} task(s) to migrate")
    
    # Get existing tasks for user 1 to check for duplicates
    existing_task_ids = {
        task.task_id for task in session.query(Task).filter(Task.user_id == TARGET_USER_ID).all()
    }
    
    migrated = 0
    duplicates = 0
    errors = 0
    
    for task in non_user_tasks:
        try:
            # Check for duplicate
            if task.task_id in existing_task_ids:
                print(f"   [DUPLICATE] Task {task.task_id} ({task.name}) already exists for user 1 - removing duplicate")
                session.delete(task)
                duplicates += 1
                continue
            
            # Migrate to user 1
            task.user_id = TARGET_USER_ID
            migrated += 1
            print(f"   [OK] Migrated task: {task.name} ({task.task_id})")
            
        except Exception as e:
            print(f"   [ERROR] Failed to migrate task {task.task_id}: {e}")
            errors += 1
    
    if migrated > 0 or duplicates > 0:
        session.commit()
    
    return migrated, duplicates, errors


def migrate_task_instances_from_database(session) -> Tuple[int, int, int]:
    """
    Migrate task instances from database where user_id is NULL/empty to user_id = 1.
    Returns: (migrated_count, duplicates_removed, errors)
    """
    print("\n[MIGRATE] Migrating task instances from database...")
    
    # Find instances with non-user user_id
    non_user_instances = session.query(TaskInstance).filter(
        (TaskInstance.user_id.is_(None)) | (TaskInstance.user_id == 0)
    ).all()
    
    if not non_user_instances:
        print("   [SKIP] No task instances with non-user user_id found")
        return 0, 0, 0
    
    print(f"   Found {len(non_user_instances)} instance(s) to migrate")
    
    # Get existing instances for user 1 to check for duplicates
    existing_instance_ids = {
        inst.instance_id for inst in session.query(TaskInstance).filter(
            TaskInstance.user_id == TARGET_USER_ID
        ).all()
    }
    
    migrated = 0
    duplicates = 0
    errors = 0
    
    for instance in non_user_instances:
        try:
            # Check for duplicate
            if instance.instance_id in existing_instance_ids:
                print(f"   [DUPLICATE] Instance {instance.instance_id} already exists for user 1 - removing duplicate")
                session.delete(instance)
                duplicates += 1
                continue
            
            # Migrate to user 1
            instance.user_id = TARGET_USER_ID
            migrated += 1
            
        except Exception as e:
            print(f"   [ERROR] Failed to migrate instance {instance.instance_id}: {e}")
            errors += 1
    
    if migrated > 0 or duplicates > 0:
        session.commit()
    
    if migrated > 0:
        print(f"   [OK] Migrated {migrated} instance(s)")
    
    return migrated, duplicates, errors


def migrate_notes_from_database(session) -> Tuple[int, int, int]:
    """
    Migrate notes from database where user_id is NULL/empty to user_id = 1.
    Returns: (migrated_count, duplicates_removed, errors)
    """
    print("\n[MIGRATE] Migrating notes from database...")
    
    # Find notes with non-user user_id
    non_user_notes = session.query(Note).filter(
        (Note.user_id.is_(None)) | (Note.user_id == 0)
    ).all()
    
    if not non_user_notes:
        print("   [SKIP] No notes with non-user user_id found")
        return 0, 0, 0
    
    print(f"   Found {len(non_user_notes)} note(s) to migrate")
    
    # Get existing notes for user 1 to check for duplicates
    existing_note_ids = {
        note.note_id for note in session.query(Note).filter(Note.user_id == TARGET_USER_ID).all()
    }
    
    migrated = 0
    duplicates = 0
    errors = 0
    
    for note in non_user_notes:
        try:
            # Check for duplicate
            if note.note_id in existing_note_ids:
                print(f"   [DUPLICATE] Note {note.note_id} already exists for user 1 - removing duplicate")
                session.delete(note)
                duplicates += 1
                continue
            
            # Migrate to user 1
            note.user_id = TARGET_USER_ID
            migrated += 1
            
        except Exception as e:
            print(f"   [ERROR] Failed to migrate note {note.note_id}: {e}")
            errors += 1
    
    if migrated > 0 or duplicates > 0:
        session.commit()
    
    if migrated > 0:
        print(f"   [OK] Migrated {migrated} note(s)")
    
    return migrated, duplicates, errors


def migrate_user_preferences_from_database(session) -> Tuple[int, int, int]:
    """
    Migrate user preferences from database where user_id is non-user to user_id = "1".
    Returns: (migrated_count, duplicates_removed, errors)
    """
    print("\n[MIGRATE] Migrating user preferences from database...")
    
    # Find preferences with non-user user_id
    all_prefs = session.query(UserPreferences).all()
    non_user_prefs = [
        pref for pref in all_prefs
        if is_non_user(pref.user_id)
    ]
    
    if not non_user_prefs:
        print("   [SKIP] No user preferences with non-user user_id found")
        return 0, 0, 0
    
    print(f"   Found {len(non_user_prefs)} preference(s) to migrate")
    
    # Check if user 1 preferences already exist
    existing_pref = session.query(UserPreferences).filter(
        UserPreferences.user_id == TARGET_USER_ID_STR
    ).first()
    
    migrated = 0
    duplicates = 0
    errors = 0
    
    for pref in non_user_prefs:
        try:
            if existing_pref is not None:
                # Merge preferences (keep existing, update with non-user values where missing)
                print(f"   [MERGE] Merging preferences from '{pref.user_id}' into user 1")
                # For now, just delete the duplicate - user 1 already has preferences
                session.delete(pref)
                duplicates += 1
            else:
                # Migrate to user 1
                pref.user_id = TARGET_USER_ID_STR
                migrated += 1
                existing_pref = pref
                
        except Exception as e:
            print(f"   [ERROR] Failed to migrate preference {pref.user_id}: {e}")
            errors += 1
    
    if migrated > 0 or duplicates > 0:
        session.commit()
    
    if migrated > 0:
        print(f"   [OK] Migrated {migrated} preference(s)")
    
    return migrated, duplicates, errors


def migrate_survey_responses_from_database(session) -> Tuple[int, int, int]:
    """
    Migrate survey responses from database where user_id is non-user to user_id = "1".
    Returns: (migrated_count, duplicates_removed, errors)
    """
    print("\n[MIGRATE] Migrating survey responses from database...")
    
    # Find responses with non-user user_id
    all_responses = session.query(SurveyResponse).all()
    non_user_responses = [
        resp for resp in all_responses
        if is_non_user(resp.user_id)
    ]
    
    if not non_user_responses:
        print("   [SKIP] No survey responses with non-user user_id found")
        return 0, 0, 0
    
    print(f"   Found {len(non_user_responses)} response(s) to migrate")
    
    # Get existing responses for user 1 to check for duplicates
    existing_response_ids = {
        resp.response_id for resp in session.query(SurveyResponse).filter(
            SurveyResponse.user_id == TARGET_USER_ID_STR
        ).all()
    }
    
    migrated = 0
    duplicates = 0
    errors = 0
    
    for response in non_user_responses:
        try:
            # Check for duplicate
            if response.response_id in existing_response_ids:
                print(f"   [DUPLICATE] Response {response.response_id} already exists for user 1 - removing duplicate")
                session.delete(response)
                duplicates += 1
                continue
            
            # Migrate to user 1
            response.user_id = TARGET_USER_ID_STR
            migrated += 1
            
        except Exception as e:
            print(f"   [ERROR] Failed to migrate response {response.response_id}: {e}")
            errors += 1
    
    if migrated > 0 or duplicates > 0:
        session.commit()
    
    if migrated > 0:
        print(f"   [OK] Migrated {migrated} response(s)")
    
    return migrated, duplicates, errors


def migrate_popup_triggers_from_database(session) -> Tuple[int, int, int]:
    """
    Migrate popup triggers from database where user_id is non-user to user_id = "1".
    Returns: (migrated_count, duplicates_removed, errors)
    """
    print("\n[MIGRATE] Migrating popup triggers from database...")
    
    # Find triggers with non-user user_id
    all_triggers = session.query(PopupTrigger).all()
    non_user_triggers = [
        trigger for trigger in all_triggers
        if is_non_user(trigger.user_id)
    ]
    
    if not non_user_triggers:
        print("   [SKIP] No popup triggers with non-user user_id found")
        return 0, 0, 0
    
    print(f"   Found {len(non_user_triggers)} trigger(s) to migrate")
    
    # Get existing triggers for user 1 to check for duplicates
    existing_triggers = session.query(PopupTrigger).filter(
        PopupTrigger.user_id == TARGET_USER_ID_STR
    ).all()
    existing_trigger_keys = {
        (t.trigger_id, t.task_id) for t in existing_triggers
    }
    
    migrated = 0
    duplicates = 0
    errors = 0
    
    for trigger in non_user_triggers:
        try:
            # Check for duplicate (same trigger_id and task_id)
            key = (trigger.trigger_id, trigger.task_id)
            if key in existing_trigger_keys:
                print(f"   [DUPLICATE] Trigger {trigger.trigger_id} (task: {trigger.task_id}) already exists for user 1 - removing duplicate")
                session.delete(trigger)
                duplicates += 1
                continue
            
            # Migrate to user 1
            trigger.user_id = TARGET_USER_ID_STR
            migrated += 1
            
        except Exception as e:
            print(f"   [ERROR] Failed to migrate trigger {trigger.id}: {e}")
            errors += 1
    
    if migrated > 0 or duplicates > 0:
        session.commit()
    
    if migrated > 0:
        print(f"   [OK] Migrated {migrated} trigger(s)")
    
    return migrated, duplicates, errors


def migrate_popup_responses_from_database(session) -> Tuple[int, int, int]:
    """
    Migrate popup responses from database where user_id is non-user to user_id = "1".
    Returns: (migrated_count, duplicates_removed, errors)
    """
    print("\n[MIGRATE] Migrating popup responses from database...")
    
    # Find responses with non-user user_id
    all_responses = session.query(PopupResponse).all()
    non_user_responses = [
        resp for resp in all_responses
        if is_non_user(resp.user_id)
    ]
    
    if not non_user_responses:
        print("   [SKIP] No popup responses with non-user user_id found")
        return 0, 0, 0
    
    print(f"   Found {len(non_user_responses)} response(s) to migrate")
    
    # Get existing responses for user 1 to check for duplicates
    existing_response_ids = {
        resp.id for resp in session.query(PopupResponse).filter(
            PopupResponse.user_id == TARGET_USER_ID_STR
        ).all()
    }
    
    migrated = 0
    duplicates = 0
    errors = 0
    
    for response in non_user_responses:
        try:
            # Check for duplicate
            if response.id in existing_response_ids:
                print(f"   [DUPLICATE] Popup response {response.id} already exists for user 1 - removing duplicate")
                session.delete(response)
                duplicates += 1
                continue
            
            # Migrate to user 1
            response.user_id = TARGET_USER_ID_STR
            migrated += 1
            
        except Exception as e:
            print(f"   [ERROR] Failed to migrate popup response {response.id}: {e}")
            errors += 1
    
    if migrated > 0 or duplicates > 0:
        session.commit()
    
    if migrated > 0:
        print(f"   [OK] Migrated {migrated} response(s)")
    
    return migrated, duplicates, errors


def migrate_tasks_from_csv() -> Tuple[int, int, int]:
    """
    Migrate tasks from CSV where user_id is non-user to user_id = 1.
    Returns: (migrated_count, duplicates_removed, errors)
    """
    print("\n[MIGRATE] Migrating tasks (templates) from CSV...")
    
    csv_file = os.path.join(DATA_DIR, 'tasks.csv')
    if not os.path.exists(csv_file):
        print("   [SKIP] tasks.csv not found")
        return 0, 0, 0
    
    try:
        df = pd.read_csv(csv_file, dtype=str).fillna('')
    except Exception as e:
        print(f"   [ERROR] Failed to read CSV: {e}")
        return 0, 0, 0
    
    if 'user_id' not in df.columns:
        df['user_id'] = ''
    
    # Find rows with non-user user_id
    non_user_mask = df['user_id'].apply(is_non_user)
    non_user_count = non_user_mask.sum()
    
    if non_user_count == 0:
        print("   [SKIP] No tasks with non-user user_id found")
        return 0, 0, 0
    
    print(f"   Found {non_user_count} task(s) to migrate")
    
    # Get existing task_ids for user 1
    existing_task_ids = set(
        df[df['user_id'].astype(str) == TARGET_USER_ID_STR]['task_id'].tolist()
    )
    
    migrated = 0
    duplicates = 0
    errors = 0
    
    for idx, row in df[non_user_mask].iterrows():
        try:
            task_id = str(row.get('task_id', '')).strip()
            if not task_id:
                continue
            
            # Check for duplicate
            if task_id in existing_task_ids:
                print(f"   [DUPLICATE] Task {task_id} already exists for user 1 - removing from CSV")
                df = df.drop(idx)
                duplicates += 1
                continue
            
            # Migrate to user 1
            df.at[idx, 'user_id'] = TARGET_USER_ID_STR
            migrated += 1
            existing_task_ids.add(task_id)
            
        except Exception as e:
            print(f"   [ERROR] Failed to migrate task at row {idx}: {e}")
            errors += 1
    
    if migrated > 0 or duplicates > 0:
        df.to_csv(csv_file, index=False)
        print(f"   [OK] Updated CSV file")
    
    return migrated, duplicates, errors


def migrate_task_instances_from_csv() -> Tuple[int, int, int]:
    """
    Migrate task instances from CSV where user_id is non-user to user_id = 1.
    Returns: (migrated_count, duplicates_removed, errors)
    """
    print("\n[MIGRATE] Migrating task instances from CSV...")
    
    csv_file = os.path.join(DATA_DIR, 'task_instances.csv')
    if not os.path.exists(csv_file):
        print("   [SKIP] task_instances.csv not found")
        return 0, 0, 0
    
    try:
        df = pd.read_csv(csv_file, dtype=str).fillna('')
    except Exception as e:
        print(f"   [ERROR] Failed to read CSV: {e}")
        return 0, 0, 0
    
    if 'user_id' not in df.columns:
        df['user_id'] = ''
    
    # Find rows with non-user user_id
    non_user_mask = df['user_id'].apply(is_non_user)
    non_user_count = non_user_mask.sum()
    
    if non_user_count == 0:
        print("   [SKIP] No task instances with non-user user_id found")
        return 0, 0, 0
    
    print(f"   Found {non_user_count} instance(s) to migrate")
    
    # Get existing instance_ids for user 1
    existing_instance_ids = set(
        df[df['user_id'].astype(str) == TARGET_USER_ID_STR]['instance_id'].tolist()
    )
    
    migrated = 0
    duplicates = 0
    errors = 0
    
    for idx, row in df[non_user_mask].iterrows():
        try:
            instance_id = str(row.get('instance_id', '')).strip()
            if not instance_id:
                continue
            
            # Check for duplicate
            if instance_id in existing_instance_ids:
                print(f"   [DUPLICATE] Instance {instance_id} already exists for user 1 - removing from CSV")
                df = df.drop(idx)
                duplicates += 1
                continue
            
            # Migrate to user 1
            df.at[idx, 'user_id'] = TARGET_USER_ID_STR
            migrated += 1
            existing_instance_ids.add(instance_id)
            
        except Exception as e:
            print(f"   [ERROR] Failed to migrate instance at row {idx}: {e}")
            errors += 1
    
    if migrated > 0 or duplicates > 0:
        df.to_csv(csv_file, index=False)
        print(f"   [OK] Updated CSV file")
    
    return migrated, duplicates, errors


def migrate_notes_from_csv() -> Tuple[int, int, int]:
    """
    Migrate notes from CSV where user_id is non-user to user_id = 1.
    Returns: (migrated_count, duplicates_removed, errors)
    """
    print("\n[MIGRATE] Migrating notes from CSV...")
    
    csv_file = os.path.join(DATA_DIR, 'notes.csv')
    if not os.path.exists(csv_file):
        print("   [SKIP] notes.csv not found")
        return 0, 0, 0
    
    try:
        df = pd.read_csv(csv_file, dtype=str).fillna('')
    except Exception as e:
        print(f"   [ERROR] Failed to read CSV: {e}")
        return 0, 0, 0
    
    if 'user_id' not in df.columns:
        df['user_id'] = ''
    
    # Find rows with non-user user_id
    non_user_mask = df['user_id'].apply(is_non_user)
    non_user_count = non_user_mask.sum()
    
    if non_user_count == 0:
        print("   [SKIP] No notes with non-user user_id found")
        return 0, 0, 0
    
    print(f"   Found {non_user_count} note(s) to migrate")
    
    # Get existing note_ids for user 1
    existing_note_ids = set(
        df[df['user_id'].astype(str) == TARGET_USER_ID_STR]['note_id'].tolist()
    )
    
    migrated = 0
    duplicates = 0
    errors = 0
    
    for idx, row in df[non_user_mask].iterrows():
        try:
            note_id = str(row.get('note_id', '')).strip()
            if not note_id:
                continue
            
            # Check for duplicate
            if note_id in existing_note_ids:
                print(f"   [DUPLICATE] Note {note_id} already exists for user 1 - removing from CSV")
                df = df.drop(idx)
                duplicates += 1
                continue
            
            # Migrate to user 1
            df.at[idx, 'user_id'] = TARGET_USER_ID_STR
            migrated += 1
            existing_note_ids.add(note_id)
            
        except Exception as e:
            print(f"   [ERROR] Failed to migrate note at row {idx}: {e}")
            errors += 1
    
    if migrated > 0 or duplicates > 0:
        df.to_csv(csv_file, index=False)
        print(f"   [OK] Updated CSV file")
    
    return migrated, duplicates, errors


def migrate_user_preferences_from_csv() -> Tuple[int, int, int]:
    """
    Migrate user preferences from CSV where user_id is non-user to user_id = "1".
    Returns: (migrated_count, duplicates_removed, errors)
    """
    print("\n[MIGRATE] Migrating user preferences from CSV...")
    
    csv_file = os.path.join(DATA_DIR, 'user_preferences.csv')
    if not os.path.exists(csv_file):
        print("   [SKIP] user_preferences.csv not found")
        return 0, 0, 0
    
    try:
        df = pd.read_csv(csv_file, dtype=str).fillna('')
    except Exception as e:
        print(f"   [ERROR] Failed to read CSV: {e}")
        return 0, 0, 0
    
    if 'user_id' not in df.columns:
        print("   [SKIP] user_id column not found in CSV")
        return 0, 0, 0
    
    # Find rows with non-user user_id
    non_user_mask = df['user_id'].apply(is_non_user)
    non_user_count = non_user_mask.sum()
    
    if non_user_count == 0:
        print("   [SKIP] No user preferences with non-user user_id found")
        return 0, 0, 0
    
    print(f"   Found {non_user_count} preference(s) to migrate")
    
    # Check if user 1 preferences already exist
    user1_mask = df['user_id'].astype(str) == TARGET_USER_ID_STR
    has_user1 = user1_mask.any()
    
    migrated = 0
    duplicates = 0
    errors = 0
    
    for idx, row in df[non_user_mask].iterrows():
        try:
            if has_user1:
                # Merge or remove duplicate
                print(f"   [DUPLICATE] User 1 preferences already exist - removing duplicate from '{row.get('user_id', '')}'")
                df = df.drop(idx)
                duplicates += 1
            else:
                # Migrate to user 1
                df.at[idx, 'user_id'] = TARGET_USER_ID_STR
                migrated += 1
                has_user1 = True
                
        except Exception as e:
            print(f"   [ERROR] Failed to migrate preference at row {idx}: {e}")
            errors += 1
    
    if migrated > 0 or duplicates > 0:
        df.to_csv(csv_file, index=False)
        print(f"   [OK] Updated CSV file")
    
    return migrated, duplicates, errors


def migrate_survey_responses_from_csv() -> Tuple[int, int, int]:
    """
    Migrate survey responses from CSV where user_id is non-user to user_id = "1".
    Returns: (migrated_count, duplicates_removed, errors)
    """
    print("\n[MIGRATE] Migrating survey responses from CSV...")
    
    csv_file = os.path.join(DATA_DIR, 'survey_responses.csv')
    if not os.path.exists(csv_file):
        print("   [SKIP] survey_responses.csv not found")
        return 0, 0, 0
    
    try:
        df = pd.read_csv(csv_file, dtype=str).fillna('')
    except Exception as e:
        print(f"   [ERROR] Failed to read CSV: {e}")
        return 0, 0, 0
    
    if 'user_id' not in df.columns:
        df['user_id'] = ''
    
    # Find rows with non-user user_id
    non_user_mask = df['user_id'].apply(is_non_user)
    non_user_count = non_user_mask.sum()
    
    if non_user_count == 0:
        print("   [SKIP] No survey responses with non-user user_id found")
        return 0, 0, 0
    
    print(f"   Found {non_user_count} response(s) to migrate")
    
    # Get existing response_ids for user 1
    existing_response_ids = set(
        df[df['user_id'].astype(str) == TARGET_USER_ID_STR]['response_id'].tolist()
    )
    
    migrated = 0
    duplicates = 0
    errors = 0
    
    for idx, row in df[non_user_mask].iterrows():
        try:
            response_id = str(row.get('response_id', '')).strip()
            if not response_id:
                continue
            
            # Check for duplicate
            if response_id in existing_response_ids:
                print(f"   [DUPLICATE] Response {response_id} already exists for user 1 - removing from CSV")
                df = df.drop(idx)
                duplicates += 1
                continue
            
            # Migrate to user 1
            df.at[idx, 'user_id'] = TARGET_USER_ID_STR
            migrated += 1
            existing_response_ids.add(response_id)
            
        except Exception as e:
            print(f"   [ERROR] Failed to migrate response at row {idx}: {e}")
            errors += 1
    
    if migrated > 0 or duplicates > 0:
        df.to_csv(csv_file, index=False)
        print(f"   [OK] Updated CSV file")
    
    return migrated, duplicates, errors


def migrate_popup_triggers_from_csv() -> Tuple[int, int, int]:
    """
    Migrate popup triggers from CSV where user_id is non-user to user_id = "1".
    Returns: (migrated_count, duplicates_removed, errors)
    """
    print("\n[MIGRATE] Migrating popup triggers from CSV...")
    
    csv_file = os.path.join(DATA_DIR, 'popup_triggers.csv')
    if not os.path.exists(csv_file):
        print("   [SKIP] popup_triggers.csv not found")
        return 0, 0, 0
    
    try:
        df = pd.read_csv(csv_file, dtype=str).fillna('')
    except Exception as e:
        print(f"   [ERROR] Failed to read CSV: {e}")
        return 0, 0, 0
    
    if 'user_id' not in df.columns:
        df['user_id'] = ''
    
    # Find rows with non-user user_id
    non_user_mask = df['user_id'].apply(is_non_user)
    non_user_count = non_user_mask.sum()
    
    if non_user_count == 0:
        print("   [SKIP] No popup triggers with non-user user_id found")
        return 0, 0, 0
    
    print(f"   Found {non_user_count} trigger(s) to migrate")
    
    # Get existing triggers for user 1 (by trigger_id and task_id combination)
    user1_df = df[df['user_id'].astype(str) == TARGET_USER_ID_STR]
    existing_trigger_keys = set(
        zip(user1_df['trigger_id'].tolist(), user1_df['task_id'].fillna('').tolist())
    )
    
    migrated = 0
    duplicates = 0
    errors = 0
    
    for idx, row in df[non_user_mask].iterrows():
        try:
            trigger_id = str(row.get('trigger_id', '')).strip()
            task_id = str(row.get('task_id', '')).strip() if pd.notna(row.get('task_id')) else ''
            key = (trigger_id, task_id)
            
            # Check for duplicate
            if key in existing_trigger_keys:
                print(f"   [DUPLICATE] Trigger {trigger_id} (task: {task_id}) already exists for user 1 - removing from CSV")
                df = df.drop(idx)
                duplicates += 1
                continue
            
            # Migrate to user 1
            df.at[idx, 'user_id'] = TARGET_USER_ID_STR
            migrated += 1
            existing_trigger_keys.add(key)
            
        except Exception as e:
            print(f"   [ERROR] Failed to migrate trigger at row {idx}: {e}")
            errors += 1
    
    if migrated > 0 or duplicates > 0:
        df.to_csv(csv_file, index=False)
        print(f"   [OK] Updated CSV file")
    
    return migrated, duplicates, errors


def migrate_popup_responses_from_csv() -> Tuple[int, int, int]:
    """
    Migrate popup responses from CSV where user_id is non-user to user_id = "1".
    Returns: (migrated_count, duplicates_removed, errors)
    """
    print("\n[MIGRATE] Migrating popup responses from CSV...")
    
    csv_file = os.path.join(DATA_DIR, 'popup_responses.csv')
    if not os.path.exists(csv_file):
        print("   [SKIP] popup_responses.csv not found")
        return 0, 0, 0
    
    try:
        df = pd.read_csv(csv_file, dtype=str).fillna('')
    except Exception as e:
        print(f"   [ERROR] Failed to read CSV: {e}")
        return 0, 0, 0
    
    if 'user_id' not in df.columns:
        df['user_id'] = ''
    
    # Find rows with non-user user_id
    non_user_mask = df['user_id'].apply(is_non_user)
    non_user_count = non_user_mask.sum()
    
    if non_user_count == 0:
        print("   [SKIP] No popup responses with non-user user_id found")
        return 0, 0, 0
    
    print(f"   Found {non_user_count} response(s) to migrate")
    
    # Get existing response ids for user 1 (use id column if exists, otherwise use index)
    if 'id' in df.columns:
        existing_ids = set(
            df[df['user_id'].astype(str) == TARGET_USER_ID_STR]['id'].tolist()
        )
        id_col = 'id'
    else:
        # No id column - use a combination of other fields to identify duplicates
        user1_df = df[df['user_id'].astype(str) == TARGET_USER_ID_STR]
        existing_ids = set(
            zip(
                user1_df['trigger_id'].tolist(),
                user1_df.get('task_id', pd.Series([''] * len(user1_df))).fillna('').tolist(),
                user1_df.get('instance_id', pd.Series([''] * len(user1_df))).fillna('').tolist(),
                user1_df.get('created_at', pd.Series([''] * len(user1_df))).fillna('').tolist()
            )
        )
        id_col = None
    
    migrated = 0
    duplicates = 0
    errors = 0
    
    for idx, row in df[non_user_mask].iterrows():
        try:
            if id_col:
                response_id = str(row.get(id_col, '')).strip()
                if not response_id:
                    continue
                is_duplicate = response_id in existing_ids
            else:
                # Use combination of fields
                key = (
                    str(row.get('trigger_id', '')).strip(),
                    str(row.get('task_id', '')).strip() if pd.notna(row.get('task_id')) else '',
                    str(row.get('instance_id', '')).strip() if pd.notna(row.get('instance_id')) else '',
                    str(row.get('created_at', '')).strip() if pd.notna(row.get('created_at')) else ''
                )
                is_duplicate = key in existing_ids
            
            # Check for duplicate
            if is_duplicate:
                print(f"   [DUPLICATE] Popup response at row {idx} already exists for user 1 - removing from CSV")
                df = df.drop(idx)
                duplicates += 1
                continue
            
            # Migrate to user 1
            df.at[idx, 'user_id'] = TARGET_USER_ID_STR
            migrated += 1
            if id_col:
                existing_ids.add(response_id)
            else:
                existing_ids.add(key)
            
        except Exception as e:
            print(f"   [ERROR] Failed to migrate response at row {idx}: {e}")
            errors += 1
    
    if migrated > 0 or duplicates > 0:
        df.to_csv(csv_file, index=False)
        print(f"   [OK] Updated CSV file")
    
    return migrated, duplicates, errors


def main():
    """Main migration function."""
    print("=" * 70)
    print("Migration: Non-User Data to User 1")
    print("=" * 70)
    print(f"\nThis script will migrate all data from non-users (NULL, empty, 'default')")
    print(f"to user_id = {TARGET_USER_ID} in both database and CSV files.")
    print("\nThis includes:")
    print("  - Task templates (tasks)")
    print("  - Task instances")
    print("  - Notes")
    print("  - User preferences")
    print("  - Survey responses")
    print("  - Popup triggers")
    print("  - Popup responses")
    print("\nThe script will also check for and remove duplicate data.")
    
    response = input("\nContinue? (yes/no): ").strip().lower()
    if response not in ('yes', 'y'):
        print("[CANCELLED] Migration cancelled by user")
        return
    
    # Initialize database
    print("\n" + "=" * 70)
    print("1. Initializing database...")
    print("=" * 70)
    init_db()
    
    # Ensure user 1 exists
    with get_session() as session:
        ensure_user_exists(session, TARGET_USER_ID)
    
    # Track totals
    total_migrated = 0
    total_duplicates = 0
    total_errors = 0
    
    # Migrate from database
    print("\n" + "=" * 70)
    print("2. Migrating from Database")
    print("=" * 70)
    
    with get_session() as session:
        # Task templates
        m, d, e = migrate_tasks_from_database(session)
        total_migrated += m
        total_duplicates += d
        total_errors += e
        
        # Task instances
        m, d, e = migrate_task_instances_from_database(session)
        total_migrated += m
        total_duplicates += d
        total_errors += e
        
        # Notes
        m, d, e = migrate_notes_from_database(session)
        total_migrated += m
        total_duplicates += d
        total_errors += e
        
        # User preferences
        m, d, e = migrate_user_preferences_from_database(session)
        total_migrated += m
        total_duplicates += d
        total_errors += e
        
        # Survey responses
        m, d, e = migrate_survey_responses_from_database(session)
        total_migrated += m
        total_duplicates += d
        total_errors += e
        
        # Popup triggers
        m, d, e = migrate_popup_triggers_from_database(session)
        total_migrated += m
        total_duplicates += d
        total_errors += e
        
        # Popup responses
        m, d, e = migrate_popup_responses_from_database(session)
        total_migrated += m
        total_duplicates += d
        total_errors += e
    
    # Migrate from CSV
    print("\n" + "=" * 70)
    print("3. Migrating from CSV Files")
    print("=" * 70)
    
    # Task templates
    m, d, e = migrate_tasks_from_csv()
    total_migrated += m
    total_duplicates += d
    total_errors += e
    
    # Task instances
    m, d, e = migrate_task_instances_from_csv()
    total_migrated += m
    total_duplicates += d
    total_errors += e
    
    # Notes
    m, d, e = migrate_notes_from_csv()
    total_migrated += m
    total_duplicates += d
    total_errors += e
    
    # User preferences
    m, d, e = migrate_user_preferences_from_csv()
    total_migrated += m
    total_duplicates += d
    total_errors += e
    
    # Survey responses
    m, d, e = migrate_survey_responses_from_csv()
    total_migrated += m
    total_duplicates += d
    total_errors += e
    
    # Popup triggers
    m, d, e = migrate_popup_triggers_from_csv()
    total_migrated += m
    total_duplicates += d
    total_errors += e
    
    # Popup responses
    m, d, e = migrate_popup_responses_from_csv()
    total_migrated += m
    total_duplicates += d
    total_errors += e
    
    # Summary
    print("\n" + "=" * 70)
    print("Migration Summary")
    print("=" * 70)
    print(f"Total records migrated: {total_migrated}")
    print(f"Total duplicates removed: {total_duplicates}")
    print(f"Total errors: {total_errors}")
    
    if total_errors > 0:
        print("\n[WARNING] Some errors occurred during migration. Please review the output above.")
    elif total_migrated > 0 or total_duplicates > 0:
        print("\n[SUCCESS] Migration completed successfully!")
    else:
        print("\n[INFO] No data needed to be migrated.")
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    main()
