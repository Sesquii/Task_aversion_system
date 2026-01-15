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
        
        # 4.1: Momentum popup (5 tasks completed)
        if '4.1' not in disabled_triggers:
            popup = self._evaluate_trigger_4_1(completion_context, user_id)
            if popup:
                candidates.append((4.1, popup))  # Priority 4.1
        
        # 1.1: Take a break (4 hours without significant idle time)
        if '1.1' not in disabled_triggers:
            popup = self._evaluate_trigger_1_1(completion_context, user_id)
            if popup:
                candidates.append((1.1, popup))  # Priority 1.1
        
        # Add other triggers here as they're implemented
        # 1.2: Other time-based triggers
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
    
    def _evaluate_trigger_4_1(self, context: Optional[Dict[str, Any]], user_id: str) -> Optional[Dict[str, Any]]:
        """
        Trigger 4.1: Momentum popup at 5 tasks
        Fires when user completes 5 tasks in a session (high momentum).
        """
        if not context:
            return None
        
        # Only trigger on completion events
        event_type = context.get('event_type')
        if event_type != 'complete':
            return None
        
        # Check cooldown (don't show more than once per day)
        trigger_id = '4.1'
        if not self.state_manager.check_cooldown(trigger_id, 24, user_id):
            return None
        
        # Get recent task completions (last 24 hours)
        from backend.analytics import Analytics
        from datetime import datetime, timedelta
        import pandas as pd
        
        analytics = Analytics()
        # Convert string user_id to int for database queries
        user_id_int = None
        try:
            if user_id and user_id != 'default':
                user_id_int = int(user_id) if user_id.isdigit() else None
        except (ValueError, AttributeError):
            pass
        df = analytics._load_instances(user_id=user_id_int)
        
        if df.empty:
            return None
        
        # Get completed tasks only
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        if completed.empty:
            return None
        
        # Parse completed_at timestamps
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed.dropna(subset=['completed_at_dt'])
        
        # Get recent completions within last 24 hours
        cutoff_time = datetime.now() - timedelta(hours=24)
        recent = completed[completed['completed_at_dt'] >= cutoff_time].copy()
        
        # Count recent completions
        task_count = len(recent)
        
        # Trigger at exactly 5 tasks
        if task_count != 5:
            return None
        
        # Calculate momentum factor to ensure it's high
        try:
            # Get the most recent completion for momentum calculation
            if len(recent) > 0:
                latest_row = recent.iloc[-1]
                momentum_factor = analytics.calculate_momentum_factor(latest_row)
                
                # Only show if momentum is high (>= 0.7)
                if momentum_factor < 0.7:
                    return None
        except Exception:
            # If calculation fails, still show popup (better to show than miss)
            pass
        
        # Increment count
        count = self.state_manager.increment_trigger_count(trigger_id, user_id)
        
        # Get tier for message selection
        tier = self.state_manager.get_trigger_tier(trigger_id, user_id)
        
        # Get tiered message
        message_data = self._get_trigger_4_1_message(tier)
        
        # Log popup show
        self.state_manager.log_popup_response(
            trigger_id=trigger_id,
            context=context,
            user_id=user_id,
            task_id=context.get('task_id'),
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
    
    def _get_trigger_4_1_message(self, tier: int) -> Dict[str, Any]:
        """Get tiered message for trigger 4.1 (momentum at 5 tasks)."""
        if tier == 0:
            title = "Great Momentum!"
            message = (
                "You've completed 5 tasks - that's excellent momentum! "
                "You're building energy through consistent action. "
                "Would you like to keep going, or take a break?"
            )
        elif tier <= 2:
            title = "Strong Progress!"
            message = (
                "You've completed 5 tasks in this session. "
                "You're maintaining good momentum. "
                "Consider whether you want to continue or take a well-deserved break."
            )
        else:
            title = "Consistent Momentum"
            message = (
                "You've completed 5 tasks. "
                "You're building a pattern of consistent action. "
                "Remember to balance productivity with rest."
            )
        
        return {
            'title': title,
            'message': message,
            'options': [
                {'value': 'continue', 'label': 'Keep Going', 'color': 'primary'},
                {'value': 'break', 'label': 'Take a Break', 'color': 'secondary'}
            ]
        }
    
    def _evaluate_trigger_1_1(self, context: Optional[Dict[str, Any]], user_id: str) -> Optional[Dict[str, Any]]:
        """
        Trigger 1.1: Take a break after 4 hours without significant idle time
        Fires when user has been working for 4+ hours with minimal breaks.
        """
        if not context:
            return None
        
        # Only trigger on completion events
        event_type = context.get('event_type')
        if event_type != 'complete':
            return None
        
        # Check cooldown (don't show more than once per day)
        trigger_id = '1.1'
        if not self.state_manager.check_cooldown(trigger_id, 24, user_id):
            return None
        
        # Get recent task completions
        from backend.analytics import Analytics
        from datetime import datetime, timedelta
        import pandas as pd
        
        analytics = Analytics()
        # Convert string user_id to int for database queries
        user_id_int = None
        try:
            if user_id and user_id != 'default':
                user_id_int = int(user_id) if user_id.isdigit() else None
        except (ValueError, AttributeError):
            pass
        df = analytics._load_instances(user_id=user_id_int)
        
        if df.empty:
            return None
        
        # Get completed tasks only
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        if completed.empty:
            return None
        
        # Parse completed_at timestamps
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed.dropna(subset=['completed_at_dt'])
        
        # Sort by completion time
        completed = completed.sort_values('completed_at_dt')
        
        # Get recent completions within last 4 hours
        cutoff_time = datetime.now() - timedelta(hours=4)
        recent = completed[completed['completed_at_dt'] >= cutoff_time].copy()
        
        if len(recent) < 2:
            return None  # Need at least 2 tasks to measure
        
        # Calculate total time span
        first_completion = recent.iloc[0]['completed_at_dt']
        last_completion = recent.iloc[-1]['completed_at_dt']
        total_span_hours = (last_completion - first_completion).total_seconds() / 3600.0
        
        # Must be at least 4 hours
        if total_span_hours < 4.0:
            return None
        
        # Calculate average gap between completions (idle time)
        gaps = []
        for i in range(1, len(recent)):
            gap_hours = (recent.iloc[i]['completed_at_dt'] - 
                        recent.iloc[i-1]['completed_at_dt']).total_seconds() / 3600.0
            gaps.append(gap_hours)
        
        if not gaps:
            return None
        
        avg_gap_hours = sum(gaps) / len(gaps)
        
        # "Significant idle time" = gap of 30+ minutes (0.5 hours)
        # If average gap is less than 30 minutes, user hasn't taken significant breaks
        if avg_gap_hours >= 0.5:
            return None  # User has taken breaks
        
        # User has been working for 4+ hours with minimal breaks
        # Increment count
        count = self.state_manager.increment_trigger_count(trigger_id, user_id)
        
        # Get tier for message selection
        tier = self.state_manager.get_trigger_tier(trigger_id, user_id)
        
        # Get tiered message
        message_data = self._get_trigger_1_1_message(tier, total_span_hours)
        
        # Log popup show
        self.state_manager.log_popup_response(
            trigger_id=trigger_id,
            context=context,
            user_id=user_id,
            task_id=context.get('task_id'),
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
    
    def _get_trigger_1_1_message(self, tier: int, hours_worked: float) -> Dict[str, Any]:
        """Get tiered message for trigger 1.1 (take a break after 4 hours)."""
        hours_str = f"{hours_worked:.1f}"
        
        if tier == 0:
            title = "Time for a Break?"
            message = (
                f"You've been working for {hours_str} hours with minimal breaks. "
                "Taking regular breaks helps maintain focus and prevents burnout. "
                "Consider stepping away for a few minutes to recharge."
            )
        elif tier <= 2:
            title = "Consider a Break"
            message = (
                f"You've been working for {hours_str} hours. "
                "Remember that rest is an important part of productivity. "
                "A short break can help you maintain your energy and focus."
            )
        else:
            title = "Rest Reminder"
            message = (
                f"You've been working for {hours_str} hours. "
                "Regular breaks are essential for sustained productivity. "
                "Consider taking a break to maintain your well-being."
            )
        
        return {
            'title': title,
            'message': message,
            'options': [
                {'value': 'break', 'label': 'Take a Break', 'color': 'primary'},
                {'value': 'continue', 'label': 'Keep Going', 'color': 'secondary'}
            ]
        }