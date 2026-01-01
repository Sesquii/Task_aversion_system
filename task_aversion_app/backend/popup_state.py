"""
Popup state management for tracking trigger counts, cooldowns, and responses.
Provides CRUD operations for popup triggers and responses with graceful fallback.
"""
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.exc import OperationalError, IntegrityError

from backend.database import get_session, PopupTrigger, PopupResponse


class PopupStateManager:
    """
    Manages popup trigger state and responses.
    Gracefully falls back to no-op if database is unavailable.
    """
    
    def __init__(self):
        self.use_db = bool(os.getenv('DATABASE_URL', 'sqlite:///data/task_aversion.db'))
        # Always try to use DB (even if default SQLite), but handle errors gracefully
    
    def _safe_db_operation(self, operation, fallback_value=None):
        """Execute a database operation with graceful error handling."""
        if not self.use_db:
            return fallback_value
        
        try:
            with get_session() as session:
                result = operation(session)
                session.commit()
                return result
        except (OperationalError, IntegrityError) as e:
            print(f"[PopupState] Database error (graceful fallback): {e}")
            return fallback_value
        except Exception as e:
            print(f"[PopupState] Unexpected error: {e}")
            return fallback_value
    
    def get_trigger_state(self, trigger_id: str, user_id: str = 'default', task_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get trigger state for a specific trigger."""
        def op(session):
            query = session.query(PopupTrigger).filter(
                PopupTrigger.trigger_id == trigger_id,
                PopupTrigger.user_id == user_id
            )
            if task_id:
                query = query.filter(PopupTrigger.task_id == task_id)
            else:
                query = query.filter(PopupTrigger.task_id.is_(None))
            
            trigger = query.first()
            return trigger.to_dict() if trigger else None
        
        return self._safe_db_operation(op, fallback_value=None)
    
    def increment_trigger_count(self, trigger_id: str, user_id: str = 'default', task_id: Optional[str] = None) -> int:
        """Increment trigger count and update last_shown_at. Returns new count."""
        def op(session):
            query = session.query(PopupTrigger).filter(
                PopupTrigger.trigger_id == trigger_id,
                PopupTrigger.user_id == user_id
            )
            if task_id:
                query = query.filter(PopupTrigger.task_id == task_id)
            else:
                query = query.filter(PopupTrigger.task_id.is_(None))
            
            trigger = query.first()
            
            if trigger:
                trigger.count += 1
                trigger.last_shown_at = datetime.utcnow()
                trigger.updated_at = datetime.utcnow()
                count = trigger.count
            else:
                # Create new trigger state
                trigger = PopupTrigger(
                    trigger_id=trigger_id,
                    user_id=user_id,
                    task_id=task_id,
                    count=1,
                    last_shown_at=datetime.utcnow()
                )
                session.add(trigger)
                count = 1
            
            return count
        
        return self._safe_db_operation(op, fallback_value=0)
    
    def update_trigger_feedback(self, trigger_id: str, helpful: Optional[bool] = None, 
                                response: Optional[str] = None, comment: Optional[str] = None,
                                user_id: str = 'default', task_id: Optional[str] = None):
        """Update feedback for a trigger."""
        def op(session):
            query = session.query(PopupTrigger).filter(
                PopupTrigger.trigger_id == trigger_id,
                PopupTrigger.user_id == user_id
            )
            if task_id:
                query = query.filter(PopupTrigger.task_id == task_id)
            else:
                query = query.filter(PopupTrigger.task_id.is_(None))
            
            trigger = query.first()
            if trigger:
                if helpful is not None:
                    trigger.helpful = helpful
                if response is not None:
                    trigger.last_response = response
                if comment is not None:
                    trigger.last_comment = comment
                trigger.updated_at = datetime.utcnow()
        
        self._safe_db_operation(op)
    
    def check_cooldown(self, trigger_id: str, cooldown_hours: int = 24, 
                      user_id: str = 'default', task_id: Optional[str] = None) -> bool:
        """
        Check if trigger is in cooldown period.
        Returns True if trigger can fire (not in cooldown), False if in cooldown.
        """
        state = self.get_trigger_state(trigger_id, user_id, task_id)
        if not state or not state.get('last_shown_at'):
            return True  # Never shown, can fire
        
        try:
            last_shown = datetime.fromisoformat(state['last_shown_at'].replace(' ', 'T'))
            cooldown_end = last_shown + timedelta(hours=cooldown_hours)
            return datetime.utcnow() >= cooldown_end
        except (ValueError, TypeError, AttributeError):
            # If we can't parse the date, allow trigger to fire
            return True
    
    def get_daily_popup_count(self, user_id: str = 'default', date: Optional[datetime] = None) -> int:
        """Get count of popups shown today for a user."""
        if date is None:
            date = datetime.utcnow()
        
        def op(session):
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            
            count = session.query(PopupResponse).filter(
                PopupResponse.user_id == user_id,
                PopupResponse.created_at >= start_of_day,
                PopupResponse.created_at < end_of_day
            ).count()
            
            return count
        
        return self._safe_db_operation(op, fallback_value=0)
    
    def log_popup_response(self, trigger_id: str, response_value: Optional[str] = None,
                           helpful: Optional[bool] = None, comment: Optional[str] = None,
                           context: Optional[Dict[str, Any]] = None,
                           user_id: str = 'default', task_id: Optional[str] = None,
                           instance_id: Optional[str] = None):
        """Log a popup response."""
        def op(session):
            response = PopupResponse(
                trigger_id=trigger_id,
                user_id=user_id,
                task_id=task_id,
                instance_id=instance_id,
                response_value=response_value,
                helpful=helpful,
                comment=comment,
                context=context or {}
            )
            session.add(response)
        
        self._safe_db_operation(op)
    
    def get_trigger_tier(self, trigger_id: str, user_id: str = 'default', task_id: Optional[str] = None) -> int:
        """
        Get tier level for a trigger based on count.
        Tier 0 = first time, Tier 1-2 = repeats, Tier 3+ = habitual.
        """
        state = self.get_trigger_state(trigger_id, user_id, task_id)
        if not state:
            return 0
        
        count = state.get('count', 0)
        if count == 0:
            return 0
        elif count <= 2:
            return 1
        elif count <= 5:
            return 2
        else:
            return 3
