import os
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


DATA_DIR = os.path.join(Path(__file__).resolve().parent.parent, "data")
os.makedirs(DATA_DIR, exist_ok=True)

NOTES_FILE = os.path.join(DATA_DIR, "notes.csv")


class NotesManager:
    """Notes storage for behavioral and emotional patterns. Supports both CSV and database backends."""

    def __init__(self, notes_file: Optional[str] = None):
        # Store file path for CSV backend (if needed)
        self.file = notes_file or NOTES_FILE
        
        # Default to database (SQLite) unless USE_CSV is explicitly set
        use_csv = os.getenv('USE_CSV', '').lower() in ('1', 'true', 'yes')
        
        if use_csv:
            # CSV backend (explicitly requested)
            self.use_db = False
        else:
            # Database backend (default)
            if not os.getenv('DATABASE_URL'):
                os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'
            self.use_db = True
        
        # Strict mode: If DISABLE_CSV_FALLBACK is set, fail instead of falling back to CSV
        self.strict_mode = bool(os.getenv('DISABLE_CSV_FALLBACK', '').lower() in ('1', 'true', 'yes'))
        
        if self.use_db:
            # Database backend
            try:
                from backend.database import get_session, Note, init_db
                self.db_session = get_session
                self.Note = Note
                init_db()
                if not getattr(NotesManager, '_printed_backend', False):
                    print("[NotesManager] Using database backend")
                    NotesManager._printed_backend = True
            except Exception as e:
                if self.strict_mode:
                    raise RuntimeError(
                        f"Database initialization failed and CSV fallback is disabled: {e}\n"
                        "Set DISABLE_CSV_FALLBACK=false or unset DATABASE_URL to allow CSV fallback."
                    ) from e
                print(f"[NotesManager] Database initialization failed: {e}, falling back to CSV")
                self.use_db = False
                self._init_csv()
        else:
            # CSV backend (explicitly requested via USE_CSV)
            if self.strict_mode:
                raise RuntimeError(
                    "CSV backend is disabled (DISABLE_CSV_FALLBACK is set) but USE_CSV is set.\n"
                    "Please unset USE_CSV to use the database backend, or unset DISABLE_CSV_FALLBACK."
                )
            self._init_csv()
            print("[NotesManager] Using CSV backend")
        
        # Initialize default note if needed (will be called per-user when needed)
        # Note: _initialize_default_note() now requires user_id, so we skip it here

    def _init_csv(self):
        """Initialize CSV backend."""
        os.makedirs(DATA_DIR, exist_ok=True)
        self._ensure_file()
        self._reload_csv()

    def _ensure_file(self):
        """Ensure CSV file exists with proper headers."""
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        if not os.path.exists(self.file):
            with open(self.file, "w", encoding="utf-8") as f:
                f.write("note_id,content,timestamp\n")

    def _reload_csv(self):
        """CSV-specific reload."""
        self._ensure_file()
        try:
            self.df = pd.read_csv(self.file, dtype=str).fillna("")
        except Exception:
            self.df = pd.DataFrame(
                columns=[
                    "note_id",
                    "content",
                    "timestamp",
                ]
            )

    def _save_csv(self):
        """CSV-specific save."""
        self.df.to_csv(self.file, index=False)
        self._reload_csv()

    def _next_id(self) -> str:
        """Generate next note ID."""
        return f"note-{int(datetime.utcnow().timestamp()*1000)}"

    def _initialize_default_note(self, user_id: Optional[int] = None):
        """Initialize with default note if no notes exist for the user.
        
        Args:
            user_id: User ID to check notes for (required for database, optional for CSV during migration)
        """
        if self.use_db:
            with self.db_session() as session:
                query = session.query(self.Note)
                # Filter by user_id if provided (include NULL user_id during migration period)
                if user_id is not None:
                    from sqlalchemy import or_
                    query = query.filter(or_(self.Note.user_id == user_id, self.Note.user_id.is_(None)))
                note_count = query.count()
                if note_count == 0:
                    self.add_note("suno after music walks seems useful", user_id=user_id)
        else:
            self._reload_csv()
            if self.df.empty:
                self.add_note("suno after music walks seems useful", user_id=user_id)

    def add_note(self, content: str, user_id: Optional[int] = None) -> str:
        """Add a new note. Returns the note_id.
        
        Args:
            content: Note content
            user_id: User ID to associate note with (required for database, optional for CSV during migration)
        
        Raises:
            ValidationError: If note validation fails (too long, etc.)
        """
        # Validate and sanitize note content
        from backend.security_utils import validate_note, ValidationError
        try:
            content = validate_note(content)
        except ValidationError as e:
            raise  # Re-raise validation errors for UI to handle
        
        note_id = self._next_id()
        timestamp = datetime.utcnow()
        
        if self.use_db:
            with self.db_session() as session:
                note = self.Note(
                    note_id=note_id,
                    content=content,
                    timestamp=timestamp,
                    user_id=user_id
                )
                session.add(note)
                session.commit()
        else:
            self._reload_csv()
            row = {
                "note_id": note_id,
                "content": content,
                "timestamp": timestamp.isoformat(),
                "user_id": str(user_id) if user_id is not None else '',
            }
            self.df = pd.concat([self.df, pd.DataFrame([row])], ignore_index=True)
            self._save_csv()
        
        return note_id

    def get_all_notes(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all notes for a user, sorted by timestamp (newest first).
        
        Args:
            user_id: User ID to filter by (required for data isolation)
        """
        # CRITICAL: Require user_id for data isolation
        if user_id is None:
            print("[NotesManager] WARNING: get_all_notes() called without user_id - returning empty for security")
            return []
        
        if self.use_db:
            with self.db_session() as session:
                from sqlalchemy import or_
                # Filter by user_id (include NULL user_id during migration period)
                query = session.query(self.Note).filter(
                    or_(self.Note.user_id == user_id, self.Note.user_id.is_(None))
                )
                notes = query.order_by(self.Note.timestamp.desc()).all()
                return [note.to_dict() for note in notes]
        else:
            self._reload_csv()
            if self.df.empty:
                return []
            # Filter by user_id
            df = self.df.copy()
            df = df[df['user_id'].astype(str) == str(user_id)]
            # Convert to records and sort by timestamp descending
            notes = df.to_dict(orient="records")
            # Sort by timestamp descending (newest first)
            notes.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return notes

    def delete_note(self, note_id: str, user_id: Optional[int] = None) -> bool:
        """Delete a note by note_id. Returns True if deleted, False if not found.
        
        Args:
            note_id: Note ID to delete
            user_id: User ID to verify ownership (required for data isolation)
        """
        # CRITICAL: Require user_id for data isolation
        if user_id is None:
            print("[NotesManager] WARNING: delete_note() called without user_id - returning False for security")
            return False
        
        if self.use_db:
            with self.db_session() as session:
                from sqlalchemy import or_
                # Filter by note_id and user_id (include NULL user_id during migration period)
                query = session.query(self.Note).filter(
                    self.Note.note_id == note_id
                ).filter(
                    or_(self.Note.user_id == user_id, self.Note.user_id.is_(None))
                )
                note = query.first()
                if note:
                    session.delete(note)
                    session.commit()
                    return True
                return False
        else:
            self._reload_csv()
            if self.df.empty:
                return False
            # Filter by user_id
            df = self.df.copy()
            df = df[df['user_id'].astype(str) == str(user_id)]
            original_len = len(df)
            df = df[df["note_id"] != note_id]
            if len(df) < original_len:
                # Update self.df with filtered result
                self.df = df
                self._save_csv()
                return True
            return False
