#!/usr/bin/env python3
"""
INSERT/UPDATE/DELETE-focused static analysis: transactions and batching on write paths.

Scans app code (backend, ui, app.py; excludes migration dirs) for:
  - session.commit() (transaction boundaries)
  - session.add_all(, bulk_insert_mappings(, executemany( (batched writes)
  - session.add( / session.delete( / .delete() (single-row writes)
  - Loops containing session.add( or session.commit() (potential N-commits)

Produces actionable counts: files with commit-per-write vs batched patterns,
and lists write hotspots that may benefit from batching. Use for per-SQL-type
write-path coverage (INSERT/UPDATE/DELETE).

Usage:
  cd task_aversion_app
  python scripts/performance/write_transactions_and_batching.py [--top N]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path


def analyze_file(path: Path) -> dict[str, int | list[tuple[int, str]]]:
    """
    Return dict: commit_count, add_count, add_all_count, bulk_count, executemany_count,
    delete_count, loop_commit_lines (list of (line_no, snippet)).
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    text = "\n".join(lines)
    counts = {
        "commit_count": len(re.findall(r"session\.commit\s*\(", text)),
        "add_count": len(re.findall(r"session\.add\s*\(", text)),
        "add_all_count": len(re.findall(r"session\.add_all\s*\(", text)),
        "bulk_count": len(re.findall(r"bulk_insert_mappings\s*\(", text)),
        "executemany_count": len(re.findall(r"executemany\s*\(", text)),
        "delete_count": len(re.findall(r"session\.delete\s*\(", text))
        + len(re.findall(r"\)\.delete\s*\(", text)),
    }
    # Heuristic: commit inside a loop (for/while with session.commit in body)
    loop_commit_lines: list[tuple[int, str]] = []
    in_loop = False
    loop_indent = -1
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.match(r"for\s+\w+", stripped) or re.match(r"while\s+", stripped):
            in_loop = True
            loop_indent = len(line) - len(line.lstrip())
        elif in_loop and (len(line) - len(line.lstrip())) <= loop_indent and line.strip():
            in_loop = False
        if in_loop and re.search(r"session\.commit\s*\(", line):
            loop_commit_lines.append((i, line.strip()[:60]))
    counts["loop_commit_lines"] = loop_commit_lines
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write-path transactions and batching (INSERT/UPDATE/DELETE-focused)"
    )
    parser.add_argument("--top", type=int, default=25, help="Show top N files by commit count")
    parser.add_argument(
        "--root",
        type=str,
        default=None,
        help="Root directory (default: task_aversion_app)",
    )
    args = parser.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent.parent
    if not root.is_dir():
        print(f"[FAIL] Root not found: {root}")
        return 1

    include_dirs = ("backend", "ui")
    exclude_dirs = ("venv", ".venv", "__pycache__", "SQLite_migration", "PostgreSQL_migration")

    py_files: list[Path] = []
    for p in root.rglob("*.py"):
        parts = p.parts
        if any(ex in parts for ex in exclude_dirs):
            continue
        rel = p.relative_to(root)
        if str(rel) == "app.py" or any(rel.parts[0] == d for d in include_dirs):
            py_files.append(p)

    file_stats: list[tuple[Path, dict]] = []
    total_commits = 0
    total_batched = 0
    total_single = 0
    loop_commit_files: list[tuple[Path, list[tuple[int, str]]]] = []

    for path in py_files:
        rel = path.relative_to(root)
        data = analyze_file(path)
        if not data:
            continue
        commits = data.get("commit_count", 0)
        add_all = data.get("add_all_count", 0)
        bulk = data.get("bulk_count", 0)
        exec_many = data.get("executemany_count", 0)
        add = data.get("add_count", 0)
        delete = data.get("delete_count", 0)
        if commits > 0 or add_all or bulk or exec_many or add or delete:
            file_stats.append((rel, data))
            total_commits += commits
            total_batched += add_all + bulk + exec_many
            total_single += add + delete
            loop_lines = data.get("loop_commit_lines", [])
            if loop_lines:
                loop_commit_files.append((rel, loop_lines))

    file_stats.sort(key=lambda x: -(x[1].get("commit_count", 0)))

    print("=" * 72)
    print("WRITE-PATH TRANSACTIONS AND BATCHING (INSERT/UPDATE/DELETE-focused)")
    print("=" * 72)
    print(f"Root: {root}")
    print(f"Scoped to: app.py, backend/, ui/ (excludes migrations)")
    print(f"Files scanned: {len(py_files)}")
    print()
    print("--- Actionable totals ---")
    print(f"  session.commit() count:     {total_commits}")
    print(f"  Batched write sites:        {total_batched} (add_all, bulk_insert_mappings, executemany)")
    print(f"  Single-row write sites:    {total_single} (add, delete)")
    if total_commits > 0:
        ratio = total_single / total_commits if total_commits else 0
        print(f"  Writes per commit (approx): {ratio:.1f}")
    print()

    print("--- Top files by session.commit() count ---")
    for rel, data in file_stats[: args.top]:
        c = data.get("commit_count", 0)
        if c == 0:
            continue
        a = data.get("add_count", 0)
        d = data.get("delete_count", 0)
        batch = data.get("add_all_count", 0) + data.get("bulk_count", 0) + data.get("executemany_count", 0)
        parts = [f"commit:{c}", f"add:{a}", f"delete:{d}"]
        if batch:
            parts.append(f"batch:{batch}")
        print(f"  {c:5d}  {rel}")
        print(f"         {'  '.join(parts)}")
    print()

    if loop_commit_files:
        print("--- Commit-inside-loop (potential N-commits / write hotspots) ---")
        for rel, line_list in loop_commit_files[:20]:
            print(f"  {rel}")
            for line_no, snippet in line_list[:5]:
                print(f"    L{line_no}  {snippet}")
        print()

    print("Legend: batched = add_all, bulk_insert_mappings, executemany. Consider batching")
    print("where commit-per-write is high and loops contain commit().")
    return 0


if __name__ == "__main__":
    sys.exit(main())
