# backend/recommendation_logger.py
"""
Logging system for recommendation effectiveness tracking.

Tracks:
- When recommendations are generated
- What recommendations were shown
- What the user actually selected/did
- Context (time, metrics selected, filters)
- Outcomes (did they complete the recommended task?)
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

# Setup logging directory
LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'logs')
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

# Recommendation log file (JSONL format - one JSON object per line)
REC_LOG_FILE = os.path.join(LOG_DIR, f'recommendations_{datetime.now().strftime("%Y%m%d")}.jsonl')

# Standard Python logger for debugging
logger = logging.getLogger('recommendation_logger')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler(
        os.path.join(LOG_DIR, f'recommendation_debug_{datetime.now().strftime("%Y%m%d")}.log'),
        encoding='utf-8'
    )
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False


class RecommendationLogger:
    """Logs recommendation events for analysis."""
    
    @staticmethod
    def log_recommendation_generated(
        mode: str,
        metrics: List[str],
        filters: Optional[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
        session_id: Optional[str] = None
    ):
        """Log when recommendations are generated.
        
        Args:
            mode: 'templates' or 'instances'
            metrics: List of metric keys used for ranking
            filters: Filters applied (duration, task_type, etc.)
            recommendations: List of recommendation dicts returned
            session_id: Optional session identifier
        """
        try:
            event = {
                'event_type': 'recommendation_generated',
                'timestamp': datetime.now().isoformat(),
                'mode': mode,
                'metrics': metrics,
                'filters': filters or {},
                'recommendation_count': len(recommendations),
                'recommendations': [
                    {
                        'task_id': rec.get('task_id'),
                        'instance_id': rec.get('instance_id'),
                        'task_name': rec.get('task_name') or rec.get('title'),
                        'score': rec.get('score'),
                        'rank': idx + 1,
                        'metric_values': rec.get('metric_values', {}),
                    }
                    for idx, rec in enumerate(recommendations)
                ],
                'session_id': session_id,
            }
            
            # Write to JSONL file (append mode)
            with open(REC_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event) + '\n')
            
            logger.info(f"Logged recommendation generation: {mode} mode, {len(recommendations)} recommendations")
            
        except Exception as e:
            logger.error(f"Failed to log recommendation generation: {e}", exc_info=True)
    
    @staticmethod
    def log_recommendation_selected(
        task_id: Optional[str],
        instance_id: Optional[str],
        task_name: Optional[str],
        recommendation_score: Optional[float],
        action: str,  # 'initialize', 'start', 'resume'
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Log when user selects a recommendation.
        
        Args:
            task_id: Task ID that was selected
            instance_id: Instance ID if applicable
            task_name: Name of the task
            recommendation_score: Score of the recommendation
            action: Action taken ('initialize', 'start', 'resume')
            session_id: Optional session identifier
            context: Additional context (metrics used, filters, etc.)
        """
        try:
            event = {
                'event_type': 'recommendation_selected',
                'timestamp': datetime.now().isoformat(),
                'task_id': task_id,
                'instance_id': instance_id,
                'task_name': task_name,
                'recommendation_score': recommendation_score,
                'action': action,
                'session_id': session_id,
                'context': context or {},
            }
            
            with open(REC_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event) + '\n')
            
            logger.info(f"Logged recommendation selection: {task_name} ({action})")
            
        except Exception as e:
            logger.error(f"Failed to log recommendation selection: {e}", exc_info=True)
    
    @staticmethod
    def log_recommendation_outcome(
        task_id: Optional[str],
        instance_id: Optional[str],
        task_name: Optional[str],
        outcome: str,  # 'completed', 'cancelled', 'abandoned'
        completion_time_minutes: Optional[float] = None,
        actual_relief: Optional[float] = None,
        predicted_relief: Optional[float] = None,
        session_id: Optional[str] = None
    ):
        """Log the outcome of a recommended task.
        
        Args:
            task_id: Task ID
            instance_id: Instance ID
            task_name: Name of the task
            outcome: 'completed', 'cancelled', or 'abandoned'
            completion_time_minutes: Time taken to complete (if completed)
            actual_relief: Actual relief score (if completed)
            predicted_relief: Predicted relief score (from recommendation)
            session_id: Optional session identifier
        """
        try:
            event = {
                'event_type': 'recommendation_outcome',
                'timestamp': datetime.now().isoformat(),
                'task_id': task_id,
                'instance_id': instance_id,
                'task_name': task_name,
                'outcome': outcome,
                'completion_time_minutes': completion_time_minutes,
                'actual_relief': actual_relief,
                'predicted_relief': predicted_relief,
                'relief_accuracy': (
                    abs(actual_relief - predicted_relief) 
                    if (actual_relief is not None and predicted_relief is not None) 
                    else None
                ),
                'session_id': session_id,
            }
            
            with open(REC_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event) + '\n')
            
            logger.info(f"Logged recommendation outcome: {task_name} ({outcome})")
            
        except Exception as e:
            logger.error(f"Failed to log recommendation outcome: {e}", exc_info=True)
    
    @staticmethod
    def log_task_completed_outside_recommendations(
        task_id: str,
        instance_id: Optional[str],
        task_name: str,
        was_recommended: bool = False,
        recommendation_score: Optional[float] = None,
        session_id: Optional[str] = None
    ):
        """Log when a task is completed that wasn't from recommendations.
        
        Useful for comparing recommended vs non-recommended task completion rates.
        
        Args:
            task_id: Task ID
            instance_id: Instance ID
            task_name: Name of the task
            was_recommended: Whether this task was in recent recommendations
            recommendation_score: Score if it was recommended
            session_id: Optional session identifier
        """
        try:
            event = {
                'event_type': 'task_completed',
                'timestamp': datetime.now().isoformat(),
                'task_id': task_id,
                'instance_id': instance_id,
                'task_name': task_name,
                'was_recommended': was_recommended,
                'recommendation_score': recommendation_score,
                'session_id': session_id,
            }
            
            with open(REC_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event) + '\n')
            
            logger.info(f"Logged task completion: {task_name} (recommended: {was_recommended})")
            
        except Exception as e:
            logger.error(f"Failed to log task completion: {e}", exc_info=True)


# Global instance
recommendation_logger = RecommendationLogger()
