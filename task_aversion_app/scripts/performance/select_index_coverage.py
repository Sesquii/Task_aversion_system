#!/usr/bin/env python3
"""
SELECT-focused index coverage: whether indexes cover SELECT read paths.

Part of per-SQL-type coverage (SELECT). Complements pg_index_review.py and
catalog_indexes.py by cross-referencing (1) tables/columns touched by SELECTs
in the codebase with (2) indexes defined in the codebase. Teaches index coverage
and yields actionable counts: tables with SELECTs, tables with at least one index,
tables with SELECTs but no index (candidates for new indexes).

No database required (static scan). Optional: set DATABASE_URL to include
live PostgreSQL index list in the report.

Usage:
  cd task_aversion_app
  python scripts/performance/select_index_coverage.py [--live]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from collections import defaultdict

# Model class name -> table name (must match database.py)
MODEL_TO_TABLE: dict[str, str] = {
    "User": "users",
    "Task": "tasks",
    "TaskInstance": "task_instances",
    "Emotion": "emotions",
    "PopupTrigger": "popup_triggers",
    "PopupResponse": "popup_responses",
    "Note": "notes",
    "UserPreferences": "user_preferences",
    "SurveyResponse": "survey_responses",
}


def tables_touched_by_selects(root: Path) -> dict[str, int]:
    """Scan app code for SELECT usage; return table -> count of SELECT sites."""
    tables: dict[str, int] = defaultdict(int)

    def extract_from_sql(text: str) -> set[str]:
        out: set[str] = set()
        for m in re.finditer(
            r"(?:FROM|JOIN)\s+[\"']?(\w+)[\"']?(?:\s+AS\s+\w+)?(?:\s+|,|$)",
            text,
            re.IGNORECASE,
        ):
            out.add(m.group(1).lower())
        return out

    exclude = ("venv", ".venv", "__pycache__", "SQLite_migration", "PostgreSQL_migration")
    include_dirs = ("backend", "ui")
    for p in root.rglob("*.py"):
        if any(ex in p.parts for ex in exclude):
            continue
        rel = p.relative_to(root)
        if str(rel) != "app.py" and (not rel.parts or rel.parts[0] not in include_dirs):
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for m in re.finditer(r"session\.query\s*\(\s*(\w+)", content):
            if m.group(1) in MODEL_TO_TABLE:
                tables[MODEL_TO_TABLE[m.group(1)]] += 1
        for line in content.splitlines():
            if re.search(r"SELECT\s+", line, re.IGNORECASE) and re.search(
                r"FROM\s+\w+", line, re.IGNORECASE
            ):
                if "'" in line or '"' in line:
                    for t in extract_from_sql(line):
                        tables[t] += 1

    return dict(tables)


def tables_with_indexes_in_codebase(root: Path) -> set[str]:
    """Scan migrations and backend for CREATE INDEX / Index(); return set of table names."""
    tables_with_index: set[str] = set()
    model_tables: set[str] = set()

    candidates = [
        root / "backend" / "database.py",
        root / "backend" / "add_database_indexes.py",
    ]
    for d in ["PostgreSQL_migration", "SQLite_migration"]:
        mig = root / d
        if mig.is_dir():
            candidates.extend(mig.glob("*.py"))

    for path in candidates:
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if path.name == "database.py":
            for m in re.finditer(r"__tablename__\s*=\s*[\'\"]([\w_]+)[\'\"]", content):
                model_tables.add(m.group(1))

        for m in re.finditer(
            r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?\w+\s+ON\s+[\"']?(\w+)[\"']?\s*\([^)]+\)",
            content,
            re.IGNORECASE,
        ):
            tables_with_index.add(m.group(1).lower())
        for m in re.finditer(
            r"CREATE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?\w+\s+ON\s+[\"']?(\w+)[\"']?\s+USING",
            content,
            re.IGNORECASE,
        ):
            tables_with_index.add(m.group(1).lower())
        for _ in re.finditer(r"Index\s*\(\s*[\'\"]\w+[\'\"]\s*,", content):
            tables_with_index.update(model_tables)
            break
        for _ in re.finditer(r"Column\s*\(\s*\w+.*?index\s*=\s*True", content, re.IGNORECASE | re.DOTALL):
            tables_with_index.update(model_tables)
            break

    return tables_with_index


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SELECT-focused: index coverage for SELECT read paths (static)"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also query PostgreSQL for current indexes (requires DATABASE_URL)",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent.parent
    if not root.is_dir():
        print(f"[FAIL] Root not found: {root}")
        return 1

    tables_select = tables_touched_by_selects(root)
    tables_index = tables_with_indexes_in_codebase(root)

    tables_with_selects = set(tables_select.keys())
    uncovered = tables_with_selects - tables_index
    covered = tables_with_selects & tables_index

    print("=" * 72)
    print("SELECT INDEX COVERAGE (SELECT-focused; read paths vs indexes)")
    print("=" * 72)
    print(f"Root: {root}")
    print()
    print("--- Actionable counts ---")
    print(f"  Tables with SELECT usage (codebase):     {len(tables_with_selects)}")
    print(f"  Tables with at least one index (code):   {len(tables_index)}")
    print(f"  SELECT tables covered by an index:      {len(covered)}")
    print(f"  SELECT tables with no index in code:    {len(uncovered)}")
    print()

    if tables_with_selects:
        print("--- Tables touched by SELECTs (by site count) ---")
        for t in sorted(tables_with_selects, key=lambda x: -tables_select.get(x, 0)):
            c = tables_select.get(t, 0)
            status = "index in code" if t in tables_index else "no index in code"
            print(f"  {t:25}  sites={c:4d}  {status}")
        print()

    if uncovered:
        print("--- SELECT tables with no index in codebase (review for new indexes) ---")
        for t in sorted(uncovered, key=lambda x: -tables_select.get(x, 0)):
            print(f"  {t}")
        print()

    if args.live:
        database_url = os.getenv("DATABASE_URL", "")
        if database_url.startswith("postgresql"):
            try:
                from sqlalchemy import create_engine, text
            except ImportError:
                print("[WARN] sqlalchemy not available; skipping live index list.")
            else:
                engine = create_engine(database_url, pool_pre_ping=True)
                with engine.connect() as conn:
                    r = conn.execute(
                        text(
                            "SELECT tablename FROM pg_indexes WHERE schemaname = 'public'"
                        )
                    )
                    live_tables = {row[0].lower() for row in r}
                still_uncovered = tables_with_selects - live_tables
                print("--- Live PostgreSQL: SELECT tables still without index ---")
                if still_uncovered:
                    for t in sorted(still_uncovered):
                        print(f"  {t}")
                else:
                    print("  (none; all SELECT tables have at least one index in DB)")
                print()
        else:
            print("[WARN] DATABASE_URL not PostgreSQL; --live skipped.")

    print("[INFO] SELECT-focused for per-SQL-type coverage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
