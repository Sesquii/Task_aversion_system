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
    PopupTrigger, PopupResponse, Note, SurveyResponse
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
        # Export Tasks (always create file, even if empty)
        tasks = session.query(Task).all()
        tasks_file = os.path.join(data_dir, 'tasks.csv')
        if tasks:
            tasks_data = [task.to_dict() for task in tasks]
            tasks_df = pd.DataFrame(tasks_data)
            tasks_df.to_csv(tasks_file, index=False, encoding='utf-8')
            export_counts['tasks'] = len(tasks)
        else:
            # Create empty CSV with header from Task model
            tasks_df = pd.DataFrame(columns=['task_id', 'name', 'description', 'type', 'version', 'created_at', 
                                             'is_recurring', 'categories', 'default_estimate_minutes', 'task_type',
                                             'default_initial_aversion', 'routine_frequency', 'routine_days_of_week',
                                             'routine_time', 'completion_window_hours', 'completion_window_days', 
                                             'notes', 'user_id'])
            tasks_df.to_csv(tasks_file, index=False, encoding='utf-8')
            export_counts['tasks'] = 0
        exported_files.append(tasks_file)
        
        # Export TaskInstances (always create file, even if empty)
        instances = session.query(TaskInstance).all()
        instances_file = os.path.join(data_dir, 'task_instances.csv')
        if instances:
            instances_data = [instance.to_dict() for instance in instances]
            instances_df = pd.DataFrame(instances_data)
            instances_df.to_csv(instances_file, index=False, encoding='utf-8')
            export_counts['task_instances'] = len(instances)
        else:
            # Create empty CSV with header from TaskInstance model
            instances_df = pd.DataFrame(columns=['instance_id', 'task_id', 'task_name', 'task_version', 'created_at',
                                                 'initialized_at', 'started_at', 'completed_at', 'cancelled_at',
                                                 'predicted', 'actual', 'procrastination_score', 'proactive_score',
                                                 'behavioral_score', 'net_relief', 'behavioral_deviation', 'is_completed',
                                                 'is_deleted', 'status', 'duration_minutes', 'delay_minutes', 
                                                 'relief_score', 'cognitive_load', 'mental_energy_needed', 
                                                 'task_difficulty', 'emotional_load', 'environmental_effect',
                                                 'skills_improved', 'serendipity_factor', 'disappointment_factor', 'user_id'])
            instances_df.to_csv(instances_file, index=False, encoding='utf-8')
            export_counts['task_instances'] = 0
        exported_files.append(instances_file)
        
        # Export Emotions (always create file, even if empty)
        emotions = session.query(Emotion).all()
        emotions_file = os.path.join(data_dir, 'emotions.csv')
        if emotions:
            emotions_data = [emotion.to_dict() for emotion in emotions]
            emotions_df = pd.DataFrame(emotions_data)
            emotions_df.to_csv(emotions_file, index=False, encoding='utf-8')
            export_counts['emotions'] = len(emotions)
        else:
            # Create empty CSV with header from Emotion model
            emotions_df = pd.DataFrame(columns=['emotion'])
            emotions_df.to_csv(emotions_file, index=False, encoding='utf-8')
            export_counts['emotions'] = 0
        exported_files.append(emotions_file)
        
        # Export PopupTriggers (always create file, even if empty)
        popup_triggers = session.query(PopupTrigger).all()
        triggers_file = os.path.join(data_dir, 'popup_triggers.csv')
        if popup_triggers:
            triggers_data = [trigger.to_dict() for trigger in popup_triggers]
            triggers_df = pd.DataFrame(triggers_data)
            triggers_df.to_csv(triggers_file, index=False, encoding='utf-8')
            export_counts['popup_triggers'] = len(popup_triggers)
        else:
            # Create empty CSV with header from PopupTrigger model
            triggers_df = pd.DataFrame(columns=['id', 'user_id', 'trigger_id', 'task_id', 'count', 'last_shown_at',
                                                'helpful', 'last_response', 'last_comment', 'created_at', 'updated_at'])
            triggers_df.to_csv(triggers_file, index=False, encoding='utf-8')
            export_counts['popup_triggers'] = 0
        exported_files.append(triggers_file)
        
        # Export PopupResponses (always create file, even if empty)
        popup_responses = session.query(PopupResponse).all()
        responses_file = os.path.join(data_dir, 'popup_responses.csv')
        if popup_responses:
            responses_data = [response.to_dict() for response in popup_responses]
            responses_df = pd.DataFrame(responses_data)
            responses_df.to_csv(responses_file, index=False, encoding='utf-8')
            export_counts['popup_responses'] = len(popup_responses)
        else:
            # Create empty CSV with header from PopupResponse model
            responses_df = pd.DataFrame(columns=['id', 'user_id', 'trigger_id', 'task_id', 'instance_id', 
                                                 'response_value', 'helpful', 'comment', 'context', 'created_at'])
            responses_df.to_csv(responses_file, index=False, encoding='utf-8')
            export_counts['popup_responses'] = 0
        exported_files.append(responses_file)
        
        # Export Notes (always create file, even if empty)
        notes = session.query(Note).all()
        notes_file = os.path.join(data_dir, 'notes.csv')
        if notes:
            notes_data = [note.to_dict() for note in notes]
            notes_df = pd.DataFrame(notes_data)
            notes_df.to_csv(notes_file, index=False, encoding='utf-8')
            export_counts['notes'] = len(notes)
        else:
            # Create empty CSV with header from Note model
            notes_df = pd.DataFrame(columns=['note_id', 'content', 'timestamp', 'user_id'])
            notes_df.to_csv(notes_file, index=False, encoding='utf-8')
            export_counts['notes'] = 0
        exported_files.append(notes_file)
        
        # Export SurveyResponses (always create file, even if empty)
        survey_responses = session.query(SurveyResponse).all()
        survey_responses_file = os.path.join(data_dir, 'survey_responses.csv')
        if survey_responses:
            responses_data = [response.to_dict() for response in survey_responses]
            responses_df = pd.DataFrame(responses_data)
            responses_df.to_csv(survey_responses_file, index=False, encoding='utf-8')
            export_counts['survey_responses'] = len(survey_responses)
        else:
            # Create empty CSV with header from SurveyResponse model
            responses_df = pd.DataFrame(columns=['user_id', 'response_id', 'question_category', 'question_id', 
                                                 'response_value', 'response_text', 'timestamp'])
            responses_df.to_csv(survey_responses_file, index=False, encoding='utf-8')
            export_counts['survey_responses'] = 0
        exported_files.append(survey_responses_file)
        
        # Export user preferences (CSV file, not database table) - always create if include_user_preferences is True
        if include_user_preferences:
            prefs_file = PREFS_FILE
            dest_prefs_file = os.path.join(data_dir, 'user_preferences.csv')
            if os.path.exists(prefs_file):
                # Copy user_preferences.csv to data_dir if it's not already there
                if os.path.dirname(prefs_file) != data_dir:
                    import shutil
                    shutil.copy2(prefs_file, dest_prefs_file)
                else:
                    # If it's already in data_dir, just use it
                    dest_prefs_file = prefs_file
                
                # Count rows
                try:
                    prefs_df = pd.read_csv(prefs_file)
                    export_counts['user_preferences'] = len(prefs_df)
                except Exception:
                    export_counts['user_preferences'] = 0
                exported_files.append(dest_prefs_file)
            else:
                # Create empty user_preferences.csv with header (for completeness)
                prefs_df = pd.DataFrame(columns=['user_id', 'tutorial_completed', 'tutorial_choice', 'tutorial_auto_show',
                                                 'tooltip_mode_enabled', 'survey_completed', 'created_at', 'last_active',
                                                 'gap_handling', 'persistent_emotion_values', 'productivity_history',
                                                 'productivity_goal_settings', 'monitored_metrics_config',
                                                 'execution_score_chunk_state', 'productivity_settings'])
                prefs_df.to_csv(dest_prefs_file, index=False, encoding='utf-8')
                export_counts['user_preferences'] = 0
                exported_files.append(dest_prefs_file)
        
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
    
    # Create ZIP with all exported files (include empty files too for completeness)
    files_added = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in exported_files:
            if os.path.exists(file_path):
                # Add file to zip with just the filename (not full path)
                # Include empty files too (e.g., empty survey_responses.csv with headers)
                zipf.write(file_path, os.path.basename(file_path))
                files_added += 1
    
    if files_added == 0:
        raise ValueError("No data files to include in ZIP archive")
    
    return zip_path
