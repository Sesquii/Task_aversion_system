#!/usr/bin/env python3
"""
Static analysis: count database query sites across the codebase.

Scans Python files for:
  - session.query(
  - .execute(
  - execute(text(
  - Raw SQL strings containing SELECT / PRAGMA (heuristic)

Outputs per-file and per-directory counts to find the most query-heavy modules.
Use this to identify subsystems that may contribute to high query volume on page load.

Usage:
  cd task_aversion_app
  python scripts/performance/analyze_static_queries.py [--top N] [--by-dir]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from collections import defaultdict

# Skip files larger than this to avoid timeouts (regex cost scales with file size)
MAX_FILE_BYTES = 1_500_000  # 1.5 MB


def count_in_file(path: Path) -> dict[str, int]:
    """Count query-related patterns in a single file. Returns dict of pattern -> count."""
    try:
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            return {}
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    counts = {
        "session.query": len(re.findall(r"session\.query\s*\(", text)),
        "execute(": len(re.findall(r"\.execute\s*\(\s*", text))
        + len(re.findall(r"execute\s*\(\s*text\s*\(|conn\.execute\s*\(", text)),
        "text(sql": len(re.findall(r"text\s*\(\s*[\'\"]", text)),  # text("SELECT...") style
        "SELECT (string)": 0,
        "PRAGMA": len(re.findall(r"PRAGMA\s+", text, re.IGNORECASE)),
    }
    # Heuristic: SELECT inside a string — line-by-line only to avoid catastrophic backtracking
    # on large files (full-file regex with DOTALL was causing timeouts)
    for line in text.splitlines():
        if re.search(r"[\'\"].*SELECT\s+", line, re.IGNORECASE) or re.search(
            r"SELECT\s+.*[\'\"].*\)", line, re.IGNORECASE
        ):
            counts["SELECT (string)"] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Static query-site analysis")
    parser.add_argument("--top", type=int, default=30, help="Show top N files by total query sites")
    parser.add_argument("--by-dir", action="store_true", help="Aggregate and show by directory")
    parser.add_argument("--root", type=str, default=None, help="Root directory (default: task_aversion_app)")
    args = parser.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent.parent
    if not root.is_dir():
        print(f"[FAIL] Root not found: {root}")
        return 1

    # Collect all .py files under root, exclude venv / __pycache__
    py_files: list[Path] = []
    for p in root.rglob("*.py"):
        parts = p.parts
        if "venv" in parts or "__pycache__" in parts or ".venv" in parts:
            continue
        py_files.append(p)

    # Per-file totals (sum of all pattern counts as "query sites")
    file_counts: list[tuple[Path, dict[str, int], int]] = []
    dir_totals: dict[str, int] = defaultdict(int)

    for path in py_files:
        rel = path.relative_to(root)
        counts = count_in_file(path)
        total = sum(counts.values())
        if total > 0:
            file_counts.append((rel, counts, total))
            if args.by_dir:
                dir_name = str(rel.parent) if rel.parent != Path(".") else "."
                dir_totals[dir_name] += total

    # Sort by total descending
    file_counts.sort(key=lambda x: -x[2])

    print("=" * 80)
    print("STATIC QUERY SITE ANALYSIS")
    print("=" * 80)
    print(f"Root: {root}")
    print(f"Files scanned: {len(py_files)}")
    print(f"Files with at least one query site: {len(file_counts)}")
    print()

    if args.by_dir:
        print("--- By directory (total query sites) ---")
        for dir_name in sorted(dir_totals.keys(), key=lambda d: -dir_totals[d]):
            print(f"  {dir_totals[dir_name]:5d}  {dir_name}")
        print()

    print("--- Top files by total query sites ---")
    for rel, counts, total in file_counts[: args.top]:
        parts = str(rel)
        detail = "  ".join(f"{k}:{v}" for k, v in counts.items() if v > 0)
        print(f"  {total:5d}  {parts}")
        if detail:
            print(f"         {detail}")
    print()
    print("Legend: session.query, execute(, text(sql, SELECT (string), PRAGMA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
