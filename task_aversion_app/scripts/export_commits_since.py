"""
Export Git commit messages since a given commit or date.

Usage examples (PowerShell):

  # Since a specific commit (range <since_commit>..HEAD)
  python scripts/export_commits_since.py --since 2cc0c97 --output ..\\..\\data\\commits_since_2cc0c97.txt

  # Since a specific date (falls back to --since "YYYY-MM-DD")
  python scripts/export_commits_since.py --since 2026-01-01 --output ..\\..\\data\\commits_since_2026-01-01.txt
"""
from __future__ import annotations

import argparse
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def run_git_command(cmd: List[str], cwd: Path) -> Tuple[bool, str, str]:
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return result.returncode == 0, result.stdout, result.stderr
    except FileNotFoundError as e:
        return False, "", f"Git not found: {e}"
    except Exception as e:
        return False, "", f"Unexpected error: {e}"


def parse_commits(raw: str) -> List[Dict[str, str]]:
    commits: List[Dict[str, str]] = []
    lines = [ln for ln in raw.split("\n") if ln.strip()]
    for line in lines:
        parts = line.split("|", maxsplit=4)
        if len(parts) < 4:
            continue
        commit_hash = parts[0].strip()
        date_str = parts[1].strip()
        author = parts[2].strip()
        subject = parts[3].strip() if len(parts) > 3 else ""
        body = parts[4].strip() if len(parts) > 4 else ""
        commits.append(
            {
                "hash": commit_hash,
                "date": date_str,
                "author": author,
                "subject": subject,
                "message_body": body,
            }
        )
    return commits


def export_commits_since(repo_path: Path, since: str) -> List[Dict[str, str]]:
    """
    Try range syntax first: <since>..HEAD. If it fails, fall back to --since=<since> (date/time).
    """
    base_format = ["--format=%H|%ai|%an|%s|%b", "--reverse"]

    # Attempt using commit range
    ok, out, err = run_git_command(["git", "log", f"{since}..HEAD", *base_format], repo_path)
    if ok and (out or "").strip():
        return parse_commits(out)

    # Fall back to date-based since
    ok2, out2, err2 = run_git_command(["git", "log", f"--since={since}", *base_format], repo_path)
    if ok2 and (out2 or "").strip():
        return parse_commits(out2)

    # If both failed, raise a descriptive error
    if not ok and not ok2:
        raise RuntimeError(
            f"Failed to retrieve commits using range and date modes.\n"
            f"Range stderr: {err}\nDate stderr: {err2}"
        )
    # If commands succeeded but returned no output
    return []


def write_report(commits: List[Dict[str, str]], repo_path: Path, since: str, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append("GIT COMMITS SINCE")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Repository: {repo_path}")
    lines.append(f"Since: {since}")
    lines.append("")
    lines.append(f"Total Commits: {len(commits)}")
    lines.append("")

    for idx, c in enumerate(commits, 1):
        lines.append(f"Commit #{idx}: {c['hash'][:8]}")
        lines.append(f"Date: {c['date']}")
        lines.append(f"Author: {c['author']}")
        full_message = c["subject"]
        if c.get("message_body"):
            # Combine subject and body to form the full commit message
            full_message = f"{c['subject']}\n{c['message_body']}".strip()
        lines.append("Message:")
        for msg_line in full_message.split("\n"):
            lines.append(f"  {msg_line}")
        lines.append("")

    output_file.write_text("\n".join(lines), encoding="utf-8")


def default_output_path(repo_path: Path, since: str) -> Path:
    safe_since = since.replace(":", "-").replace("/", "-").replace("\\", "-").replace(" ", "_")
    return repo_path / "data" / f"commits_since_{safe_since}.txt"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export git commit messages since a ref or date")
    parser.add_argument("--repo", type=str, help="Path to git repository (default: current directory)")
    parser.add_argument("--since", type=str, required=True, help="Commit hash or date (e.g., 2cc0c97 or 2026-01-01)")
    parser.add_argument("--output", type=str, help="Output file path (default: data/commits_since_<since>.txt)")
    args = parser.parse_args()

    repo = Path(args.repo).resolve() if args.repo else Path(os.getcwd()).resolve()
    if not is_git_repo(repo):
        print(f"[ERROR] Not a git repository: {repo}")
        return 1

    try:
        commits = export_commits_since(repo, args.since)
    except RuntimeError as e:
        print(f"[ERROR] Failed to export commits: {e}")
        return 1

    output_path = Path(args.output).resolve() if args.output else default_output_path(repo, args.since)
    write_report(commits, repo, args.since, output_path)

    print(f"[SUCCESS] Exported {len(commits)} commits to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

