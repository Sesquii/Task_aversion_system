from nicegui import ui, app
from backend.user_state import UserStateManager
from backend.instance_manager import InstanceManager
from backend.analytics import Analytics
from backend.auth import get_current_user, logout
from ui.error_reporting import handle_error_with_ui
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
    from backend.auth import get_current_user
    current_user_id = get_current_user()
    user_id_str = str(current_user_id) if current_user_id is not None else DEFAULT_USER_ID
    
    custom_categories = user_state.get_cancellation_categories(user_id_str)
    all_categories = {**DEFAULT_CANCELLATION_CATEGORIES, **custom_categories}
    return all_categories


@ui.page("/settings")
def settings_page():
    # Check authentication
    user_id = get_current_user()
    if user_id is None:
        ui.navigate.to('/login')
        return

    try:
        _build_settings_content(user_id)
    except Exception as ex:
        import traceback
        traceback.print_exc()
        ui.label("Settings").classes("text-2xl font-bold mb-2")
        with ui.card().classes("w-full max-w-xl p-4 border-2 border-red-300 bg-red-50"):
            ui.label("Error loading Settings page").classes("text-lg font-semibold text-red-700 mb-2")
            ui.label(str(ex)).classes("text-sm text-red-800 mb-2")
            ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("mt-2")


