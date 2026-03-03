# Timezone integration

The app uses datetimes for due dates, "today", cutoffs (e.g. "last 7 days"), and stored timestamps. This doc describes how timezone is handled and how to adopt it.

**Display fix:** If stored timestamps are in UTC (e.g. you see "2026-02-28 23:23" but it was 5:23 PM your time), use **Settings > Timezone**: choose "Use my device timezone" (auto-detected from your browser) or pick a timezone. The app then uses your per-user timezone for all displayed times. You can also set `TIMEZONE` in `.env` as a fallback when no user preference is set.

## Current state

- **No explicit timezone**: Code uses `datetime.now()` (system local) and in some places `datetime.utcnow()` (UTC). Stored timestamps are strings like `%Y-%m-%d %H:%M` with no timezone.
- **Effect**: "Today" and date ranges follow the server’s (or your machine’s) local time. If the server is in another timezone or you travel, "today" and due-date logic can be wrong.

## Approaches

### 1. Per-user timezone (implemented)

- **Idea**: One configured timezone for the app (e.g. your home timezone). All user-facing "now" and "today" use that zone.
- **Config**: Set `TIMEZONE` in `.env` to an IANA name (e.g. `America/New_York`, `Europe/London`). If unset, behavior stays as today (system local).
- **Implementation**: `backend/app_time.py` provides:
  - `app_time.now()` – current time in app timezone (use instead of `datetime.now()` for due dates, cutoffs, "today").
  - `app_time.today()` – today’s date in app timezone.
  - `app_time.utc_now()` – current UTC (for auth/session expiry or storage if you standardize on UTC).
  - `app_time.format_for_storage(dt)` – format a datetime for DB/CSV.
- **Adoption**: Replace `datetime.now()` / `datetime.utcnow()` in business and UI code with `app_time.now()` or `app_time.utc_now()` as appropriate. Start with: initialize_task (due/today), dashboard (today, cutoffs), instance_manager (created_at/started_at/completed_at), analytics (today, cutoffs), urgency (reference "now").

### 2. Store UTC, display in app timezone

- **Idea**: Store all timestamps in UTC; convert to app timezone only for display and for "today" / cutoff logic.
- **Pros**: Unambiguous; works if you later add per-user timezones or run the app in multiple regions.
- **Cons**: Requires parsing stored strings as UTC and converting when reading; existing data may be naive (interpret as app TZ or document as "legacy local").
- **How**: When writing, use `app_time.utc_now()` and store that (or convert `app_time.now()` to UTC before storing). When reading, parse as UTC then use `.astimezone(app_tz)` for display and date comparisons. `app_time.now()` already uses the configured TIMEZONE for "today" and cutoffs.

## Recommendation

1. Use **Settings > Timezone** and choose "Use my device timezone" (or a fixed zone). Optionally set `TIMEZONE` in `.env` as fallback.
2. Use `app_time.now()` and `app_time.today()` (optionally with `user_id`) for "today" and due-date logic; use `app_time.format_for_display(stored)` for displayed timestamps.
3. Keep using `app_time.utc_now()` for auth/session expiry and for new stored timestamps if you standardize on UTC.

## Files to touch when adopting

- **High impact (today, due, cutoffs)**: `ui/initialize_task.py`, `ui/dashboard.py`, `backend/instance_manager.py`, `backend/urgency.py`, `backend/analytics.py`.
- **Other**: `backend/task_manager.py`, `backend/job_manager.py`, `ui/complete_task.py`, `backend/csv_export.py`, `backend/instrumentation.py`, `backend/profiling.py`, `ui/plotly_data_charts.py`, `ui/task_editing_manager.py`.

Replace `datetime.now()` with `app_time.now()` (and `datetime.utcnow()` with `app_time.utc_now()` where UTC is intended), and use `app_time.today()` where you need "today" as a date.

## Troubleshooting

### VPS shows UTC instead of local time

- **Cause**: When `TIMEZONE` is not set in `.env` and the user has no timezone/detected_tz in preferences, the app falls back to **system local time**. On most Linux VPS hosts the system timezone is UTC, so all times display in UTC.
- **Fix**: Set `TIMEZONE` in `.env` on the VPS to your IANA timezone (e.g. `TIMEZONE=America/New_York`) as fallback. In addition, the app **auto-applies browser timezone by default**: when the client sends a timezone to `/api/detected-timezone` and the user has no timezone set, the server sets the preference to `auto` so the browser’s zone is used. So once the dashboard (or any page that sends detected timezone) loads, times should show in the user’s zone.
- **If still UTC**: Ensure the browser can reach `POST /api/detected-timezone` with credentials (session cookie). If the request returns 401, check session/cookie domain and CORS.
- **Debug**: Open the dashboard (or settings) with `?locale_debug=1` (e.g. `/dashboard?locale_debug=1`). In the browser console you'll see `[locale] detected-timezone <status> <payload> Applied-Defaults: <header>`. Use the Network tab to confirm the POST returns 200 and inspect the response header `X-Applied-Locale-Defaults` when the server applied timezone defaults. If you see 401, the session is not being sent with the request.

### 12-hour vs 24-hour display

- **Current behavior**: The app sends the browser’s `Intl.DateTimeFormat().resolvedOptions().hour12` to `/api/detected-timezone` on dashboard/settings load and stores it per user. `format_for_display()` uses that preference (12-hour: `%I:%M %p`, 24-hour: `%H:%M`).
