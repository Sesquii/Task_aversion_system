# backend/emotion_manager.py
import os
import pandas as pd
from typing import List, Dict
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

class EmotionManager:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.file = os.path.join(DATA_DIR, 'emotions.csv')
        if not os.path.exists(self.file):
            pd.DataFrame(columns=['emotion']).to_csv(self.file, index=False)
        self._reload()

    def _reload(self):
        # Normalize whitespace to reduce accidental duplicates
        self.df = pd.read_csv(self.file, dtype=str).fillna('')
        if 'emotion' not in self.df.columns:
            self.df['emotion'] = ''
        self.df['emotion'] = self.df['emotion'].apply(lambda x: str(x).strip())

    def _save(self):
        self.df.to_csv(self.file, index=False)
        self._reload()

    @staticmethod
    def _normalize(emotion: str) -> str:
        """Lowercased/stripped helper for duplicate detection."""
        return (emotion or '').strip().lower()

    def list_emotions(self) -> List[str]:
        self._reload()
        # Drop case-insensitive duplicates while preserving first occurrence
        normalized = self.df['emotion'].str.lower()
        keep_mask = ~normalized.duplicated(keep='first')
        if not keep_mask.all():
            self.df = self.df.loc[keep_mask].reset_index(drop=True)
            self._save()
        return [e for e in self.df['emotion'].tolist() if e]

    def add_emotion(self, emotion: str):
        self._reload()
        norm = self._normalize(emotion)
        if not norm:
            return False
        existing_norms = {self._normalize(e) for e in self.df['emotion'].tolist()}
        if norm in existing_norms:
            return False
        self.df = pd.concat([self.df, pd.DataFrame([{'emotion': emotion.strip()}])], ignore_index=True)
        self._save()
        return True

    def remove_emotion(self, emotion: str) -> bool:
        """Remove all case-insensitive matches of an emotion."""
        self._reload()
        norm = self._normalize(emotion)
        if not norm:
            return False
        mask = self.df['emotion'].str.lower() != norm
        if mask.all():
            return False
        self.df = self.df.loc[mask].reset_index(drop=True)
        self._save()
        return True

    def search_emotions(self, query: str) -> List[str]:
        """Return emotions containing the query (case-insensitive)."""
        self._reload()
        q = self._normalize(query)
        emotions = [e for e in self.df['emotion'].tolist() if e]
        if not q:
            return emotions
        return [e for e in emotions if q in self._normalize(e)]

    def find_duplicates(self) -> Dict[str, List[str]]:
        """Return duplicate groups keyed by normalized value."""
        self._reload()
        normed = self.df['emotion'].str.lower()
        dup_groups: Dict[str, List[str]] = {}
        for norm_val in normed.unique():
            originals = self.df.loc[normed == norm_val, 'emotion'].tolist()
            if len(originals) > 1:
                dup_groups[norm_val] = originals
        return dup_groups

    def deduplicate_emotions(self) -> List[str]:
        """Remove case-insensitive duplicates, keeping first occurrence."""
        self._reload()
        normed = self.df['emotion'].str.lower()
        dup_mask = normed.duplicated(keep='first')
        removed = self.df.loc[dup_mask, 'emotion'].tolist()
        if removed:
            self.df = self.df.loc[~dup_mask].reset_index(drop=True)
            self._save()
        return removed
