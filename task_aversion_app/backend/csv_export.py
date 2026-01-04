# backend/csv_export.py
"""
Comprehensive CSV export utility for database tables and user preferences.
Can be used by settings page and migration scripts.
"""
import os
import pandas as pd
import zipfile
import tempfile
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from pathlib import Path

from backend.database import (
    get_session, Task, TaskInstance, Emotion, 
    PopupTrigger, PopupResponse, Note
)
from backend.user_state import UserStateManager, PREFS_FILE


def export_all_data_to_csv(
    data_dir: Optional[str] = None,
    include_user_preferences: bool = True
) -> Tuple[Dict[str, int], List[str]]:
    """
    Export all database tables and user preferences to CSV files.
    
    Args:
        data_dir: Directory to save CSV files. If None, uses default data directory.
        include_user_preferences: Whether to export user_preferences.csv
    
    Returns:
        Tuple of (export_counts dict, list of exported file paths)
        export_counts: Dictionary mapping table names to number of records exported
        exported_files: List of file paths that were created
    
    Raises:
        Exception: If export fails
    """
    if data_dir is None:
        data_dir = os.path.join(Path(__file__).resolve().parent.parent, "data")
    
    os.makedirs(data_dir, exist_ok=True)
    
    export_counts = {}
    exported_files = []
    session = get_session()
    
    try:
        # Export Tasks
        tasks = session.query(Task).all()
        if tasks:
            tasks_data = [task.to_dict() for task in tasks]
            tasks_df = pd.DataFrame(tasks_data)
            tasks_file = os.path.join(data_dir, 'tasks.csv')
            tasks_df.to_csv(tasks_file, index=False, encoding='utf-8')
            export_counts['tasks'] = len(tasks)
            exported_files.append(tasks_file)
        else:
            export_counts['tasks'] = 0
        
        # Export TaskInstances
        instances = session.query(TaskInstance).all()
        if instances:
            instances_data = [instance.to_dict() for instance in instances]
            instances_df = pd.DataFrame(instances_data)
            instances_file = os.path.join(data_dir, 'task_instances.csv')
            instances_df.to_csv(instances_file, index=False, encoding='utf-8')
            export_counts['task_instances'] = len(instances)
            exported_files.append(instances_file)
        else:
            export_counts['task_instances'] = 0
        
        # Export Emotions
        emotions = session.query(Emotion).all()
        if emotions:
            emotions_data = [emotion.to_dict() for emotion in emotions]
            emotions_df = pd.DataFrame(emotions_data)
            emotions_file = os.path.join(data_dir, 'emotions.csv')
            emotions_df.to_csv(emotions_file, index=False, encoding='utf-8')
            export_counts['emotions'] = len(emotions)
            exported_files.append(emotions_file)
        else:
            export_counts['emotions'] = 0
        
        # Export PopupTriggers
        popup_triggers = session.query(PopupTrigger).all()
        if popup_triggers:
            triggers_data = [trigger.to_dict() for trigger in popup_triggers]
            triggers_df = pd.DataFrame(triggers_data)
            triggers_file = os.path.join(data_dir, 'popup_triggers.csv')
            triggers_df.to_csv(triggers_file, index=False, encoding='utf-8')
            export_counts['popup_triggers'] = len(popup_triggers)
            exported_files.append(triggers_file)
        else:
            export_counts['popup_triggers'] = 0
        
        # Export PopupResponses
        popup_responses = session.query(PopupResponse).all()
        if popup_responses:
            responses_data = [response.to_dict() for response in popup_responses]
            responses_df = pd.DataFrame(responses_data)
            responses_file = os.path.join(data_dir, 'popup_responses.csv')
            responses_df.to_csv(responses_file, index=False, encoding='utf-8')
            export_counts['popup_responses'] = len(popup_responses)
            exported_files.append(responses_file)
        else:
            export_counts['popup_responses'] = 0
        
        # Export Notes
        notes = session.query(Note).all()
        if notes:
            notes_data = [note.to_dict() for note in notes]
            notes_df = pd.DataFrame(notes_data)
            notes_file = os.path.join(data_dir, 'notes.csv')
            notes_df.to_csv(notes_file, index=False, encoding='utf-8')
            export_counts['notes'] = len(notes)
            exported_files.append(notes_file)
        else:
            export_counts['notes'] = 0
        
        # Export user preferences (CSV file, not database table)
        if include_user_preferences:
            prefs_file = PREFS_FILE
            if os.path.exists(prefs_file):
                # Copy user_preferences.csv to data_dir if it's not already there
                if os.path.dirname(prefs_file) != data_dir:
                    import shutil
                    dest_prefs_file = os.path.join(data_dir, 'user_preferences.csv')
                    shutil.copy2(prefs_file, dest_prefs_file)
                    exported_files.append(dest_prefs_file)
                else:
                    exported_files.append(prefs_file)
                
                # Count rows
                try:
                    prefs_df = pd.read_csv(prefs_file)
                    export_counts['user_preferences'] = len(prefs_df)
                except Exception:
                    export_counts['user_preferences'] = 0
            else:
                export_counts['user_preferences'] = 0
        
    finally:
        session.close()
    
    return export_counts, exported_files


def get_export_summary(export_counts: Dict[str, int]) -> str:
    """
    Generate a human-readable summary of export results.
    
    Args:
        export_counts: Dictionary mapping table names to record counts
    
    Returns:
        Formatted summary string
    """
    lines = []
    total_records = 0
    
    for table_name, count in sorted(export_counts.items()):
        lines.append(f"  - {table_name}: {count} record(s)")
        total_records += count
    
    lines.insert(0, f"Exported {len(export_counts)} table(s) with {total_records} total record(s):")
    return "\n".join(lines)


def create_data_zip(data_dir: Optional[str] = None) -> str:
    """
    Create a ZIP file containing all CSV data files.
    
    Args:
        data_dir: Directory containing CSV files. If None, uses default data directory.
    
    Returns:
        Path to the created ZIP file
    
    Raises:
        Exception: If ZIP creation fails
    """
    if data_dir is None:
        data_dir = os.path.join(Path(__file__).resolve().parent.parent, "data")
    
    # First, ensure all data is exported to CSV
    export_counts, exported_files = export_all_data_to_csv(
        data_dir=data_dir,
        include_user_preferences=True
    )
    
    # Create ZIP file in temp directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"task_aversion_data_{timestamp}.zip"
    temp_dir = tempfile.gettempdir()
    zip_path = os.path.join(temp_dir, zip_filename)
    
    # Create ZIP with all exported files
    files_added = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in exported_files:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                # Add file to zip with just the filename (not full path)
                zipf.write(file_path, os.path.basename(file_path))
                files_added += 1
    
    if files_added == 0:
        raise ValueError("No data files to include in ZIP archive")
    
    return zip_path
