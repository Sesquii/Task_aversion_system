# backend/database.py
"""
Database models and connection management for SQL migration.
Supports both SQLite (local/dev) and PostgreSQL (production) via DATABASE_URL.
"""
import os
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, JSON, Text
from sqlalchemy.orm import sessionmaker, declarative_base
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
            'completion_window_days': str(self.completion_window_days) if self.completion_window_days is not None else ''
        }
    
    def __repr__(self):
        return f"<Task(task_id='{self.task_id}', name='{self.name}')>"


# Future models will be added here:
# - TaskInstance (from task_instances.csv)
# - Emotion (from emotions.csv)
# - User (for future multi-user support)
# - Survey (for future survey system)

