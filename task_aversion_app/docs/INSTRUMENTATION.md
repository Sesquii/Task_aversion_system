# Instrumentation for Debugging

Instrumentation helps isolate three categories of issues:

1. **Refresh/navigation bug** – Save on instance creation refreshes the page instead of navigating to dashboard (VPS only)
2. **Analytics load speed** – Analytics page slow or not loading (especially on VPS)
3. **"Connection lost"** – Brief "Connection lost. Trying to reconnect..." when a page takes 1–2+ seconds to load (VPS; WebSocket timeout)

## Environment Variables

| Variable | Values | Purpose |
|----------|--------|---------|
| `INSTRUMENT_NAVIGATION` | `1`, `true`, `yes` | Log all `ui.navigate.to()`, `ui.navigate.reload()`, and page visits |
| `INSTRUMENT_CACHE` | `1`, `true`, `yes` | Log all cache invalidations (Analytics, TaskManager, InstanceManager, Auth) |
| `INSTRUMENT_ANALYTICS` | `1`, `true`, `yes` | Log analytics page load timing and hot functions |
| `INSTRUMENT_LOG_NAV` | path | Override navigation log file (default: `data/logs/instrumentation_navigation.log`) |
| `INSTRUMENT_LOG_CACHE` | path | Override cache log file (default: `data/logs/instrumentation_cache.log`) |
| `INSTRUMENT_LOG_ANALYTICS` | path | Override analytics log file (default: `data/logs/instrumentation_analytics.log`) |

## Usage Examples

### Combined: All instrumentation (single instance)

```powershell
$env:INSTRUMENT_NAVIGATION="1"
$env:INSTRUMENT_CACHE="1"
$env:INSTRUMENT_ANALYTICS="1"
python app.py
```

Logs go to `data/logs/instrumentation_*.log`. Use when you want full visibility.

### Focused: Refresh/navigation only

```powershell
$env:INSTRUMENT_NAVIGATION="1"
$env:INSTRUMENT_CACHE="1"
$env:INSTRUMENT_LOG_NAV="data/logs/refresh_debug.log"
$env:INSTRUMENT_LOG_CACHE="data/logs/refresh_debug.log"
python app.py
```

Use to reproduce the save-to-refresh bug. Check the log for:
- `navigation` events with `kind: to` and `target: /` (expected after save)
- `page_visit` to `/initialize-task` – repeated visits right after a `to('/')` suggest the navigation was lost
- `cache_invalidation` – verify save-triggered invalidations

### Focused: Analytics speed only

```powershell
$env:INSTRUMENT_ANALYTICS="1"
$env:INSTRUMENT_LOG_ANALYTICS="data/logs/analytics_speed.log"
python app.py
```

Load the analytics page and inspect the log for:
- `analytics_page_load_start`
- `phase_initial_ui_and_warm` – time before `get_analytics_page_data`
- `warm_instances_cache` – duration
- `phase_before_page_data` – UI build before data fetch
- `get_analytics_page_data` – total duration (dashboard_metrics + relief_summary + time_tracking)
- `get_analytics_page_data_breakdown` – `dashboard_metrics_ms`, `relief_summary_ms`, `time_tracking_ms`
- `phase_ui_after_page_data` – heavy UI construction with metrics (often 1–2+ seconds)
- `analytics_page_build_complete` – **total server-side time** for the page
- `load_composite_score_start`, `get_all_scores_for_composite`, `load_composite_score_complete`

## Running on VPS to Catch the Bug

The refresh bug and slow analytics only occur on VPS. To capture them:

### 1. Enable instrumentation in `.env.production`

Add to `task_aversion_app/.env.production`:

```bash
# Instrumentation (remove after debugging)
INSTRUMENT_NAVIGATION=1
INSTRUMENT_CACHE=1
INSTRUMENT_ANALYTICS=1
```

Optional: use a separate log file for easier copying:

```bash
INSTRUMENT_LOG_NAV=/var/log/task-aversion-app/instrumentation_nav.log
INSTRUMENT_LOG_CACHE=/var/log/task-aversion-app/instrumentation_cache.log
INSTRUMENT_LOG_ANALYTICS=/var/log/task-aversion-app/instrumentation_analytics.log
```

### 2. Create log directory (if using custom paths)

```bash
sudo mkdir -p /var/log/task-aversion-app
sudo chown YOUR_USER:YOUR_USER /var/log/task-aversion-app
```

### 3. Restart the app

```bash
sudo systemctl restart task-aversion-app
```

### 4. Reproduce the issue

1. Use the app as usual (e.g. create instances, save, load analytics).
2. When the bug occurs (refresh instead of dashboard, "Connection lost", slow analytics), **stop using the app immediately**.
3. The logs will contain the events up to that moment.

### 5. Copy logs to your machine

**If using default paths** (`data/logs/`):

```bash
# From your local machine (replace VPS_HOST and paths)
scp YOUR_USER@VPS_HOST:/path/to/task_aversion_app/data/logs/instrumentation_*.log ./
```

**If using `/var/log/task-aversion-app/`**:

```bash
scp YOUR_USER@VPS_HOST:/var/log/task-aversion-app/instrumentation_*.log ./
```

### 6. Disable instrumentation after debugging

Remove the instrumentation vars from `.env.production` and restart:

```bash
sudo systemctl restart task-aversion-app
```

## Log Format

Each line is a JSON object. Common fields:

- `ts` – timestamp
- `event` – event type
- `kind` – for navigation: `to`, `reload`, `back`, `forward`
- `target` – for `navigate.to`: destination path
- `from_path` – page where navigation was triggered (when available)
- `stack` – app call stack (file:line), excludes framework code
- `duration_ms` – timing in milliseconds
- `manager`, `method` – for cache invalidation

## Example: Diagnosing the Refresh Bug

1. Enable `INSTRUMENT_NAVIGATION` and `INSTRUMENT_CACHE`.
2. Reproduce: create instance, fill form, click Save.
3. Inspect the log. Expected sequence:
   - `cache_invalidation` (InstanceManager) – from save
   - `navigation` `kind: to` `target: /` – from `do_save` in `initialize_task.py`
   - `page_visit` `/` – dashboard load

If instead you see:
- `navigation` `to` `/` followed by `page_visit` `/initialize-task` with the same `instance_id`  
then the client likely stayed on `/initialize-task` and reconnected, causing a re-render instead of a real navigation. That points to WebSocket or client-side behavior.
