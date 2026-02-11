#!/usr/bin/env python3
"""
Settings page: static scan of query sites in Settings-related code by area.

Targets the Settings page (/settings, ui/settings_page.py) and its main areas:
settings landing, CSV import path, score weights, productivity settings,
and cancellation penalties. Scans Settings UI files and the backend modules
they call (user_state is CSV-backed; csv_import, csv_export, analytics,
instance_manager have DB query sites). Reports query-site counts per file
and maps each file to the Settings area(s) it serves. No DB required.

Usage:
  cd task_aversion_app
  python scripts/performance/settings_query_sites_static.py [--by-area]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from collections import defaultdict


# File -> Settings area(s) it serves (for reporting)
SETTINGS_FILE_AREAS: dict[str, list[str]] = {
    "ui/settings_page.py": ["settings landing", "CSV import", "CSV export", "score weights link", "productivity settings link", "cancellation penalties link"],
    "ui/composite_score_weights_page.py": ["score weights"],
    "ui/productivity_settings_page.py": ["productivity settings"],
    "ui/cancellation_penalties_page.py": ["cancellation penalties"],
    "backend/csv_import.py": ["CSV import"],
    "backend/csv_export.py": ["CSV export"],
    "backend/analytics.py": ["score weights", "productivity settings"],
    "backend/instance_manager.py": ["settings landing"],
    "backend/task_manager.py": ["productivity settings"],
    "backend/user_state.py": ["settings landing", "score weights", "productivity settings", "cancellation penalties"],
}


def count_query_sites(text: str) -> dict[str, int]:
    """Count session.query, .execute, and raw SQL patterns. Excludes PRAGMA."""
    return {
        "session.query": len(re.findall(r"session\.query\s*\(", text)),
        "execute": len(re.findall(r"\.execute\s*\(\s*", text))
        + len(re.findall(r"execute\s*\(\s*text\s*\(|conn\.execute\s*\(", text)),
        "SELECT": len(re.findall(r"text\s*\(\s*[\'\"].*?SELECT\s+", text, re.IGNORECASE | re.DOTALL))
        + len(re.findall(r"[\'\"].*?SELECT\s+.*?FROM\s+", text, re.IGNORECASE | re.DOTALL)),
        "INSERT": len(re.findall(r"text\s*\(\s*[\'\"].*?INSERT\s+", text, re.IGNORECASE | re.DOTALL))
        + len(re.findall(r"[\'\"].*?INSERT\s+INTO\s+", text, re.IGNORECASE | re.DOTALL)),
        "UPDATE": len(re.findall(r"text\s*\(\s*[\'\"].*?UPDATE\s+", text, re.IGNORECASE | re.DOTALL))
        + len(re.findall(r"[\'\"].*?UPDATE\s+\w+\s+SET\s+", text, re.IGNORECASE | re.DOTALL)),
        "DELETE": len(re.findall(r"text\s*\(\s*[\'\"].*?DELETE\s+", text, re.IGNORECASE | re.DOTALL))
        + len(re.findall(r"[\'\"].*?DELETE\s+FROM\s+", text, re.IGNORECASE | re.DOTALL)),
    }


def total_pg_relevant(counts: dict[str, int]) -> int:
    """Sum of PostgreSQL-relevant query sites (exclude PRAGMA)."""
    return sum(counts.values())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Settings-related query sites by file and area (static; no DB)"
    )
    parser.add_argument(
        "--by-area",
        action="store_true",
        help="Group output by Settings area instead of by file",
    )
    args = parser.parse_args()

    # Script lives in task_aversion_app/scripts/performance/
    base = Path(__file__).resolve().parent.parent.parent
    if not (base / "ui" / "settings_page.py").is_file():
        print(f"[FAIL] App root not found: {base}")
        return 1

    file_counts: dict[str, dict[str, int]] = {}
    for rel_path in SETTINGS_FILE_AREAS:
        path = base / rel_path
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        file_counts[rel_path] = count_query_sites(text)

    print("=" * 72)
    print("SETTINGS QUERY SITES (static; by file and area)")
    print("=" * 72)
    print("Targets: Settings page (landing, CSV import, score weights,")
    print("         productivity settings, cancellation penalties).")
    print()

    if args.by_area:
        area_to_files: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for rel_path, counts in file_counts.items():
            total = total_pg_relevant(counts)
            if total == 0:
                continue
            for area in SETTINGS_FILE_AREAS.get(rel_path, ["other"]):
                area_to_files[area].append((rel_path, total))
        print("--- By Settings area ---")
        for area in sorted(area_to_files.keys()):
            rows = area_to_files[area]
            rows.sort(key=lambda x: -x[1])
            print(f"  {area}:")
            for rel_path, total in rows:
                print(f"    {total:4d}  {rel_path}")
            print()
    else:
        print("--- By file (Settings-related only) ---")
        rows = [(path, total_pg_relevant(c), c) for path, c in file_counts.items()]
        rows.sort(key=lambda x: -x[1])
        for rel_path, total, counts in rows:
            areas = ", ".join(SETTINGS_FILE_AREAS.get(rel_path, []))
            if total == 0:
                print(f"  {rel_path}  (0)  areas: {areas}")
            else:
                parts = [f"{k}={v}" for k, v in counts.items() if v > 0]
                print(f"  {total:4d}  {rel_path}")
                print(f"        areas: {areas}")
                print(f"        sites: {', '.join(parts)}")
        print()

    print("[INFO] user_state is CSV-backed; csv_import and csv_export are the main")
    print("       DB-heavy paths for Settings (import/export).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
