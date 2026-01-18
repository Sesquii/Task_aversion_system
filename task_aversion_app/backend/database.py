# backend/database.py
"""
Database models and connection management for SQL migration.
Supports both SQLite (local/dev) and PostgreSQL (production) via DATABASE_URL.
"""
import os
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, JSON, Text, Float, ForeignKey, Index, text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.pool import StaticPool

# Import JSONB for PostgreSQL (used when DATABASE_URL is PostgreSQL)
# JSONB provides better performance and supports GIN indexes
# Note: JSONB is only used at table creation time - application code treats them the same
try:
    from sqlalchemy.dialects.postgresql import JSONB
    JSONB_AVAILABLE = True
except ImportError:
    JSONB_AVAILABLE = False
    JSONB = JSON  # Fallback to JSON if postgresql dialect not available

def get_json_type():
    """
    Return appropriate JSON type based on database.
    Returns JSONB for PostgreSQL (better performance, supports indexes) or JSON for SQLite.
    """
    if DATABASE_URL.startswith('postgresql') and JSONB_AVAILABLE:
        return JSONB
    else:
        return JSON

# Base class for all models
Base = declarative_base()

# Database connection configuration
# Default to SQLite for local development
# Set DATABASE_URL environment variable for PostgreSQL: postgresql://user:password@host:port/dbname
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/task_aversion.db')

# Create engine with appropriate settings
if DATABASE_URL.startswith('sqlite'):
    # SQLite-specific settings. StaticPool reuses a single connection so PRAGMA
    # table_info runs once per table per process instead of per connection.
    engine = create_engine(
        DATABASE_URL,
        echo=False,  # Set to True for SQL query logging
        connect_args={'check_same_thread': False},  # Allow multi-threaded access
        poolclass=StaticPool,
    )
else:
    # PostgreSQL settings
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,
        max_overflow=10
    )

# Session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Track if database has been initialized (to avoid duplicate print messages)
_db_initialized = False

# Set up query logging (lightweight, can be disabled via env var)
if os.getenv('ENABLE_QUERY_LOGGING', '1').lower() in ('1', 'true', 'yes'):
    try:
        from backend.query_logger import setup_query_logging
        setup_query_logging(engine)
    except Exception as e:
        print(f"[Database] Warning: Failed to set up query logging: {e}")


def get_session():
    """Get a database session. Use as context manager or call close() manually."""
    return SessionLocal()


def init_db():
    """Initialize database by creating all tables. Idempotent - safe to call multiple times."""
    global _db_initialized
    
    # Ensure data directory exists for SQLite
    if DATABASE_URL.startswith('sqlite'):
        db_path = DATABASE_URL.replace('sqlite:///', '')
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
    
    # Create tables (idempotent operation)
    Base.metadata.create_all(engine)

    # Warm SQLite schema on the single StaticPool connection so PRAGMA table_info
    # runs at startup instead of on first user request.
    if DATABASE_URL.startswith('sqlite') and Base.metadata.tables:
        try:
            with engine.connect() as conn:
                for tbl in Base.metadata.tables.values():
                    try:
                        list(conn.execute(text(f'PRAGMA table_info("{tbl.name}")')))
                    except Exception:
                        pass
        except Exception as e:
            print(f"[Database] Schema pre-warm skipped: {e}")

    # Only print message once to avoid console spam
    if not _db_initialized:
        print(f"[Database] Initialized database at {DATABASE_URL}")
        _db_initialized = True


# ============================================================================
# SQLAlchemy Models
# ============================================================================

class User(Base):
    """
    User model for OAuth authentication.
    Stores authenticated user accounts (Google OAuth, etc.).
    """
    __tablename__ = 'users'
    
    # Primary key - INTEGER (not VARCHAR) for proper foreign key relationships
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User identification
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)  # Optional username (NOT unique - multiple users can have same name)
    
    # OAuth provider information
    google_id = Column(String(255), unique=True, nullable=True, index=True)  # Google OAuth ID
    oauth_provider = Column(String(50), default='google', nullable=False)  # 'google', 'github', etc.
    
    # Account status
    email_verified = Column(Boolean, default=True, nullable=False)  # Google emails are pre-verified
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    last_login = Column(DateTime, default=None, nullable=True)
    
    def to_dict(self) -> dict:
        """Convert model instance to dictionary."""
        return {
            'user_id': self.user_id,
            'email': self.email,
            'username': self.username,
            'google_id': self.google_id,
            'oauth_provider': self.oauth_provider,
            'email_verified': bool(self.email_verified),
            'is_active': bool(self.is_active),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }
    
    def __repr__(self):
        return f"<User(user_id={self.user_id}, email='{self.email}')>"


