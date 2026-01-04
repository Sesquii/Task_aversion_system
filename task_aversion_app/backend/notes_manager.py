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
                print("[NotesManager] Using database backend")
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
        
        # Initialize default note if needed
        self._initialize_default_note()

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

    def _initialize_default_note(self):
        """Initialize with default note if no notes exist."""
        if self.use_db:
            with self.db_session() as session:
                note_count = session.query(self.Note).count()
                if note_count == 0:
                    self.add_note("suno after music walks seems useful")
        else:
            self._reload_csv()
            if self.df.empty:
                self.add_note("suno after music walks seems useful")

    def add_note(self, content: str) -> str:
        """Add a new note. Returns the note_id."""
        note_id = self._next_id()
        timestamp = datetime.utcnow()
        
        if self.use_db:
            with self.db_session() as session:
                note = self.Note(
                    note_id=note_id,
                    content=content,
                    timestamp=timestamp
                )
                session.add(note)
                session.commit()
        else:
            self._reload_csv()
            row = {
                "note_id": note_id,
                "content": content,
                "timestamp": timestamp.isoformat(),
            }
            self.df = pd.concat([self.df, pd.DataFrame([row])], ignore_index=True)
            self._save_csv()
        
        return note_id

    def get_all_notes(self) -> List[Dict[str, Any]]:
        """Get all notes, sorted by timestamp (newest first)."""
        if self.use_db:
            with self.db_session() as session:
                notes = session.query(self.Note).order_by(self.Note.timestamp.desc()).all()
                return [note.to_dict() for note in notes]
        else:
            self._reload_csv()
            if self.df.empty:
                return []
            # Convert to records and sort by timestamp descending
            notes = self.df.to_dict(orient="records")
            # Sort by timestamp descending (newest first)
            notes.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return notes

    def delete_note(self, note_id: str) -> bool:
        """Delete a note by note_id. Returns True if deleted, False if not found."""
        if self.use_db:
            with self.db_session() as session:
                note = session.query(self.Note).filter(self.Note.note_id == note_id).first()
                if note:
                    session.delete(note)
                    session.commit()
                    return True
                return False
        else:
            self._reload_csv()
            if self.df.empty:
                return False
            original_len = len(self.df)
            self.df = self.df[self.df["note_id"] != note_id]
            if len(self.df) < original_len:
                self._save_csv()
                return True
            return False
