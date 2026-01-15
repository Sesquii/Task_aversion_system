# ui/notes_page.py
from nicegui import ui
from backend.notes_manager import NotesManager
from backend.auth import get_current_user
from datetime import datetime

notes_manager = NotesManager()


@ui.page('/notes')
def notes_page():
    """Notes page for behavioral and emotional pattern observations."""
    
    # Get current user ID
    user_id = get_current_user()
    if user_id is None:
        ui.navigate.to('/login')
        return
    
    ui.label("Notes").classes("text-2xl font-bold mb-2")
    ui.label("Draft notes on behavioral and emotional patterns, or observations from analytics.").classes(
        "text-gray-500 mb-4"
    )
    
    notes_container = ui.column().classes("w-full max-w-4xl gap-4")
    
    def refresh_notes():
        """Refresh the notes display."""
        notes_container.clear()
        
        # Create new note section
        with notes_container:
            with ui.card().classes("w-full p-6"):
                ui.label("New Note").classes("text-lg font-semibold mb-2")
                note_input = ui.textarea(
                    label="Note Content",
                    placeholder="Enter your observation about behavioral or emotional patterns, or analytics insights..."
                ).classes("w-full").props("rows=4")
                
                def save_note():
                    content = note_input.value.strip()
                    if not content:
                        ui.notify("Note content cannot be empty.", color="negative")
                        return
                    notes_manager.add_note(content, user_id=user_id)
                    note_input.value = ""
                    ui.notify("Note saved.", color="positive")
                    refresh_notes()
                
                ui.button("Save Note", on_click=save_note, icon="save").classes("mt-2")
            
            ui.separator().classes("my-4")
            
            # Display existing notes
            ui.label("All Notes").classes("text-lg font-semibold mb-2")
            
            all_notes = notes_manager.get_all_notes(user_id=user_id)
            if not all_notes:
                ui.label("No notes yet. Create your first note above.").classes("text-gray-500 italic")
            else:
                for note in all_notes:
                    with ui.card().classes("w-full p-4"):
                        with ui.column().classes("w-full gap-2"):
                            # Note content
                            ui.markdown(note.get("content", "")).classes("text-base")
                            
                            # Timestamp and delete button
                            with ui.row().classes("w-full justify-between items-center"):
                                # Format timestamp
                                timestamp_str = note.get("timestamp", "")
                                formatted_time = ""
                                if timestamp_str:
                                    try:
                                        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                                        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                                    except (ValueError, AttributeError):
                                        formatted_time = timestamp_str
                                
                                ui.label(f"Created: {formatted_time}").classes("text-xs text-gray-500")
                                
                                def delete_note_handler(note_id=note.get("note_id")):
                                    if notes_manager.delete_note(note_id, user_id=user_id):
                                        ui.notify("Note deleted.", color="positive")
                                        refresh_notes()
                                    else:
                                        ui.notify("Failed to delete note.", color="negative")
                                
                                ui.button("Delete", on_click=delete_note_handler, icon="delete").classes("text-sm").props("flat")
    
    refresh_notes()
