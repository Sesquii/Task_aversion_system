#!/usr/bin/env python
"""List users in the database with basic activity stats.

Useful to see how many accounts exist and who has been active (e.g. for
multi-user apps where you're not sure who else has signed up).

Usage (from task_aversion_app):
    python scripts/list_users.py
    python scripts/list_users.py --verbose   # include task/instance counts per user

Requires DATABASE_URL in .env or environment. Works with SQLite and PostgreSQL.
"""
import os
import sys
from argparse import ArgumentParser

# Add parent so "backend" and .env resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///data/task_aversion.db"

from backend.database import get_session, User, Task, TaskInstance


def main(verbose: bool = False) -> None:
    try:
        with get_session() as session:
            users = session.query(User).order_by(User.user_id).all()
    except Exception as e:
        print(f"[FAIL] Could not query users: {e}")
        print("Ensure DATABASE_URL points to a DB that has a 'users' table (run migrations if needed).")
        sys.exit(1)
    total = len(users)
    with get_session() as session:
        print(f"Users in database: {total}")
        if total == 0:
            print("No users found. Table may be empty or you may be using CSV auth.")
            return
        print("-" * 60)
        for u in users:
            email = (u.email or "").strip() or "(no email)"
            last_login = u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "never"
            active = "active" if u.is_active else "inactive"
            line = f"  id={u.user_id}  email={email}  last_login={last_login}  {active}"
            if verbose:
                task_count = session.query(Task).filter(Task.user_id == u.user_id).count()
                inst_count = session.query(TaskInstance).filter(TaskInstance.user_id == u.user_id).count()
                line += f"  tasks={task_count}  instances={inst_count}"
            print(line)
        print("-" * 60)
        print(f"Total: {total} user(s)")


if __name__ == "__main__":
    parser = ArgumentParser(description="List users in the database")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show task and instance counts per user")
    args = parser.parse_args()
    main(verbose=args.verbose)
