# backend/emotion_manager.py
import os
import pandas as pd
from typing import List
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

class EmotionManager:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.file = os.path.join(DATA_DIR, 'emotions.csv')
        if not os.path.exists(self.file):
            pd.DataFrame(columns=['emotion']).to_csv(self.file, index=False)
        self._reload()

    def _reload(self):
        self.df = pd.read_csv(self.file, dtype=str).fillna('')

    def _save(self):
        self.df.to_csv(self.file, index=False)
        self._reload()

    def list_emotions(self) -> List[str]:
        self._reload()
        return [e for e in self.df['emotion'].tolist() if e]

    def add_emotion(self, emotion: str):
        self._reload()
        if emotion in self.df['emotion'].values:
            return False
        self.df = pd.concat([self.df, pd.DataFrame([{'emotion': emotion}])], ignore_index=True)
        self._save()
        return True
