<!-- 2d421cbd-d6de-4ffa-95f8-af33a8d6415d 31aec94a-8f74-4a13-baad-358199d61135 -->
# Deployment & Data Plan

**Decisions**

- Database: Go straight to Postgres (skip CSV→SQLite→Postgres double-hop); plan for weekly/biweekly schema migrations.
- Deployment: Systemd + nginx on the Ubuntu 22.04 VPS (simpler now); revisit Docker later if you want image-based releases/rollbacks.
- Domain: Point `TaskAversionSystem.com` A/AAAA to the VPS; Let’s Encrypt via nginx.
- Auth interim: Enforce unique usernames (case-insensitive), with clear UI notice that this is a temporary, no-password system.
- User cap initially: ~20–30 concurrent/light users until load-tested; adjust after a basic load test.

**Steps**

1. Postgres setup: install Postgres, create DB/user, configure env vars/secrets for the app; add simple backup script.
2. App migration off CSV: add DB models/queries for tasks/logs/users, add migration script to import CSV → Postgres, switch code paths to DB; keep CSV backup.
3. Username policy & UI notice: enforce uniqueness, add inline UI notice about temporary auth; reject duplicates with a helpful message.
4. Nginx + TLS: reverse proxy to app, obtain/renew Let’s Encrypt cert for `TaskAversionSystem.com`.
5. Systemd service: unit file to run the app (gunicorn/uvicorn as needed), environment file for secrets, start/enable service.
6. Smoke & load checks: smoke test through domain; run a light load test (e.g., 20→50 virtual users) to size initial max users.
7. Release cadence: tag/releases from main; keep a deploy branch/tag for the VPS; migrations run per release (weekly/biweekly OK).

**Notes**

- Schema changes: batch into weekly/biweekly migrations; keep migration scripts versioned.
- Future Docker path: once stable, add Dockerfile/compose for image-based releases and fast rollbacks.
- Procfile platforms skipped: ephemeral disk/quotas would constrain your CSV/log usage and add cost.

**Simple flow**

```mermaid
flowchart TD
  User --> Nginx
  Nginx --> App[App (systemd service)]
  App --> PG[Postgres]
  App --> Logs[Backups/Logs]
```

### To-dos

- [ ] Set up Postgres DB/user/env vars
- [ ] Migrate CSV data to Postgres and switch reads/writes
- [ ] Enforce unique usernames and add UI notice
- [ ] Configure nginx reverse proxy with TLS
- [ ] Create systemd unit/env files and enable service
- [ ] Smoke test via domain and run light load test
- [ ] Set release/tag process with weekly migrations