class Task(Base):
    """
    Task definition model (migrated from tasks.csv).
    Represents a task template that can have multiple instances.
    """
    __tablename__ = 'tasks'
    
    # Primary key
    task_id = Column(String, primary_key=True)  # Format: t{timestamp}
    
    # Basic task information
    name = Column(String, nullable=False)
    description = Column(Text, default='')
    type = Column(String, default='one-time')  # one-time, recurring, routine
    version = Column(Integer, default=1)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)  # Indexed for date range queries
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Task properties
    is_recurring = Column(Boolean, default=False)
    json_type = get_json_type()
    categories = Column(json_type, default=list)  # JSONB for PostgreSQL, JSON for SQLite
    default_estimate_minutes = Column(Integer, default=0)
    task_type = Column(String, default='Work', index=True)  # Work, Self care, etc. - Indexed for filtering
    default_initial_aversion = Column(String, default='')  # Optional default aversion value
    
    # Routine scheduling fields
    routine_frequency = Column(String, default='none')  # 'none', 'daily', 'weekly'
    routine_days_of_week = Column(json_type, default=list)  # JSONB for PostgreSQL, JSON for SQLite
    routine_time = Column(String, default='00:00')  # Time in HH:MM format (24-hour)
    completion_window_hours = Column(Integer, default=None)  # Hours to complete task after initialization without penalty
    completion_window_days = Column(Integer, default=None)  # Days to complete task after initialization without penalty
    
    # Shared notes field - notes are shared across all instances of this task template
    notes = Column(Text, default='')  # Runtime notes (separate from description which is set at task creation)
    
    # User association (nullable for existing anonymous data)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=True, index=True)
    
    def to_dict(self) -> dict:
        """Convert model instance to dictionary (compatible with CSV format)."""
        return {
            'task_id': self.task_id,
            'name': self.name,
            'description': self.description or '',
            'type': self.type,
            'version': str(self.version),
            'created_at': self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else '',
            'is_recurring': str(bool(self.is_recurring)),
            'categories': json.dumps(self.categories) if isinstance(self.categories, list) else (self.categories or '[]'),
            'default_estimate_minutes': str(self.default_estimate_minutes),
            'task_type': self.task_type or 'Work',
            'default_initial_aversion': self.default_initial_aversion or '',
            'routine_frequency': self.routine_frequency or 'none',
            'routine_days_of_week': json.dumps(self.routine_days_of_week) if isinstance(self.routine_days_of_week, list) else (self.routine_days_of_week or '[]'),
            'routine_time': self.routine_time or '00:00',
            'completion_window_hours': str(self.completion_window_hours) if self.completion_window_hours is not None else '',
            'completion_window_days': str(self.completion_window_days) if self.completion_window_days is not None else '',
            'notes': self.notes or '',
            'user_id': str(self.user_id) if self.user_id is not None else ''
        }
    
    def __repr__(self):
        return f"<Task(task_id='{self.task_id}', name='{self.name}')>"