def _build_settings_content(user_id):
    """Build the main settings page content (separate so we can wrap in try/except)."""
    def go_survey():
        ui.navigate.to("/survey")

    def handle_logout():
        """Logout and redirect to login page."""
        # Clear session
        success = logout()
        if success:
            ui.notify("Logged out successfully", color="positive")
        else:
            ui.notify("Error during logout", color="negative")
        
        # Clear localStorage via JavaScript and force full page reload
        ui.run_javascript('''
            try {
                if (window.localStorage) {
                    localStorage.removeItem('session_token');
                    localStorage.removeItem('tas_user_id');
                    localStorage.removeItem('user_id');
                    localStorage.removeItem('login_redirect');
                }
            } catch(e) {
                console.log('Error clearing localStorage:', e);
            }
            window.location.href = "/login";
        ''')
    
    # def go_data_guide():
    #     ui.navigate.to("/data-guide")

    ui.label("Settings").classes("text-2xl font-bold mb-2")
    
    # Logout button at the top
    with ui.card().classes("w-full max-w-xl p-4 gap-3 mb-4 bg-red-50 border-2 border-red-200"):
        ui.label("Account").classes("text-lg font-semibold text-red-700")
        ui.button("Logout", on_click=handle_logout, color='red').classes("w-full")
        ui.label("Log out of your account. You will need to log in again to access your data.").classes("text-xs text-gray-600 mt-1")

    # Interface (this device): mobile vs desktop layout
    with ui.card().classes("w-full max-w-xl p-4 gap-3 mb-4"):
        ui.label("Interface (this device)").classes("text-lg font-semibold")
        ui.label("Choose layout for this device only. Your phone and computer can use different layouts.").classes("text-sm text-gray-600")
        current_mode = app.storage.browser.get("ui_mode") or "desktop"

        def set_ui_mode(mode: str):
            # Reload via choose-experience so app follows same logic as initial selection after login
            ui.run_javascript(f'window.location.href = "/choose-experience?preselect={mode}";')

        with ui.row().classes("gap-2"):
            ui.button(
                "Desktop",
                icon="computer",
                on_click=lambda: set_ui_mode("desktop"),
            ).classes("flex-1")
            ui.button(
                "Mobile",
                icon="phone_android",
                on_click=lambda: set_ui_mode("mobile"),
            ).classes("flex-1")
        ui.label(f"Current: {current_mode.capitalize()}").classes("text-xs text-gray-500")
        ui.label("Click a button to switch and go to the dashboard.").classes("text-xs text-gray-500")

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
            
            # Get user_id for data isolation
            current_user_id_str = str(user_id) if user_id is not None else DEFAULT_USER_ID
            goal_settings = user_state.get_productivity_goal_settings(current_user_id_str)
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
                existing = user_state.get_productivity_goal_settings(current_user_id_str)
                settings.update(existing)
                user_state.set_productivity_goal_settings(current_user_id_str, settings)
                ui.notify("Goal hours saved!", color="positive")
                # Update display
                daily_target_new = new_goal / 5.0
                ui.navigate.reload()
            
            ui.button("Save Goal Hours", on_click=save_goal_hours).classes("bg-green-500 text-white mt-2 w-full")
            ui.label("This setting is used throughout the system for productivity potential calculations and volume targets.").classes("text-xs text-gray-500 mt-1")
        
        ui.separator()
        ui.label("Data & Export").classes("text-lg font-semibold")
        
        def download_zip():
            """Create ZIP file and trigger browser download."""
            try:
                from backend.csv_export import create_data_zip
                import os
                import tempfile
                from pathlib import Path
                
                # CRITICAL: Get current logged-in user_id for data isolation
                current_user_id = get_current_user()
                if current_user_id is None:
                    ui.notify("You must be logged in to export data.", color="negative")
                    return
                
                # Create ZIP file - pass user_id to ensure users can only export their own data
                zip_path = create_data_zip(user_id=current_user_id)
                zip_filename = os.path.basename(zip_path)
                
                # Read zip file content as bytes
                with open(zip_path, 'rb') as f:
                    zip_content = f.read()
                
                # Use NiceGUI's download function with bytes
                # ui.download accepts (source, filename) where source can be bytes, path, or URL
                ui.download(zip_content, filename=zip_filename)
                
                ui.notify(f"Download started: {zip_filename}", color="positive", timeout=3000)
                
                # Clean up temp file after a delay (give browser time to download)
                import threading
                def cleanup():
                    import time
                    time.sleep(10)  # Wait 10 seconds before cleanup to allow download to complete
                    try:
                        if os.path.exists(zip_path):
                            os.remove(zip_path)
                            print(f"[Settings] Cleaned up temp file: {zip_path}")
                    except Exception as e:
                        print(f"[Settings] Error cleaning up temp file: {e}")
                
                threading.Thread(target=cleanup, daemon=True).start()
                
            except Exception as e:
                handle_error_with_ui(
                    'download_user_data',
                    e,
                    user_id=get_current_user(),
                    context={'action': 'download_zip'}
                )
        
        async def handle_upload(e):
            """Handle ZIP file upload and import data into the current database."""
            try:
                from backend.csv_import import import_from_zip
                from nicegui import events
                import tempfile
                import os
                
                # NiceGUI 3.x: UploadEventArguments has .file (FileUpload), not .content
                if not isinstance(e, events.UploadEventArguments) or e.file is None:
                    ui.notify("Invalid upload event.", color="negative")
                    return
                # Save uploaded file to temp location (FileUpload has async save/read)
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
                temp_file.close()
                try:
                    await e.file.save(temp_file.name)
                except Exception as save_ex:
                    try:
                        if os.path.exists(temp_file.name):
                            os.remove(temp_file.name)
                    except Exception:
                        pass
                    handle_error_with_ui(
                        'import_user_data',
                        save_ex,
                        user_id=get_current_user(),
                        context={'action': 'import_zip', 'step': 'save_upload'}
                    )
                    return
                try:
                    # CRITICAL: Get current logged-in user_id for data isolation
                    current_user_id = get_current_user()
                    if current_user_id is None:
                        ui.notify("You must be logged in to import data.", color="negative")
                        return
                    
                    # Import data - pass user_id to ensure users can only import their own data
                    results = import_from_zip(temp_file.name, skip_existing=True, user_id=current_user_id)
                    
                    # Build summary message
                    summary_lines = ["Import completed:"]
                    total_imported = 0
                    total_skipped = 0
                    total_errors = 0
                    
                    for table_name, stats in results.items():
                        if table_name.startswith('_'):  # Skip internal keys like _error, _backup_info
                            continue
                        imported = stats.get('imported', 0)
                        skipped = stats.get('skipped', 0)
                        errors = stats.get('errors', 0)
                        total_imported += imported
                        total_skipped += skipped
                        total_errors += errors
                        
                        if 'error' in stats:
                            summary_lines.append(f"  {table_name}: FAILED - {stats['error']}")
                        elif imported > 0 or skipped > 0 or errors > 0:
                            summary_lines.append(f"  {table_name}: {imported} imported, {skipped} skipped, {errors} errors")
                        elif 'note' in stats:
                            summary_lines.append(f"  {table_name}: {stats['note']}")
                    
                    summary_lines.append(f"\nTotal: {total_imported} imported, {total_skipped} skipped, {total_errors} errors")
                    
                    message = "\n".join(summary_lines)
                    has_failures = any(
                        isinstance(s, dict) and s.get('error')
                        for k, s in results.items() if not k.startswith('_')
                    )
                    ui.notify(message, color="negative" if has_failures else "positive", timeout=10000)
                    
                    # Invalidate caches so dashboard/analytics show newly imported data (including initialized/active instances)
                    try:
                        im._invalidate_instance_caches()
                        from backend.analytics import Analytics
                        Analytics()._invalidate_instances_cache(user_id=current_user_id)
                    except Exception:
                        pass
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
                handle_error_with_ui(
                    'import_user_data',
                    ex,
                    user_id=get_current_user(),
                    context={'action': 'import_zip'}
                )
        
        ui.button("💾 Download My Data", on_click=download_zip).classes("bg-blue-500 text-white mt-2")
        ui.label("Download all your data as a ZIP file containing CSV files (tasks, instances, emotions, popup triggers/responses, notes, survey responses, and user preferences). Export includes all task statuses: initialized, active, and completed. Use for backup or to transfer data to another device.").classes("text-sm text-gray-600 mt-2")
        
        # Import from ZIP (writes to current database; user_id used for data isolation)
        with ui.card().classes("p-4 mt-2 bg-gray-50 border border-gray-200"):
            ui.label("Import Data from ZIP").classes("text-base font-semibold mb-2")
            ui.label(
                "Upload a ZIP file containing CSV exports (e.g. from Download My Data). "
                "All data (initialized, active, and completed tasks) is imported and associated with your account."
            ).classes("text-sm text-gray-600 mb-3")
            ui.upload(
                on_upload=handle_upload,
                max_file_size=50 * 1024 * 1024,  # 50 MB limit
                label="Choose ZIP file to import",
                auto_upload=True
            ).classes("mt-2").props("accept=.zip")
        
        # Import limits
        with ui.card().classes("p-3 mt-2 bg-gray-50 border border-gray-200"):
            ui.label("Import Limits").classes("text-sm font-semibold mb-2 text-gray-600")
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
