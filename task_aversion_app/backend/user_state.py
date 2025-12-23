import os
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


DATA_DIR = os.path.join(Path(__file__).resolve().parent.parent, "data")
os.makedirs(DATA_DIR, exist_ok=True)

PREFS_FILE = os.path.join(DATA_DIR, "user_preferences.csv")

DEFAULT_PREFS = {
    "user_id": "",
    "tutorial_completed": "False",
    "tutorial_choice": "",
    "tutorial_auto_show": "True",
    "tooltip_mode_enabled": "True",
    "survey_completed": "False",
    "created_at": "",
    "last_active": "",
}


class UserStateManager:
    """Manage anonymous user ids and onboarding preferences backed by CSV."""

    def __init__(self, prefs_file: Optional[str] = None):
        self.file = prefs_file or PREFS_FILE
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        self._ensure_file()
        self._reload()

    # -----------------------------
    # File helpers
    # -----------------------------
    def _ensure_file(self):
        if not os.path.exists(self.file):
            pd.DataFrame(columns=DEFAULT_PREFS.keys()).to_csv(self.file, index=False)

    def _reload(self):
        try:
            self.df = pd.read_csv(self.file, dtype=str).fillna("")
        except Exception:
            self.df = pd.DataFrame(columns=DEFAULT_PREFS.keys())

    def _save(self):
        self.df.to_csv(self.file, index=False)
        self._reload()

    # -----------------------------
    # Public API
    # -----------------------------
    def ensure_user(self, user_id: str) -> Dict[str, Any]:
        """Ensure a row exists for user_id, return preferences dict."""
        self._reload()
        existing = self.df[self.df["user_id"] == user_id]
        if not existing.empty:
            prefs = existing.iloc[0].to_dict()
            return prefs

        now = datetime.utcnow().isoformat()
        row = {**DEFAULT_PREFS}
        row["user_id"] = user_id
        row["created_at"] = now
        row["last_active"] = now
        self.df = pd.concat([self.df, pd.DataFrame([row])], ignore_index=True)
        self._save()
        return row

    def get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        self._reload()
        rows = self.df[self.df["user_id"] == user_id]
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def update_preference(self, user_id: str, key: str, value: Any) -> Dict[str, Any]:
        """Update a single preference; creates the user row if needed."""
        self.ensure_user(user_id)
        self._reload()
        if key not in self.df.columns:
            # Expand CSV dynamically if new preference keys are introduced
            self.df[key] = ""
        self.df.loc[self.df["user_id"] == user_id, key] = str(value)
        self.df.loc[self.df["user_id"] == user_id, "last_active"] = datetime.utcnow().isoformat()
        self._save()
        return self.get_user_preferences(user_id) or {}

    def is_new_user(self, user_id: str) -> bool:
        return self.get_user_preferences(user_id) is None

    def mark_tutorial_completed(self, user_id: str, choice: Optional[str] = None):
        prefs = self.ensure_user(user_id)
        self.update_preference(user_id, "tutorial_completed", True)
        if choice:
            self.update_preference(user_id, "tutorial_choice", choice)
        return self.get_user_preferences(user_id) or prefs

    def mark_survey_completed(self, user_id: str):
        return self.update_preference(user_id, "survey_completed", True)

    def should_auto_show_tutorial(self, prefs: Dict[str, Any]) -> bool:
        auto_show = str(prefs.get("tutorial_auto_show", "True")).lower() == "true"
        completed = str(prefs.get("tutorial_completed", "False")).lower() == "true"
        return auto_show and not completed

    def get_score_weights(self, user_id: str) -> Dict[str, float]:
        """Get composite score weights for a user.
        
        Returns:
            Dict of component_name -> weight (default: equal weights)
        """
        prefs = self.get_user_preferences(user_id)
        if not prefs:
            return {}
        
        weights_json = prefs.get("composite_score_weights", "")
        if not weights_json:
            return {}
        
        try:
            import json
            return json.loads(weights_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_score_weights(self, user_id: str, weights: Dict[str, float]) -> Dict[str, Any]:
        """Set composite score weights for a user.
        
        Args:
            user_id: User ID
            weights: Dict of component_name -> weight
            
        Returns:
            Updated preferences dict
        """
        import json
        weights_json = json.dumps(weights)
        return self.update_preference(user_id, "composite_score_weights", weights_json)

    def get_persistent_emotions(self, user_id: str = "default") -> Dict[str, int]:
        """Get persistent emotion values that persist across tasks.
        
        Args:
            user_id: User ID (defaults to "default" for single-user systems)
            
        Returns:
            Dict of emotion -> value (0-100)
        """
        prefs = self.get_user_preferences(user_id)
        if not prefs:
            return {}
        
        emotion_json = prefs.get("persistent_emotion_values", "")
        if not emotion_json:
            return {}
        
        try:
            import json
            return json.loads(emotion_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_persistent_emotions(self, emotion_values: Dict[str, int], user_id: str = "default") -> Dict[str, Any]:
        """Set persistent emotion values that persist across tasks.
        
        Args:
            emotion_values: Dict of emotion -> value (0-100)
            user_id: User ID (defaults to "default" for single-user systems)
            
        Returns:
            Updated preferences dict
        """
        import json
        # Filter out zero values to keep data clean
        filtered = {k: v for k, v in emotion_values.items() if v > 0}
        emotion_json = json.dumps(filtered)
        return self.update_preference(user_id, "persistent_emotion_values", emotion_json)

    # -----------------------------
    # JavaScript helpers
    # -----------------------------
    @staticmethod
    def js_get_or_create_user_id(local_key: str = "tas_user_id") -> str:
        """
        Returns JS snippet that ensures a user_id in localStorage and returns it.
        Designed to be used with ui.run_javascript(..., respond=True).
        """
        return f"""
        (() => {{
            const key = '{local_key}';
            let uid = window.localStorage.getItem(key);
            if (!uid || typeof uid !== 'string' || uid.length < 6) {{
                const rand = (len=12) => Array.from(crypto.getRandomValues(new Uint8Array(len)))
                    .map((b) => b.toString(16).padStart(2, '0')).join('');
                uid = (crypto.randomUUID ? crypto.randomUUID() : rand()) + '-' + Date.now().toString(36);
                window.localStorage.setItem(key, uid);
            }}
            return uid;
        }})();
        """

    @staticmethod
    def js_set_pref_flag(flag: str, value: bool, local_key: str = "tas_user_prefs") -> str:
        """Store lightweight preference flags client-side for quick access."""
        return f"""
        (() => {{
            const key = '{local_key}';
            let prefs = {{}};
            try {{
                prefs = JSON.parse(window.localStorage.getItem(key) || '{{}}');
            }} catch (e) {{}}
            prefs['{flag}'] = {str(value).lower()};
            window.localStorage.setItem(key, JSON.stringify(prefs));
            return prefs;
        }})();
        """

    @staticmethod
    def js_get_pref_flag(flag: str, local_key: str = "tas_user_prefs") -> str:
        return f"""
        (() => {{
            const key = '{local_key}';
            try {{
                const prefs = JSON.parse(window.localStorage.getItem(key) || '{{}}');
                return prefs['{flag}'];
            }} catch (e) {{
                return null;
            }}
        }})();
        """