class TaskInstance(Base):
    """
    Task instance model (migrated from task_instances.csv).
    Represents a single execution/attempt of a task.
    """
    __tablename__ = 'task_instances'
    
    # Primary key
    instance_id = Column(String, primary_key=True)  # Format: i{timestamp}
    
    # Foreign key to Task (optional for now, can add constraint later)
    task_id = Column(String, nullable=False, index=True)
    task_name = Column(String, nullable=False)
    task_version = Column(Integer, default=1)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    initialized_at = Column(DateTime, default=None, nullable=True)
    started_at = Column(DateTime, default=None, nullable=True)
    completed_at = Column(DateTime, default=None, nullable=True, index=True)  # Indexed for completed-only queries
    cancelled_at = Column(DateTime, default=None, nullable=True)
    
    # JSON data (raw data storage)
    # Use JSONB for PostgreSQL (better performance, supports GIN indexes) or JSON for SQLite
    # Application code treats them the same - SQLAlchemy handles conversion automatically
    json_type = get_json_type()
    predicted = Column(json_type, default=dict)  # JSONB for PostgreSQL, JSON for SQLite
    actual = Column(json_type, default=dict)  # JSONB for PostgreSQL, JSON for SQLite
    
    # Scores
    procrastination_score = Column(Float, default=None, nullable=True)
    proactive_score = Column(Float, default=None, nullable=True)
    behavioral_score = Column(Float, default=None, nullable=True)
    net_relief = Column(Float, default=None, nullable=True)
    behavioral_deviation = Column(Float, default=None, nullable=True)
    
    # Emotional factors (calculated from net_relief)
    serendipity_factor = Column(Float, default=None, nullable=True)  # Positive net_relief (pleasant surprise)
    disappointment_factor = Column(Float, default=None, nullable=True)  # Negative net_relief (disappointment)
    
    # Status flags
    is_completed = Column(Boolean, default=False, index=True)
    is_deleted = Column(Boolean, default=False, index=True)
    status = Column(String, default='active', index=True)  # active, initialized, completed, cancelled
    
    # Extracted attributes (for analytics)
    duration_minutes = Column(Float, default=None, nullable=True)
    delay_minutes = Column(Float, default=None, nullable=True)
    relief_score = Column(Float, default=None, nullable=True)
    cognitive_load = Column(Float, default=None, nullable=True)
    mental_energy_needed = Column(Float, default=None, nullable=True)
    task_difficulty = Column(Float, default=None, nullable=True)
    emotional_load = Column(Float, default=None, nullable=True)
    environmental_effect = Column(Float, default=None, nullable=True)
    skills_improved = Column(Text, default='')  # Comma-separated list stored as text
    
    # User association (nullable for existing anonymous data)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=True, index=True)
    
    def to_dict(self) -> dict:
        """Convert model instance to dictionary (compatible with CSV format)."""
        def format_datetime(dt):
            return dt.strftime("%Y-%m-%d %H:%M") if dt else ''
        
        return {
            'instance_id': self.instance_id,
            'task_id': self.task_id,
            'task_name': self.task_name,
            'task_version': str(self.task_version),
            'created_at': format_datetime(self.created_at),
            'initialized_at': format_datetime(self.initialized_at),
            'started_at': format_datetime(self.started_at),
            'completed_at': format_datetime(self.completed_at),
            'cancelled_at': format_datetime(self.cancelled_at),
            'predicted': json.dumps(self.predicted) if isinstance(self.predicted, dict) else (self.predicted or '{}'),
            'actual': json.dumps(self.actual) if isinstance(self.actual, dict) else (self.actual or '{}'),
            'procrastination_score': str(self.procrastination_score) if self.procrastination_score is not None else '',
            'proactive_score': str(self.proactive_score) if self.proactive_score is not None else '',
            'behavioral_score': str(self.behavioral_score) if self.behavioral_score is not None else '',
            'net_relief': str(self.net_relief) if self.net_relief is not None else '',
            'behavioral_deviation': str(self.behavioral_deviation) if self.behavioral_deviation is not None else '',
            'is_completed': str(bool(self.is_completed)),
            'is_deleted': str(bool(self.is_deleted)),
            'status': self.status or 'active',
            'duration_minutes': str(self.duration_minutes) if self.duration_minutes is not None else '',
            'delay_minutes': str(self.delay_minutes) if self.delay_minutes is not None else '',
            'relief_score': str(self.relief_score) if self.relief_score is not None else '',
            'cognitive_load': str(self.cognitive_load) if self.cognitive_load is not None else '',
            'mental_energy_needed': str(self.mental_energy_needed) if self.mental_energy_needed is not None else '',
            'task_difficulty': str(self.task_difficulty) if self.task_difficulty is not None else '',
            'emotional_load': str(self.emotional_load) if self.emotional_load is not None else '',
            'environmental_effect': str(self.environmental_effect) if self.environmental_effect is not None else '',
            'skills_improved': self.skills_improved or '',
            'serendipity_factor': str(self.serendipity_factor) if self.serendipity_factor is not None else '',
            'disappointment_factor': str(self.disappointment_factor) if self.disappointment_factor is not None else '',
            'user_id': str(self.user_id) if self.user_id is not None else ''
        }
    
    def __repr__(self):
        return f"<TaskInstance(instance_id='{self.instance_id}', task_id='{self.task_id}', status='{self.status}')>"
    
    # Composite indexes for common query patterns
    __table_args__ = (
        # Index for filtering by status and completion (common in list_active_instances)
        Index('idx_taskinstance_status_completed', 'status', 'is_completed', 'is_deleted'),
        # Index for task_id + completion status (common when getting instances for a task)
        Index('idx_taskinstance_task_completed', 'task_id', 'is_completed'),
    )


class Emotion(Base):
    """
    Emotion model (migrated from emotions.csv).
    Stores a list of emotions that users can select from.
    """
    __tablename__ = 'emotions'
    
    # Primary key
    emotion_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Emotion name (unique, case-insensitive matching handled in application logic)
    emotion = Column(String, nullable=False, unique=True, index=True)
    
    def to_dict(self) -> dict:
        """Convert model instance to dictionary (compatible with CSV format)."""
        return {
            'emotion': self.emotion
        }
    
    def __repr__(self):
        return f"<Emotion(emotion='{self.emotion}')>"


