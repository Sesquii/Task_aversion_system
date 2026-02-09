# Option A: PostgreSQL Locally First (CSV + SQLite as Backup)

Use PostgreSQL on your machine first while keeping CSV and SQLite as backup. No server deployment until you are ready.

## Prerequisites

- **Docker Desktop** installed and **running** (PostgreSQL runs in a container; no need to install Postgres on Windows)
- **Python** and app dependencies already installed

If you see "unable to get image" or "pipe/dockerDesktopLinuxEngine... The system cannot find the file specified", start Docker Desktop and try again.

**"password authentication failed for user task_aversion_user"**  
Another Postgres container or volume may be on port 5432 with different credentials. Fix:

1. From project root: `docker-compose down -v` (stops containers and removes the postgres volume).
2. Run this script again so Postgres starts with the expected user/password (`task_aversion_user` / `testpassword`).

If you need to keep existing data in another container, stop that container so only docker-compose Postgres uses port 5432.

## Quick start

### 1. Start PostgreSQL and run migrations (one-time)

From **project root** (where `docker-compose.yml` is):

```powershell
cd task_aversion_app
.\PostgreSQL_migration\start_local_postgres_and_migrate.ps1
```

Or from **task_aversion_app**:

```powershell
.\PostgreSQL_migration\start_local_postgres_and_migrate.ps1
```

The script will:

- Start the Postgres service with `docker-compose up -d postgres` (data persists in volume `postgres-data`)
- Wait until Postgres is ready
- Run all migrations 001–010
- Print a short status check

### 2. Point the app at PostgreSQL

Create a `.env` file in `task_aversion_app` (copy from below if you don’t have `.env.example`). Add or set:

```
DATABASE_URL=postgresql://task_aversion_user:testpassword@localhost:5432/task_aversion_test
```

Example `.env` (optional variables):

```
# Local PostgreSQL (Option A)
DATABASE_URL=postgresql://task_aversion_user:testpassword@localhost:5432/task_aversion_test

# Optional
# ENVIRONMENT=development
```

The app loads `.env` via `backend.auth`; when `DATABASE_URL` is set, it uses Postgres. CSV and SQLite are not modified.

### 3. Run the app

```powershell
cd task_aversion_app
python app.py
```

The app will use the database given by `DATABASE_URL` (PostgreSQL if you set it as above).

### 4. Roll back to CSV / SQLite

- Remove or comment out `DATABASE_URL` in `.env`, or
- Set `DATABASE_URL=sqlite:///data/task_aversion.db` to use SQLite again.

No need to change code; the app switches backend based on `DATABASE_URL`.

## Data and backups

- **CSV**: Your existing CSV files in `data/` are left as-is. They are not deleted.
- **SQLite**: If you used SQLite before, `data/task_aversion.db` remains. You can point `DATABASE_URL` back to it.
- **PostgreSQL**: Data lives in the Docker volume `postgres-data`. To back up:  
  `docker exec task-aversion-postgres pg_dump -U task_aversion_user task_aversion_test > backup.sql`

## Importing existing data into PostgreSQL

If you have data in CSV or SQLite and want it in Postgres:

1. Set `DATABASE_URL` to the Postgres URL (e.g. in `.env`).
2. Use the app’s CSV import (writes to the current database) or run your existing migration scripts (e.g. `migrate_csv_to_database.py`, `migrate_remaining_csv_to_database.py`) with `DATABASE_URL` set to the Postgres URL.

## Stopping PostgreSQL

From project root:

```powershell
docker-compose stop postgres
```

To start it again later: `docker-compose up -d postgres`. Migrations are only needed once; data persists in the volume.

## Manual steps (without the script)

If you prefer to run steps yourself:

```powershell
# From project root
docker-compose up -d postgres

# Wait until ready, then from task_aversion_app:
$env:DATABASE_URL = "postgresql://task_aversion_user:testpassword@localhost:5432/task_aversion_test"
python PostgreSQL_migration/check_migration_status.py
python PostgreSQL_migration/001_initial_schema.py
# ... 002 through 010 ...
python PostgreSQL_migration/check_migration_status.py
```

See `README.md` in this folder for the full list and order of migrations.
