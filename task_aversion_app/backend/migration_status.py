"""
Programmatic migration status check for app startup and health route.

Returns whether the database has all required migrations applied so the app
can refuse to serve or show a "Run migrations" screen when behind.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
# Lazy engine import to avoid circular import / early DB access
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from backend.database import engine as e
        _engine = e
    return _engine


def _check_table_exists(inspector, table_name: str) -> bool:
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def _check_column_exists(inspector, table_name: str, column_name: str) -> bool:
    try:
        columns = [c["name"] for c in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def _check_index_exists(inspector, table_name: str, index_name: str) -> bool:
    try:
        indexes = inspector.get_indexes(table_name)
        return index_name in [idx["name"] for idx in indexes]
    except Exception:
        return False


@dataclass
class MigrationStatus:
    """Result of migration status check."""

    ok: bool
    message: str
    command: str
    details: list[str]


def get_migration_status() -> MigrationStatus:
    """
    Check if the database has all required migrations applied.
    Works for both PostgreSQL and SQLite (same schema expectations).
    When app uses CSV (USE_CSV=1 or no DATABASE_URL), returns ok=True (no check).
    """
    command = "python run_migrations.py"
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    use_csv = os.getenv("USE_CSV", "").strip().lower() in ("1", "true", "yes")
    if use_csv or not database_url:
        return MigrationStatus(
            ok=True,
            message="",
            command=command,
            details=[],
        )

    try:
        from sqlalchemy import inspect as sa_inspect
        engine = _get_engine()
        inspector = sa_inspect(engine)
    except Exception as e:
        return MigrationStatus(
            ok=False,
            message="Database connection failed.",
            command=command,
            details=[str(e)],
        )

    is_postgres = database_url.lower().startswith("postgresql")
    failures: list[str] = []

    # --- Required tables (001, 003, 004, 006, 007, 008, 009, 014) ---
    required_tables = [
        "tasks",
        "task_instances",
        "emotions",
        "user_preferences",
        "survey_responses",
        "users",
        "jobs",
        "job_task_mapping",
    ]
    for table in required_tables:
        if not _check_table_exists(inspector, table):
            failures.append(f"Table '{table}' is missing")

    if _check_table_exists(inspector, "tasks"):
        # Migration 002: routine fields on tasks
        for col in (
            "routine_frequency",
            "routine_days_of_week",
            "routine_time",
            "completion_window_hours",
            "completion_window_days",
        ):
            if not _check_column_exists(inspector, "tasks", col):
                failures.append(f"tasks.{col} missing (migration 002)")
                break
        # Migration 006: notes on tasks
        if not _check_column_exists(inspector, "tasks", "notes"):
            failures.append("tasks.notes missing (migration 006)")

    if _check_table_exists(inspector, "task_instances"):
        for col in ("due_at", "net_emotional", "serendipity_factor", "disappointment_factor"):
            if not _check_column_exists(inspector, "task_instances", col):
                failures.append(f"task_instances.{col} missing")
                break
        if is_postgres:
            required_indexes = [
                "idx_task_instances_task_status",
                "idx_task_instances_created_at",
                "idx_task_instances_user_active",
            ]
            for idx in required_indexes:
                if not _check_index_exists(inspector, "task_instances", idx):
                    failures.append(f"task_instances index '{idx}' missing")
                    break

    if _check_table_exists(inspector, "emotions"):
        if not _check_column_exists(inspector, "emotions", "user_id"):
            failures.append("emotions.user_id missing (migration 011)")

    if _check_table_exists(inspector, "user_preferences"):
        for col in ("timezone", "detected_tz"):
            if not _check_column_exists(inspector, "user_preferences", col):
                failures.append(f"user_preferences.{col} missing (migration 016)")
                break

    # User ID on main tables (010)
    for table in ("tasks", "task_instances", "survey_responses", "popup_triggers"):
        if _check_table_exists(inspector, table):
            has_user_id = _check_column_exists(inspector, table, "user_id") or _check_column_exists(
                inspector, table, "user_id_new"
            )
            if not has_user_id:
                failures.append(f"{table}.user_id (or user_id_new) missing (migration 010)")
                break

    if failures:
        return MigrationStatus(
            ok=False,
            message="Database migrations are behind. Apply them before using the app.",
            command=command,
            details=failures,
        )
    return MigrationStatus(
        ok=True,
        message="",
        command=command,
        details=[],
    )
