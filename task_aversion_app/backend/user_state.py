import os
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any, List
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

    # -----------------------------
    # Productivity score preferences
    # -----------------------------
    def get_productivity_settings(self, user_id: str) -> Dict[str, Any]:
        """Get productivity scoring settings (curve + burnout thresholds)."""
        prefs = self.get_user_preferences(user_id)
        if not prefs:
            return {}

        settings_json = prefs.get("productivity_settings", "")
        if not settings_json:
            return {}

        try:
            import json
            return json.loads(settings_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_productivity_settings(self, user_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Persist productivity scoring settings."""
        import json
        settings_json = json.dumps(settings)
        return self.update_preference(user_id, "productivity_settings", settings_json)
    
    def get_productivity_goal_settings(self, user_id: str) -> Dict[str, Any]:
        """Get productivity goal tracking settings.
        
        Returns:
            Dict with:
            - goal_hours_per_week (float, default 40.0)
            - starting_hours_per_week (float or None)
            - initialization_method (str or None: 'auto', 'manual', 'hybrid')
            - auto_estimate_factor (float, default 10.0)
            - last_adjusted_at (ISO string or None)
            - auto_adjusted_count (int, default 0)
            - user_override_flag (bool, default False)
        """
        prefs = self.get_user_preferences(user_id)
        if not prefs:
            return {}
        
        goal_settings_json = prefs.get("productivity_goal_settings", "")
        if not goal_settings_json:
            return {}
        
        try:
            import json
            settings = json.loads(goal_settings_json)
            # Ensure defaults
            if 'goal_hours_per_week' not in settings:
                settings['goal_hours_per_week'] = 40.0
            if 'auto_estimate_factor' not in settings:
                settings['auto_estimate_factor'] = 10.0
            if 'auto_adjusted_count' not in settings:
                settings['auto_adjusted_count'] = 0
            if 'user_override_flag' not in settings:
                settings['user_override_flag'] = False
            return settings
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_productivity_goal_settings(self, user_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Persist productivity goal tracking settings.
        
        Args:
            user_id: User ID
            settings: Dict with goal_hours_per_week, starting_hours_per_week, etc.
        
        Returns:
            Updated preferences dict
        """
        import json
        # Validate and normalize settings
        normalized = {}
        if 'goal_hours_per_week' in settings:
            normalized['goal_hours_per_week'] = float(settings['goal_hours_per_week'])
        if 'starting_hours_per_week' in settings:
            val = settings['starting_hours_per_week']
            normalized['starting_hours_per_week'] = float(val) if val is not None else None
        if 'initialization_method' in settings:
            normalized['initialization_method'] = settings['initialization_method']
        if 'auto_estimate_factor' in settings:
            normalized['auto_estimate_factor'] = float(settings['auto_estimate_factor'])
        if 'last_adjusted_at' in settings:
            normalized['last_adjusted_at'] = settings['last_adjusted_at']
        if 'auto_adjusted_count' in settings:
            normalized['auto_adjusted_count'] = int(settings['auto_adjusted_count'])
        if 'user_override_flag' in settings:
            normalized['user_override_flag'] = bool(settings['user_override_flag'])
        
        settings_json = json.dumps(normalized)
        return self.update_preference(user_id, "productivity_goal_settings", settings_json)
    
    def get_productivity_history(self, user_id: str) -> List[Dict[str, Any]]:
        """Get historical productivity tracking data (weekly snapshots).
        
        Returns:
            List of dicts, each containing:
            - week_start (ISO date string: YYYY-MM-DD)
            - goal_hours (float)
            - actual_hours (float)
            - productivity_score (float)
            - productivity_points (float)
            - recorded_at (ISO datetime string)
        """
        prefs = self.get_user_preferences(user_id)
        if not prefs:
            return []
        
        history_json = prefs.get("productivity_history", "")
        if not history_json:
            return []
        
        try:
            import json
            return json.loads(history_json)
        except (json.JSONDecodeError, TypeError):
            return []
    
    def add_productivity_history_entry(
        self,
        user_id: str,
        week_start: str,
        goal_hours_per_week: float,
        actual_hours: float,
        productivity_score: float,
        productivity_points: float
    ) -> Dict[str, Any]:
        """Add a weekly snapshot to productivity history.
        
        Args:
            user_id: User ID
            week_start: Week start date as ISO string (YYYY-MM-DD)
            goal_hours_per_week: Goal hours for this week
            actual_hours: Actual productive hours for this week
            productivity_score: Total productivity score for this week
            productivity_points: Total productivity points for this week
        
        Returns:
            Updated preferences dict
        """
        import json
        from datetime import datetime
        
        # Get existing history
        history = self.get_productivity_history(user_id)
        
        # Create new entry
        new_entry = {
            'week_start': week_start,
            'goal_hours_per_week': float(goal_hours_per_week),
            'actual_hours': float(actual_hours),
            'productivity_score': float(productivity_score),
            'productivity_points': float(productivity_points),
            'recorded_at': datetime.utcnow().isoformat()
        }
        
        # Check if entry for this week already exists, update it if so
        existing_index = None
        for i, entry in enumerate(history):
            if entry.get('week_start') == week_start:
                existing_index = i
                break
        
        if existing_index is not None:
            history[existing_index] = new_entry
        else:
            history.append(new_entry)
        
        # Sort by week_start (oldest first)
        history.sort(key=lambda x: x.get('week_start', ''))
        
        # Keep only last 52 weeks (1 year) to prevent unbounded growth
        if len(history) > 52:
            history = history[-52:]
        
        history_json = json.dumps(history)
        return self.update_preference(user_id, "productivity_history", history_json)

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
    # Cancellation categories management
    # -----------------------------
    def get_cancellation_categories(self, user_id: str = "default") -> Dict[str, str]:
        """Get custom cancellation categories for a user.
        
        Args:
            user_id: User ID (defaults to "default" for single-user systems)
            
        Returns:
            Dict of category_key -> category_label
        """
        prefs = self.get_user_preferences(user_id)
        if not prefs:
            return {}
        
        categories_json = prefs.get("cancellation_categories", "")
        if not categories_json:
            return {}
        
        try:
            import json
            return json.loads(categories_json)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_cancellation_categories(self, categories: Dict[str, str], user_id: str = "default") -> Dict[str, Any]:
        """Set custom cancellation categories for a user.
        
        Args:
            categories: Dict of category_key -> category_label
            user_id: User ID (defaults to "default" for single-user systems)
            
        Returns:
            Updated preferences dict
        """
        import json
        categories_json = json.dumps(categories)
        return self.update_preference(user_id, "cancellation_categories", categories_json)
    
    def add_cancellation_category(self, category_key: str, category_label: str, user_id: str = "default") -> Dict[str, str]:
        """Add a new cancellation category.
        
        Args:
            category_key: Unique key for the category (e.g., 'custom_reason_1')
            category_label: Display label for the category
            user_id: User ID
            
        Returns:
            Updated categories dict
        """
        categories = self.get_cancellation_categories(user_id)
        categories[category_key] = category_label
        self.set_cancellation_categories(categories, user_id)
        return categories
    
    def remove_cancellation_category(self, category_key: str, user_id: str = "default") -> Dict[str, str]:
        """Remove a cancellation category.
        
        Args:
            category_key: Key of the category to remove
            user_id: User ID
            
        Returns:
            Updated categories dict
        """
        categories = self.get_cancellation_categories(user_id)
        if category_key in categories:
            del categories[category_key]
            self.set_cancellation_categories(categories, user_id)
        return categories

    # -----------------------------
    # Cancellation penalties management
    # -----------------------------
    def get_cancellation_penalties(self, user_id: str = "default") -> Dict[str, float]:
        """Get cancellation penalty multipliers for each category.
        
        Args:
            user_id: User ID (defaults to "default" for single-user systems)
            
        Returns:
            Dict of category_key -> penalty_multiplier (0.0 to 1.0)
        """
        prefs = self.get_user_preferences(user_id)
        if not prefs:
            return {}
        
        penalties_json = prefs.get("cancellation_penalties", "")
        if not penalties_json:
            return {}
        
        try:
            import json
            return json.loads(penalties_json)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_cancellation_penalties(self, penalties: Dict[str, float], user_id: str = "default") -> Dict[str, Any]:
        """Set cancellation penalty multipliers for each category.
        
        Args:
            penalties: Dict of category_key -> penalty_multiplier (0.0 to 1.0)
            user_id: User ID (defaults to "default" for single-user systems)
            
        Returns:
            Updated preferences dict
        """
        import json
        # Ensure all values are between 0.0 and 1.0
        validated_penalties = {k: max(0.0, min(1.0, float(v))) for k, v in penalties.items()}
        penalties_json = json.dumps(validated_penalties)
        return self.update_preference(user_id, "cancellation_penalties", penalties_json)

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

