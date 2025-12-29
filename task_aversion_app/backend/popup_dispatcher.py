"""
Popup dispatcher service for evaluating triggers and returning popup content.
Implements trigger catalog from popup_rules.md with tiered messaging and cooldown logic.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime

from backend.popup_state import PopupStateManager
from backend.user_state import UserStateManager


class PopupDispatcher:
    """
    Evaluates triggers and returns popup content based on context.
    Honors cooldowns, daily caps, and one-popup-per-event rules.
    """
    
    def __init__(self):
        self.state_manager = PopupStateManager()
        self.user_state = UserStateManager()
        self.default_daily_cap = 5  # Default daily cap for production
        self.default_cooldown_hours = 24
    
    def get_daily_cap(self, user_id: str = 'default') -> int:
        """
        Get daily popup cap for a user.
        
        Priority:
        1. User preference popup_daily_cap
        2. Default value (5)
        
        Args:
            user_id: User identifier
        
        Returns:
            Daily cap value (int)
        """
        # Check user preference
        prefs = self.user_state.get_user_preferences(user_id)
        if prefs:
            pref_cap = prefs.get('popup_daily_cap', '')
            if pref_cap:
                try:
                    return int(pref_cap)
                except (ValueError, TypeError):
                    pass
        
        # Default
        return self.default_daily_cap
    
    def evaluate_triggers(self, completion_context: Optional[Dict[str, Any]] = None,
                         survey_context: Optional[Dict[str, Any]] = None,
                         settings: Optional[Dict[str, Any]] = None,
                         user_id: str = 'default') -> Optional[Dict[str, Any]]:
        """
        Evaluate all triggers and return highest-priority popup (or none).
        
        Args:
            completion_context: Context from task completion (actual/predicted, completion %, etc.)
            survey_context: Survey-related context (procrastination, perfectionism, etc.)
            settings: User settings (daily cap, disabled triggers, etc.)
            user_id: User identifier
        
        Returns:
            Popup dict with trigger_id, message, options, etc., or None if no popup should show
        """
        # Get daily cap (from env var, user preference, or default)
        daily_cap = self.get_daily_cap(user_id)
        
        # Override from settings if provided (for runtime override)
        if settings and 'daily_cap' in settings:
            daily_cap = settings.get('daily_cap', daily_cap)
        
        # Check daily cap
        daily_count = self.state_manager.get_daily_popup_count(user_id)
        if daily_count >= daily_cap:
            return None  # Hit daily cap
        
        # Get disabled triggers from settings
        disabled_triggers = set()
        if settings and 'disabled_triggers' in settings:
            disabled_triggers = set(settings.get('disabled_triggers', []))
        
        # Evaluate triggers in priority order
        # Priority: Data Quality (7.x) > Time-Based (1.x) > Completion (2.x) > Affect (3.x) > Behavioral (4.x) > Survey (5.x)
        
        candidates = []
        
        # 7.1: No sliders adjusted (Data Quality)
        if '7.1' not in disabled_triggers:
            popup = self._evaluate_trigger_7_1(completion_context, user_id)
            if popup:
                candidates.append((7.1, popup))  # Priority 7.1
        
        # Add other triggers here as they're implemented
        # 1.1: Time Overrun
        # 2.1: Partial Completion
        # etc.
        
        # Return highest priority popup
        if candidates:
            # Sort by priority (higher number = higher priority)
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        
        return None
    
    def _evaluate_trigger_7_1(self, context: Optional[Dict[str, Any]], user_id: str) -> Optional[Dict[str, Any]]:
        """
        Trigger 7.1: No sliders adjusted
        Fires when user attempts to complete/initialize without adjusting any sliders.
        """
        if not context:
            return None
        
        # Check if this is a completion or initialization event
        event_type = context.get('event_type')  # 'complete' or 'initialize'
        if event_type not in ['complete', 'initialize']:
            return None
        
        # Check if any sliders were adjusted
        sliders_adjusted = context.get('sliders_adjusted', False)
        if sliders_adjusted:
            return None  # Sliders were adjusted, no popup
        
        # Check cooldown
        trigger_id = '7.1'
        task_id = context.get('task_id')
        if not self.state_manager.check_cooldown(trigger_id, self.default_cooldown_hours, user_id, task_id):
            return None  # In cooldown
        
        # Get tier for message selection
        tier = self.state_manager.get_trigger_tier(trigger_id, user_id, task_id)
        
        # Increment count
        count = self.state_manager.increment_trigger_count(trigger_id, user_id, task_id)
        
        # Get tiered message
        message_data = self._get_trigger_7_1_message(tier, event_type)
        
        # Log popup show
        self.state_manager.log_popup_response(
            trigger_id=trigger_id,
            context=context,
            user_id=user_id,
            task_id=task_id,
            instance_id=context.get('instance_id')
        )
        
        return {
            'trigger_id': trigger_id,
            'title': message_data['title'],
            'message': message_data['message'],
            'options': message_data['options'],
            'show_helpful_toggle': True,
            'tier': tier,
            'count': count
        }
    
    def _get_trigger_7_1_message(self, tier: int, event_type: str) -> Dict[str, Any]:
        """
        Get tiered message for trigger 7.1 (no sliders adjusted).
        
        Args:
            tier: Trigger tier (0=first time, 1-2=repeats, 3+=habitual)
            event_type: 'complete' or 'initialize'
        """
        action = "complete" if event_type == 'complete' else "initialize"
        action_ing = "completing" if event_type == 'complete' else "initializing"
        
        if tier == 0:
            # First time: brief, encouraging
            title = "Check Your Sliders"
            message = (
                f"Before {action_ing} this task, take a moment to ensure your sliders accurately reflect "
                f"your current state. Accurate tracking helps you understand patterns and improve over time."
            )
        elif tier <= 2:
            # Repeats: slightly more direct
            title = "Sliders Not Adjusted"
            message = (
                f"It looks like you haven't adjusted any sliders before {action_ing} this task. "
                f"Taking a moment to set accurate values helps with emotional regulation and provides "
                f"better insights into your task patterns."
            )
        else:
            # Habitual: supportive but clear
            title = "Remember to Track Emotions"
            message = (
                f"You're about to {action} this task without adjusting sliders. "
                f"Tracking your emotional state is an important part of emotional regulation. "
                f"Even if values seem similar, small adjustments help maintain awareness."
            )
        
        # Optional reinforcement message about emotional tracking
        reinforcement = (
            "\n\nTracking your emotions helps you recognize patterns, manage stress, "
            "and make more informed decisions about your tasks."
        )
        
        return {
            'title': title,
            'message': message + reinforcement,
            'options': [
                {'value': 'continue', 'label': 'Continue', 'color': 'primary'},
                {'value': 'edit', 'label': 'Edit Sliders', 'color': 'secondary'}
            ]
        }
    
    def handle_popup_response(self, trigger_id: str, response_value: str,
                              helpful: Optional[bool] = None, comment: Optional[str] = None,
                              user_id: str = 'default', task_id: Optional[str] = None):
        """Handle user response to a popup."""
        # Update trigger feedback
        self.state_manager.update_trigger_feedback(
            trigger_id=trigger_id,
            helpful=helpful,
            response=response_value,
            comment=comment,
            user_id=user_id,
            task_id=task_id
        )
        
        # Log response
        self.state_manager.log_popup_response(
            trigger_id=trigger_id,
            response_value=response_value,
            helpful=helpful,
            comment=comment,
            user_id=user_id,
            task_id=task_id
        )
