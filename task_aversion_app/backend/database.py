# backend/database.py
"""
Database models and connection management for SQL migration.
Supports both SQLite (local/dev) and PostgreSQL (production) via DATABASE_URL.
"""
import os
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, JSON, Text, Float, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.exc import OperationalError, IntegrityError

# Base class for all models
Base = declarative_base()

# Database connection configuration
# Default to SQLite for local development
# Set DATABASE_URL environment variable for PostgreSQL: postgresql://user:password@host:port/dbname
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/task_aversion.db')

# Create engine with appropriate settings
if DATABASE_URL.startswith('sqlite'):
    # SQLite-specific settings
    engine = create_engine(
        DATABASE_URL,
        echo=False,  # Set to True for SQL query logging
        connect_args={'check_same_thread': False}  # Allow multi-threaded access
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


def get_session():
    """Get a database session. Use as context manager or call close() manually."""
    return SessionLocal()


def init_db():
    """Initialize database by creating all tables."""
    # Ensure data directory exists for SQLite
    if DATABASE_URL.startswith('sqlite'):
        db_path = DATABASE_URL.replace('sqlite:///', '')
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
    
    Base.metadata.create_all(engine)
    print(f"[Database] Initialized database at {DATABASE_URL}")


# ============================================================================
# SQLAlchemy Models
# ============================================================================

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Task properties
    is_recurring = Column(Boolean, default=False)
    categories = Column(JSON, default=list)  # List of category strings
    default_estimate_minutes = Column(Integer, default=0)
    task_type = Column(String, default='Work')  # Work, Self care, etc.
    default_initial_aversion = Column(String, default='')  # Optional default aversion value
    
    # Routine scheduling fields
    routine_frequency = Column(String, default='none')  # 'none', 'daily', 'weekly'
    routine_days_of_week = Column(JSON, default=list)  # List of day numbers (0=Monday, 6=Sunday) for weekly
    routine_time = Column(String, default='00:00')  # Time in HH:MM format (24-hour)
    completion_window_hours = Column(Integer, default=None)  # Hours to complete task after initialization without penalty
    completion_window_days = Column(Integer, default=None)  # Days to complete task after initialization without penalty
    
    # Shared notes field - notes are shared across all instances of this task template
    notes = Column(Text, default='')  # Runtime notes (separate from description which is set at task creation)
    
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
            'notes': self.notes or ''
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
    completed_at = Column(DateTime, default=None, nullable=True)
    cancelled_at = Column(DateTime, default=None, nullable=True)
    
    # JSON data (raw data storage)
    predicted = Column(JSON, default=dict)  # Predicted values as JSON
    actual = Column(JSON, default=dict)  # Actual values as JSON
    
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
        }
    
    def __repr__(self):
        return f"<TaskInstance(instance_id='{self.instance_id}', task_id='{self.task_id}', status='{self.status}')>"


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


# Future models will be added here:
# - User (for future multi-user support)
# - Survey (for future survey system)

