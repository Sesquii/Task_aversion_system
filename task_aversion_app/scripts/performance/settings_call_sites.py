#!/usr/bin/env python3
"""
Settings page: backend call sites and query-site estimates.

Targets the Settings page (/settings, ui/settings_page.py) and its main areas:
settings landing, CSV import/export path, score weights, productivity settings,
and cancellation penalties. Scans settings_page.py and the settings subpages
(composite_score_weights_page, productivity_settings_page, cancellation_penalties_page)
for calls to user_state.*, analytics.*, im.*, get_current_user, create_data_zip,
import_from_zip, task_manager.*. Then counts query sites (session.query, .execute)
in those backend methods to clarify DB usage for Settings flows.

Usage:
  cd task_aversion_app
  python scripts/performance/settings_call_sites.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from collections import defaultdict


SETTINGS_UI_FILES = [
    "ui/settings_page.py",
    "ui/composite_score_weights_page.py",
    "ui/productivity_settings_page.py",
    "ui/cancellation_penalties_page.py",
]


def extract_settings_calls(root: Path) -> dict[str, set[str]]:
    """Extract backend method/function names called from Settings UI files."""
    out: dict[str, set[str]] = defaultdict(set)
    prefixes = [
        "user_state.",
        "analytics.",
        "im.",
        "task_manager.",
    ]
    # Standalone callables used by Settings
    standalones = ["get_current_user", "create_data_zip", "import_from_zip"]

    for rel in SETTINGS_UI_FILES:
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for p in prefixes:
            key = p.rstrip(".")
            for m in re.finditer(re.escape(p) + r"(\w+)\s*\(", text):
                out[key].add(m.group(1))
        for name in standalones:
            if re.search(re.escape(name) + r"\s*\(", text):
                out["standalone"].add(name)

    return dict(out)


def count_query_sites_in_function(body: str) -> int:
    """Count session.query( and .execute( in a string (e.g. function body)."""
    return len(re.findall(r"session\.query\s*\(", body)) + len(
        re.findall(r"\.execute\s*\(\s*", body)
    )


def extract_methods_and_query_counts(module_path: Path) -> dict[str, int]:
    """For a backend module, map method_name -> query site count in that method."""
    try:
        text = module_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    method_counts: dict[str, int] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^\s*def\s+(\w+)\s*\(", line)
        if m:
            name = m.group(1)
            indent = len(line) - len(line.lstrip())
            body_lines = [line]
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if next_line.strip() == "":
                    body_lines.append(next_line)
                    j += 1
                    continue
                next_indent = len(next_line) - len(next_line.lstrip())
                if next_line.strip().startswith("def ") and next_indent <= indent:
                    break
                body_lines.append(next_line)
                j += 1
            body = "\n".join(body_lines)
            method_counts[name] = count_query_sites_in_function(body)
            i = j
        else:
            i += 1
    return method_counts


def main() -> int:
    # Script lives in task_aversion_app/scripts/performance/ -> parent.parent = task_aversion_app
    base = Path(__file__).resolve().parent.parent.parent
    if not (base / "ui" / "settings_page.py").is_file():
        print(f"[FAIL] Settings UI not found under {base}")
        return 1

    calls = extract_settings_calls(base)
    if not calls:
        print("[INFO] No Settings backend calls found.")
        return 0

    backend_modules: dict[str, Path] = {
        "user_state": base / "backend" / "user_state.py",
        "analytics": base / "backend" / "analytics.py",
        "im": base / "backend" / "instance_manager.py",
        "task_manager": base / "backend" / "task_manager.py",
        "csv_import": base / "backend" / "csv_import.py",
        "csv_export": base / "backend" / "csv_export.py",
    }
    method_counts: dict[str, dict[str, int]] = {}
    for key, path in backend_modules.items():
        if path.is_file():
            method_counts[key] = extract_methods_and_query_counts(path)
        else:
            method_counts[key] = {}

    print("=" * 72)
    print("SETTINGS PAGE CALL SITES (backend methods + query-site estimate)")
    print("=" * 72)
    print("Targets: Settings page (landing, CSV import, score weights,")
    print("         productivity settings, cancellation penalties).")
    print()
    print("Files scanned: " + ", ".join(SETTINGS_UI_FILES))
    print()

    total_estimate = 0
    hot: list[tuple[str, str, int]] = []

    for prefix in ["user_state", "analytics", "im", "task_manager", "standalone"]:
        method_set = calls.get(prefix, set())
        if not method_set:
            continue
        counts = method_counts.get(prefix, {})
        if prefix == "standalone":
            # Map create_data_zip -> csv_export, import_from_zip -> csv_import
            for name in method_set:
                if name == "create_data_zip":
                    c = method_counts.get("csv_export", {}).get("create_data_zip", 0)
                elif name == "import_from_zip":
                    c = method_counts.get("csv_import", {}).get("import_from_zip", 0)
                else:
                    c = 0
                if c > 0:
                    hot.append((prefix, name, c))
                    total_estimate += c
                print(f"  {name}()  (query sites: {c})")
            continue
        print(f"--- {prefix} ---")
        for method in sorted(method_set):
            c = counts.get(method, 0)
            if c > 0:
                hot.append((prefix, method, c))
                total_estimate += c
            print(f"  {method}()  (query sites in method: {c})")
        print()

    print("--- Hot path (Settings-related methods with at least 1 query site) ---")
    hot.sort(key=lambda x: -x[2])
    for prefix, method, c in hot[:30]:
        print(f"  {c:3d}  {prefix}.{method}()")
    print()
    print("[INFO] user_state is CSV-backed (no SQL); CSV import/export and analytics")
    print("       drive DB usage on Settings flows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
