# backend/emotion_manager.py
"""
EmotionManager - manages per-user emotion vocabulary for the UI.
Supports both CSV (fallback) and database backends with user_id data isolation.
"""
import os
from typing import List, Dict, Optional, Union

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
DEFAULT_USER_ID_STR = "default"


def _normalize_user_id(user_id: Optional[Union[int, str]]) -> Optional[Union[int, str]]:
    """
    Normalize user_id for use in EmotionManager.
    Returns None for default/anonymous; otherwise int for DB, str for CSV.
    """
    if user_id is None:
        return None
    if isinstance(user_id, int):
        return user_id if user_id else None
    s = str(user_id).strip() if user_id else ""
    return s if s and s.lower() != "default" else None


class EmotionManager:
    """Manages emotion vocabulary with per-user data isolation."""

    def __init__(self) -> None:
        use_csv = os.getenv('USE_CSV', '').lower() in ('1', 'true', 'yes')
        if use_csv or not os.getenv('DATABASE_URL'):
            self.use_db = False
            os.makedirs(DATA_DIR, exist_ok=True)
            self.file = os.path.join(DATA_DIR, 'emotions.csv')
            if not os.path.exists(self.file):
                pd.DataFrame(columns=['emotion', 'user_id']).to_csv(self.file, index=False)
            self._reload_csv()
        else:
            self.use_db = True
            try:
                from backend.database import get_session, Emotion, init_db
                self.db_session = get_session
                self.Emotion = Emotion
                init_db()
            except Exception as e:
                print(f"[EmotionManager] Database init failed: {e}, falling back to CSV")
                self.use_db = False
                os.makedirs(DATA_DIR, exist_ok=True)
                self.file = os.path.join(DATA_DIR, 'emotions.csv')
                if not os.path.exists(self.file):
                    pd.DataFrame(columns=['emotion', 'user_id']).to_csv(self.file, index=False)
                self._reload_csv()

    def _reload_csv(self) -> None:
        """Reload CSV into dataframe."""
        self.df = pd.read_csv(self.file, dtype=str).fillna('') if os.path.exists(self.file) else pd.DataFrame()
        if 'emotion' not in self.df.columns:
            self.df['emotion'] = ''
        if 'user_id' not in self.df.columns:
            self.df['user_id'] = DEFAULT_USER_ID_STR
        self.df['emotion'] = self.df['emotion'].apply(lambda x: str(x).strip())
        self.df['user_id'] = self.df['user_id'].astype(str)

    def _save_csv(self) -> None:
        """Save dataframe to CSV."""
        self.df.to_csv(self.file, index=False)
        self._reload_csv()

    @staticmethod
    def _normalize(emotion: str) -> str:
        """Lowercased/stripped helper for duplicate detection."""
        return (emotion or '').strip().lower()

    def list_emotions(
        self,
        user_id: Optional[Union[int, str]] = None
    ) -> List[str]:
        """Return emotions for the given user."""
        uid = _normalize_user_id(user_id)
        if self.use_db:
            return self._list_emotions_db(uid)
        return self._list_emotions_csv(uid)

    def _list_emotions_db(
        self,
        user_id: Optional[Union[int, str]]
    ) -> List[str]:
        """Database: list emotions filtered by user_id."""
        with self.db_session() as session:
            query = session.query(self.Emotion.emotion)
            if user_id is not None:
                uid = int(user_id) if isinstance(user_id, (int, str)) and str(user_id).isdigit() else None
                if uid is not None:
                    query = query.filter(self.Emotion.user_id == uid)
                else:
                    query = query.filter(self.Emotion.user_id.is_(None))
            rows = query.all()
            seen: set = set()
            result: List[str] = []
            for (emotion,) in rows:
                if emotion and self._normalize(emotion) not in seen:
                    seen.add(self._normalize(emotion))
                    result.append(emotion)
            return result

    def _list_emotions_csv(
        self,
        user_id: Optional[Union[int, str]]
    ) -> List[str]:
        """CSV: list emotions filtered by user_id."""
        self._reload_csv()
        uid_str = str(user_id) if user_id is not None else DEFAULT_USER_ID_STR
        mask = self.df['user_id'] == uid_str
        emotions = self.df.loc[mask, 'emotion'].tolist()
        emotions = [e for e in emotions if e]
        seen: set = set()
        result: List[str] = []
        for e in emotions:
            n = self._normalize(e)
            if n not in seen:
                seen.add(n)
                result.append(e)
        return result

    def add_emotion(
        self,
        emotion: str,
        user_id: Optional[Union[int, str]] = None
    ) -> bool:
        """Add emotion for the given user. Returns False if duplicate or empty."""
        uid = _normalize_user_id(user_id)
        if self.use_db:
            return self._add_emotion_db(emotion, uid)
        return self._add_emotion_csv(emotion, uid)

    def _add_emotion_db(
        self,
        emotion: str,
        user_id: Optional[Union[int, str]]
    ) -> bool:
        """Database: add emotion for user."""
        norm = self._normalize(emotion)
        if not norm:
            return False
        uid_int = None
        if user_id is not None:
            try:
                uid_int = int(user_id)
            except (TypeError, ValueError):
                pass
        with self.db_session() as session:
            existing = session.query(self.Emotion).filter(
                self.Emotion.user_id == uid_int,
                self.Emotion.emotion.ilike(norm)
            ).first()
            if existing:
                return False
            e = self.Emotion(emotion=emotion.strip(), user_id=uid_int)
            session.add(e)
            session.commit()
        return True

    def _add_emotion_csv(
        self,
        emotion: str,
        user_id: Optional[Union[int, str]]
    ) -> bool:
        """CSV: add emotion for user."""
        self._reload_csv()
        norm = self._normalize(emotion)
        if not norm:
            return False
        uid_str = str(user_id) if user_id is not None else DEFAULT_USER_ID_STR
        existing = self.df[(self.df['user_id'] == uid_str) & (
            self.df['emotion'].str.lower() == norm
        )]
        if not existing.empty:
            return False
        self.df = pd.concat([
            self.df,
            pd.DataFrame([{'emotion': emotion.strip(), 'user_id': uid_str}])
        ], ignore_index=True)
        self._save_csv()
        return True

    def remove_emotion(
        self,
        emotion: str,
        user_id: Optional[Union[int, str]] = None
    ) -> bool:
        """Remove emotion for the given user."""
        uid = _normalize_user_id(user_id)
        if self.use_db:
            return self._remove_emotion_db(emotion, uid)
        return self._remove_emotion_csv(emotion, uid)

    def _remove_emotion_db(
        self,
        emotion: str,
        user_id: Optional[Union[int, str]]
    ) -> bool:
        """Database: remove emotion for user."""
        norm = self._normalize(emotion)
        if not norm:
            return False
        uid_int = None
        if user_id is not None:
            try:
                uid_int = int(user_id)
            except (TypeError, ValueError):
                pass
        with self.db_session() as session:
            deleted = session.query(self.Emotion).filter(
                self.Emotion.user_id == uid_int,
                self.Emotion.emotion.ilike(norm)
            ).delete()
            session.commit()
            return deleted > 0

    def _remove_emotion_csv(
        self,
        emotion: str,
        user_id: Optional[Union[int, str]]
    ) -> bool:
        """CSV: remove emotion for user."""
        self._reload_csv()
        norm = self._normalize(emotion)
        if not norm:
            return False
        uid_str = str(user_id) if user_id is not None else DEFAULT_USER_ID_STR
        mask = (self.df['user_id'] == uid_str) & (self.df['emotion'].str.lower() != norm)
        if mask.all():
            return False
        self.df = self.df.loc[mask].reset_index(drop=True)
        self._save_csv()
        return True

    def search_emotions(
        self,
        query: str,
        user_id: Optional[Union[int, str]] = None
    ) -> List[str]:
        """Return emotions containing the query (case-insensitive) for the user."""
        emotions = self.list_emotions(user_id=user_id)
        q = self._normalize(query)
        if not q:
            return emotions
        return [e for e in emotions if q in self._normalize(e)]

    def find_duplicates(
        self,
        user_id: Optional[Union[int, str]] = None
    ) -> Dict[str, List[str]]:
        """Return duplicate groups keyed by normalized value for the user."""
        emotions = self.list_emotions(user_id=user_id)
        normed: Dict[str, List[str]] = {}
        for e in emotions:
            n = self._normalize(e)
            normed.setdefault(n, []).append(e)
        return {k: v for k, v in normed.items() if len(v) > 1}

    def deduplicate_emotions(
        self,
        user_id: Optional[Union[int, str]] = None
    ) -> List[str]:
        """Remove case-insensitive duplicates, keeping first occurrence."""
        emotions = self.list_emotions(user_id=user_id)
        seen: set = set()
        kept: List[str] = []
        removed: List[str] = []
        for e in emotions:
            n = self._normalize(e)
            if n in seen:
                removed.append(e)
            else:
                seen.add(n)
                kept.append(e)
        if removed and not self.use_db:
            self._reload_csv()
            uid_str = str(user_id) if user_id is not None else DEFAULT_USER_ID_STR
            for r in removed:
                self._remove_emotion_csv(r, user_id)
        elif removed and self.use_db:
            for r in removed:
                self._remove_emotion_db(r, user_id)
        return removed
