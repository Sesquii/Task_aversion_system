from nicegui import ui
from backend.user_state import UserStateManager
from backend.instance_manager import InstanceManager
from backend.analytics import Analytics
import json

analytics = Analytics()

user_state = UserStateManager()
DEFAULT_USER_ID = "default_user"
im = InstanceManager()

# Default cancellation categories
DEFAULT_CANCELLATION_CATEGORIES = {
    'did_while_another_active': 'Did task while another task was active',
    'deferred_to_plan': 'Deferred to plan instead of executing',
    'development_test': 'Development/test task',
    'accidental_initialization': 'Accidentally initialized',
    'failed_to_complete': 'Failed to complete task',
    'other': 'Other reason'
}


def get_all_cancellation_categories():
    """Get all cancellation categories (default + custom)."""
    custom_categories = user_state.get_cancellation_categories(DEFAULT_USER_ID)
    all_categories = {**DEFAULT_CANCELLATION_CATEGORIES, **custom_categories}
    return all_categories


@ui.page("/settings")
def settings_page():
    def go_survey():
        ui.navigate.to("/survey")
    
    # def go_data_guide():
    #     ui.navigate.to("/data-guide")

    ui.label("Settings").classes("text-2xl font-bold mb-2")
    with ui.card().classes("w-full max-w-xl p-4 gap-3"):
        ui.label("Surveys").classes("text-lg font-semibold")
        ui.button("Take Mental Health Survey", on_click=go_survey)
        ui.separator()
        ui.label("Scores & Analytics").classes("text-lg font-semibold")
        
        # Composite Score Weights
        ui.button("⚖️ Composite Score Weights", on_click=lambda: ui.navigate.to("/settings/composite-score-weights")).classes("bg-indigo-500 text-white w-full")
        ui.label("Adjust component weights for composite score calculation.").classes("text-xs text-gray-500 mb-2")
        
        # Productivity Settings Link
        ui.button("⚙️ Productivity Settings", on_click=lambda: ui.navigate.to("/settings/productivity-settings")).classes("bg-blue-500 text-white w-full")
        ui.label("Configure productivity scoring, targets, burnout thresholds, and advanced weight settings.").classes("text-xs text-gray-500")
        
        # Productivity Goal Hours Setting
        with ui.card().classes("p-3 mt-2 bg-gray-50"):
            ui.label("Productivity Goal Hours").classes("text-sm font-semibold mb-2")
            
            goal_settings = user_state.get_productivity_goal_settings(DEFAULT_USER_ID)
            current_goal = goal_settings.get('goal_hours_per_week', 30.0)
            
            goal_input = ui.number(
                label="Goal Hours Per Week",
                value=float(current_goal),
                min=0,
                max=100,
                step=0.5,
                format="%.1f"
            ).props("dense outlined").classes("w-full")
            
            # Calculate daily target
            daily_target = current_goal / 5.0  # Assume 5 work days
            ui.label(f"Daily Target: {daily_target:.1f} hours/day (assuming 5 work days)").classes("text-xs text-gray-600 mt-1")
            
            def save_goal_hours():
                new_goal = float(goal_input.value or 30.0)
                settings = {
                    'goal_hours_per_week': new_goal
                }
                # Preserve other settings
                existing = user_state.get_productivity_goal_settings(DEFAULT_USER_ID)
                settings.update(existing)
                user_state.set_productivity_goal_settings(DEFAULT_USER_ID, settings)
                ui.notify("Goal hours saved!", color="positive")
                # Update display
                daily_target_new = new_goal / 5.0
                ui.navigate.reload()
            
            ui.button("Save Goal Hours", on_click=save_goal_hours).classes("bg-green-500 text-white mt-2 w-full")
            ui.label("This setting is used throughout the system for productivity potential calculations and volume targets.").classes("text-xs text-gray-500 mt-1")
        
        ui.separator()
        ui.label("Data & Export").classes("text-lg font-semibold")
        
        def export_csv():
            """Export all database data and user preferences to CSV files."""
            try:
                from backend.csv_export import export_all_data_to_csv, get_export_summary
                import os
                
                data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
                
                export_counts, exported_files = export_all_data_to_csv(
                    data_dir=data_dir,
                    include_user_preferences=True
                )
                
                summary = get_export_summary(export_counts)
                file_list = "\n".join([f"  - {os.path.basename(f)}" for f in exported_files])
                
                message = f"Data exported successfully!\n\n{summary}\n\nFiles saved to:\n{data_dir}\n\nExported files:\n{file_list}"
                ui.notify(message, color="positive", timeout=10000)
                
            except Exception as e:
                import traceback
                error_msg = str(e)
                ui.notify(f"Error exporting data: {error_msg}", color="negative")
                print(f"[Settings] Export error: {traceback.format_exc()}")
        
        def download_zip():
            """Create ZIP file and trigger browser download."""
            try:
                from backend.csv_export import create_data_zip
                import os
                
                zip_path = create_data_zip()
                zip_filename = os.path.basename(zip_path)
                
                # Read zip file content
                with open(zip_path, 'rb') as f:
                    zip_content = f.read()
                
                # Trigger download
                ui.download(zip_content, filename=zip_filename)
                ui.notify(f"Download started: {zip_filename}", color="positive")
                
                # Clean up temp file after a delay
                import threading
                def cleanup():
                    import time
                    time.sleep(5)  # Wait 5 seconds before cleanup
                    try:
                        if os.path.exists(zip_path):
                            os.remove(zip_path)
                    except Exception:
                        pass
                
                threading.Thread(target=cleanup, daemon=True).start()
                
            except Exception as e:
                import traceback
                error_msg = str(e)
                ui.notify(f"Error creating download: {error_msg}", color="negative")
                print(f"[Settings] Download error: {traceback.format_exc()}")
        
        def handle_upload(e):
            """
            Handle ZIP file upload and import data.
            
            NOTE: This function is currently disabled for security testing.
            The code is preserved but the upload component is disabled in the UI.
            To re-enable: Remove the disabled prop and set_enabled(False) call.
            """
            # SECURITY: Feature disabled pending security audit
            ui.notify(
                "Import feature is currently disabled for security testing. "
                "Please contact administrator for data import assistance.",
                color="negative",
                timeout=8000
            )
            return
            
            # Code below is preserved for future security testing and re-enablement
            # DO NOT DELETE - This will be tested and re-enabled after security audit
            try:
                from backend.csv_import import import_from_zip
                from nicegui import events
                import tempfile
                import os
                
                # Read uploaded file content
                if isinstance(e, events.UploadEventArguments):
                    file_content = e.content.read()
                else:
                    # Fallback for different event structures
                    file_content = e.content.read() if hasattr(e.content, 'read') else e.content
                
                # Save uploaded file to temp location
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
                temp_file.write(file_content)
                temp_file.close()
                
                try:
                    # Import data
                    results = import_from_zip(temp_file.name, skip_existing=True)
                    
                    # Build summary message
                    summary_lines = ["Import completed:"]
                    total_imported = 0
                    total_skipped = 0
                    total_errors = 0
                    
                    for table_name, stats in results.items():
                        imported = stats.get('imported', 0)
                        skipped = stats.get('skipped', 0)
                        errors = stats.get('errors', 0)
                        total_imported += imported
                        total_skipped += skipped
                        total_errors += errors
                        
                        if imported > 0 or skipped > 0 or errors > 0:
                            summary_lines.append(f"  {table_name}: {imported} imported, {skipped} skipped, {errors} errors")
                        elif 'note' in stats:
                            summary_lines.append(f"  {table_name}: {stats['note']}")
                    
                    summary_lines.append(f"\nTotal: {total_imported} imported, {total_skipped} skipped, {total_errors} errors")
                    
                    message = "\n".join(summary_lines)
                    ui.notify(message, color="positive", timeout=10000)
                    
                    # Reload page to show updated data
                    ui.navigate.reload()
                    
                finally:
                    # Clean up temp file
                    try:
                        if os.path.exists(temp_file.name):
                            os.remove(temp_file.name)
                    except Exception:
                        pass
                
            except Exception as ex:
                import traceback
                error_msg = str(ex)
                ui.notify(f"Error importing data: {error_msg}", color="negative")
                print(f"[Settings] Import error: {traceback.format_exc()}")
        
        ui.button("📥 Export Data to CSV", on_click=export_csv).classes("bg-green-500 text-white mt-2")
        ui.label("Export all database data (tasks, instances, emotions, popup triggers/responses, notes) and user preferences to CSV files in the data/ folder.").classes("text-sm text-gray-600 mt-2")
        
        ui.button("💾 Download Data as ZIP", on_click=download_zip).classes("bg-blue-500 text-white mt-2")
        ui.label("Download all your data as a ZIP file containing all CSV files. Use this for backup or to transfer data to another device.").classes("text-sm text-gray-600 mt-2")
        
        # Security warning and disabled import feature
        with ui.card().classes("p-4 mt-2 bg-red-50 border-2 border-red-300"):
            ui.label("⚠️ IMPORT FEATURE TEMPORARILY DISABLED").classes("text-base font-bold text-red-700 mb-2")
            ui.markdown(
                "**Security Notice**: The data import feature has been temporarily disabled pending security testing.\n\n"
                "This feature allows importing CSV data and automatically adding database columns, which requires "
                "thorough security review to prevent exploitation before being enabled in production.\n\n"
                "**Status**: Code is preserved but functionality is disabled until security audit is complete."
            ).classes("text-sm text-red-800 mb-3")
            
            # Disabled upload component
            upload_component = ui.upload(
                on_upload=lambda e: ui.notify("Import feature is currently disabled for security testing.", color="negative"),
                max_file_size=50 * 1024 * 1024,  # 50 MB limit
                label="📤 Import Data from ZIP (DISABLED)",
                auto_upload=False
            ).classes("mt-2 opacity-50").props("accept=.zip disabled")
            upload_component.set_enabled(False)
            
            ui.label("Upload functionality is disabled. The underlying import code is preserved for future security testing.").classes("text-xs text-red-700 mt-2 italic")
        
        # Abuse prevention limits info (for reference when feature is re-enabled)
        with ui.card().classes("p-3 mt-2 bg-gray-50 border border-gray-200"):
            ui.label("Planned Import Limits (When Re-enabled)").classes("text-sm font-semibold mb-2 text-gray-600")
            ui.markdown(
                "• **File size**: Maximum 50 MB per file\n"
                "• **Rows per CSV**: Maximum 10,000 rows (excess truncated)\n"
                "• **New columns**: Maximum 10 new columns per import\n"
                "• **Total columns**: Maximum 100 columns per table\n"
                "• **ZIP files**: Maximum 20 files per archive\n"
                "• **Column names**: Must be alphanumeric with underscores only"
            ).classes("text-xs text-gray-600")
        
        ui.markdown("- **Data Guide**: Currently missing - documentation for local setup, data backup, and troubleshooting is planned but not yet implemented").classes("text-sm text-gray-600 mt-2")
    
    # Task Editing Management Section
    ui.separator().classes("my-4")
    with ui.card().classes("w-full max-w-xl p-4 gap-3"):
        ui.label("Task Editing").classes("text-lg font-semibold")
        ui.button("✏️ Task Editing Manager", on_click=lambda: ui.navigate.to("/task-editing-manager")).classes("bg-blue-500 text-white w-full")
        ui.label("Edit completed and cancelled task instances. Navigate between initialization and completion pages for completed tasks.").classes("text-sm text-gray-600 mt-2")
        
        ui.button("⚠️ Cancellation Penalty Weights", on_click=lambda: ui.navigate.to("/settings/cancellation-penalties")).classes("bg-orange-500 text-white w-full mt-2")
        ui.label("Configure productivity penalties for different cancellation reasons.").classes("text-xs text-gray-500")
