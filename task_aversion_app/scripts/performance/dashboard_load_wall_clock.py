#!/usr/bin/env python3
"""
Full-page dashboard load: wall-clock time via HTTP GET.

Targets the main dashboard (page /, built by build_dashboard in ui/dashboard.py).
Performs HTTP GET to the app root and measures response time (time to first byte
or full response). Use to measure full-page dashboard load time from the client
perspective. Requires the app to be running; for authenticated dashboard, log in
in a browser first and pass a session cookie, or interpret redirect-to-login
timings as unauthenticated response time.

Usage:
  cd task_aversion_app
  python scripts/performance/dashboard_load_wall_clock.py [--url URL] [--runs N]
"""
from __future__ import annotations

import sys
import time
import urllib.request
from pathlib import Path


def measure_get(url: str, runs: int = 5) -> tuple[list[float], int | None]:
    """
    Perform GET to url runs times; return list of elapsed seconds and status code.
    """
    times_sec: list[float] = []
    status: int | None = None

    for _ in range(runs):
        start = time.perf_counter()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DashboardWallClockScript/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = getattr(resp, "status", None)
                _ = resp.read()
        except urllib.error.HTTPError as e:
            status = e.code
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        elapsed = time.perf_counter() - start
        times_sec.append(elapsed)

    return times_sec, status


def main() -> int:
    base = Path(__file__).resolve().parent.parent.parent
    url = "http://127.0.0.1:8080/"
    runs = 5

    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == "--url" and i + 1 < len(argv):
            url = argv[i + 1].rstrip("/") + "/"
            i += 2
            continue
        if argv[i] == "--runs" and i + 1 < len(argv):
            try:
                runs = max(1, min(50, int(argv[i + 1])))
            except ValueError:
                print("[FAIL] --runs requires an integer")
                return 1
            i += 2
            continue
        i += 1

    print("=" * 80)
    print("DASHBOARD FULL-PAGE LOAD: WALL-CLOCK TIME (page /, build_dashboard)")
    print("=" * 80)
    print(f"URL: {url}")
    print(f"Runs: {runs}")
    print("(Requires app to be running. Authenticated dashboard may redirect to /login.)")
    print()

    times_sec, status = measure_get(url, runs)
    ok = all(t > 0 for t in times_sec)

    if status is not None:
        print(f"HTTP status: {status}")
    if not times_sec:
        print("[FAIL] No timings recorded.")
        return 1

    t_min = min(times_sec)
    t_max = max(times_sec)
    t_mean = sum(times_sec) / len(times_sec)
    t_ms = [t * 1000 for t in times_sec]
    print("--- Response time (wall-clock) ---")
    print(f"  min={t_min*1000:.1f} ms  mean={t_mean*1000:.1f} ms  max={t_max*1000:.1f} ms")
    print()
    print("Per run (ms):")
    for j, ms in enumerate(t_ms, 1):
        print(f"  {j:2d}. {ms:.1f}")
    print()
    print("These timings target full-page dashboard load (GET /).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