class PopupTrigger(Base):
    """
    Popup trigger state model.
    Tracks per-trigger counts, cooldowns, and user responses for popup system.
    """
    __tablename__ = 'popup_triggers'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User identifier (for future multi-user support, default to 'default')
    user_id = Column(String, default='default', nullable=False, index=True)
    
    # Trigger identifier (e.g., '7.1', '1.1', '2.1')
    trigger_id = Column(String, nullable=False, index=True)
    
    # Optional task_id for task-specific triggers
    task_id = Column(String, default=None, nullable=True, index=True)
    
    # Count of times this trigger has fired
    count = Column(Integer, default=0, nullable=False)
    
    # Last time this popup was shown
    last_shown_at = Column(DateTime, default=None, nullable=True)
    
    # User feedback: was this popup helpful?
    helpful = Column(Boolean, default=None, nullable=True)
    
    # Last response value (if applicable)
    last_response = Column(String, default=None, nullable=True)
    
    # Last comment/feedback from user
    last_comment = Column(Text, default=None, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self) -> dict:
        """Convert model instance to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'trigger_id': self.trigger_id,
            'task_id': self.task_id,
            'count': self.count,
            'last_shown_at': self.last_shown_at.strftime("%Y-%m-%d %H:%M:%S") if self.last_shown_at else None,
            'helpful': self.helpful,
            'last_response': self.last_response,
            'last_comment': self.last_comment,
            'created_at': self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            'updated_at': self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
    
    def __repr__(self):
        return f"<PopupTrigger(trigger_id='{self.trigger_id}', count={self.count})>"


class PopupResponse(Base):
    """
    Popup response log model.
    Stores detailed logs of popup shows and user responses.
    """
    __tablename__ = 'popup_responses'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User identifier
    user_id = Column(String, default='default', nullable=False, index=True)
    
    # Trigger identifier
    trigger_id = Column(String, nullable=False, index=True)
    
    # Optional task_id and instance_id for context
    task_id = Column(String, default=None, nullable=True, index=True)
    instance_id = Column(String, default=None, nullable=True, index=True)
    
    # Response data
    response_value = Column(String, default=None, nullable=True)  # e.g., 'continue', 'edit', 'yes', 'no'
    helpful = Column(Boolean, default=None, nullable=True)
    comment = Column(Text, default=None, nullable=True)
    
    # Context data (JSON) - stores completion context, survey context, etc.
    json_type = get_json_type()
    context = Column(json_type, default=dict)  # JSONB for PostgreSQL, JSON for SQLite
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self) -> dict:
        """Convert model instance to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'trigger_id': self.trigger_id,
            'task_id': self.task_id,
            'instance_id': self.instance_id,
            'response_value': self.response_value,
            'helpful': self.helpful,
            'comment': self.comment,
            'context': json.dumps(self.context) if isinstance(self.context, dict) else (self.context or '{}'),
            'created_at': self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
    
    def __repr__(self):
        return f"<PopupResponse(trigger_id='{self.trigger_id}', response='{self.response_value}')>"


class Note(Base):
    """
    Note model (migrated from notes.csv).
    Stores behavioral and emotional pattern observations.
    """
    __tablename__ = 'notes'
    
    # Primary key
    note_id = Column(String, primary_key=True)  # Format: note-{timestamp_ms}
    
    # Note content
    content = Column(Text, nullable=False)
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # User association (nullable for existing anonymous data)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=True, index=True)
    
    def to_dict(self) -> dict:
        """Convert model instance to dictionary (compatible with CSV format)."""
        return {
            'note_id': self.note_id,
            'content': self.content,
            'timestamp': self.timestamp.isoformat() if self.timestamp else '',
            'user_id': str(self.user_id) if self.user_id is not None else ''
        }
    
    def __repr__(self):
        return f"<Note(note_id='{self.note_id}', timestamp='{self.timestamp}')>"


class UserPreferences(Base):
    """
    User preferences model (migrated from user_preferences.csv).
    Stores user settings, preferences, and state information.
    """
    __tablename__ = 'user_preferences'
    
    # Primary key
    user_id = Column(String, primary_key=True)  # User identifier
    
    # Tutorial/onboarding preferences
    tutorial_completed = Column(Boolean, default=False)
    tutorial_choice = Column(String, default='')
    tutorial_auto_show = Column(Boolean, default=True)
    tooltip_mode_enabled = Column(Boolean, default=True)
    survey_completed = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    last_active = Column(DateTime, default=datetime.utcnow, nullable=True)
    
    # Gap handling preference
    gap_handling = Column(String, default=None, nullable=True)  # 'continue_as_is' or 'fresh_start'
    
    # JSON fields for complex preferences
    json_type = get_json_type()
    persistent_emotion_values = Column(json_type, default=dict)  # JSONB for PostgreSQL, JSON for SQLite
    productivity_history = Column(json_type, default=list)  # JSONB for PostgreSQL, JSON for SQLite
    productivity_goal_settings = Column(json_type, default=dict)  # JSONB for PostgreSQL, JSON for SQLite
    monitored_metrics_config = Column(json_type, default=dict)  # JSONB for PostgreSQL, JSON for SQLite
    execution_score_chunk_state = Column(json_type, default=None, nullable=True)  # JSONB for PostgreSQL, JSON for SQLite
    productivity_settings = Column(json_type, default=dict)  # JSONB for PostgreSQL, JSON for SQLite
    
    # Additional JSON fields that may be dynamically added (stored as JSON)
    # Note: The CSV may have additional fields that are stored as JSON strings
    # These will be handled dynamically by the migration script
    
    def to_dict(self) -> dict:
        """Convert model instance to dictionary (compatible with CSV format)."""
        import json
        
        def format_datetime(dt):
            return dt.isoformat() if dt else ''
        
        return {
            'user_id': self.user_id,
            'tutorial_completed': str(bool(self.tutorial_completed)),
            'tutorial_choice': self.tutorial_choice or '',
            'tutorial_auto_show': str(bool(self.tutorial_auto_show)),
            'tooltip_mode_enabled': str(bool(self.tooltip_mode_enabled)),
            'survey_completed': str(bool(self.survey_completed)),
            'created_at': format_datetime(self.created_at),
            'last_active': format_datetime(self.last_active),
            'gap_handling': self.gap_handling or '',
            'persistent_emotion_values': json.dumps(self.persistent_emotion_values) if isinstance(self.persistent_emotion_values, dict) else (self.persistent_emotion_values or '{}'),
            'productivity_history': json.dumps(self.productivity_history) if isinstance(self.productivity_history, list) else (self.productivity_history or '[]'),
            'productivity_goal_settings': json.dumps(self.productivity_goal_settings) if isinstance(self.productivity_goal_settings, dict) else (self.productivity_goal_settings or '{}'),
            'monitored_metrics_config': json.dumps(self.monitored_metrics_config) if isinstance(self.monitored_metrics_config, dict) else (self.monitored_metrics_config or '{}'),
            'execution_score_chunk_state': json.dumps(self.execution_score_chunk_state) if isinstance(self.execution_score_chunk_state, dict) else (self.execution_score_chunk_state or ''),
            'productivity_settings': json.dumps(self.productivity_settings) if isinstance(self.productivity_settings, dict) else (self.productivity_settings or '{}'),
        }
    
    def __repr__(self):
        return f"<UserPreferences(user_id='{self.user_id}', tutorial_completed={self.tutorial_completed})>"


class SurveyResponse(Base):
    """
    Survey response model (migrated from survey_responses.csv).
    Stores individual survey question responses from users.
    """
    __tablename__ = 'survey_responses'
    
    # Primary key
    response_id = Column(String, primary_key=True)  # Format: srv-{timestamp}
    
    # User identifier
    user_id = Column(String, nullable=False, index=True)
    
    # Survey question information
    question_category = Column(String, nullable=False, index=True)  # Category of question
    question_id = Column(String, nullable=False)  # Unique question identifier
    
    # Response data
    response_value = Column(String, default='', nullable=True)  # Numeric or coded response
    response_text = Column(Text, default='', nullable=True)  # Free-form text response
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Composite index for common queries (user_id + category, user_id + timestamp)
    __table_args__ = (
        Index('idx_survey_user_category', 'user_id', 'question_category'),
        Index('idx_survey_user_timestamp', 'user_id', 'timestamp'),
    )
    
    def to_dict(self) -> dict:
        """Convert model instance to dictionary (compatible with CSV format)."""
        def format_datetime(dt):
            return dt.isoformat() if dt else ''
        
        return {
            'user_id': self.user_id,
            'response_id': self.response_id,
            'question_category': self.question_category,
            'question_id': self.question_id,
            'response_value': self.response_value or '',
            'response_text': self.response_text or '',
            'timestamp': format_datetime(self.timestamp),
        }
    
    def __repr__(self):
        return f"<SurveyResponse(response_id='{self.response_id}', user_id='{self.user_id}', question_category='{self.question_category}')>"


# Future models will be added here as needed

