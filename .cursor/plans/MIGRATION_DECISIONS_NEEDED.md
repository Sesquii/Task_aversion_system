# Migration Decisions & Ambiguities

## ⚠️ Important Ambiguities to Resolve

### 1. PostgreSQL Migration Timeline

**Current State**: 
- ✅ Migrated to SQLite locally
- ✅ Using `SQLite_migration/` folder with numbered scripts
- ✅ All migrations are SQLite-specific

**Conflicting Plans**:
- `deployment-2d421cbd.plan.md` originally said "Go straight to Postgres (skip CSV→SQLite→Postgres double-hop)"
- But you've already done SQLite migration (which is fine!)

**Decision**: ✅ **Multiple plausible approaches acceptable** - Document different options, decide when closer to VPS deployment.

**Approach Options**:

**Option A: Convert SQLite migrations to PostgreSQL when deploying**
- Keep SQLite for local dev
- When ready for VPS, review all SQLite migrations
- Create PostgreSQL versions of migration scripts
- Run on PostgreSQL during VPS setup
- **Pros**: Familiar SQLite workflow, convert when needed
- **Cons**: Need to convert/verify migrations work on PostgreSQL

**Option B: Start using PostgreSQL locally now**
- Set up PostgreSQL locally
- Convert existing SQLite migrations to PostgreSQL
- Use PostgreSQL for both local and production
- **Pros**: Same database everywhere, catch issues early
- **Cons**: More complex local setup, need PostgreSQL installed

**Option C: Dual migration scripts**
- Write migrations that work for both SQLite and PostgreSQL
- Use conditional SQL based on database type
- **Pros**: One set of migrations for both
- **Cons**: More complex, need to test both paths

**Current Recommendation**: Option A - Keep SQLite for local dev, convert when deploying to VPS. Simplest path forward.

---

### 2. Alembic vs Manual Migrations

**Current**: Manual numbered scripts in `SQLite_migration/` folder

**Plans Mention**: Alembic (SQLAlchemy's official migration tool)

**Decision Needed**:
- [ ] Continue with manual scripts (simpler, more control)?
- [ ] Switch to Alembic (more standard, better for PostgreSQL)?
- [ ] Use Alembic only for PostgreSQL, keep manual for SQLite?

**Recommendation**: Continue manual scripts for SQLite (works well), consider Alembic when moving to PostgreSQL (better tooling for production).

---

### 3. Migration Frequency

**Current**: Run migrations ad-hoc as features are added

**Plans Mention**: "Batch into weekly/biweekly migrations"

**Decision**: ✅ **Minimum one migration per week** - Keep app moving along with regular progress. Can be ad-hoc (as features need it) but ensure at least weekly cadence.

**Implementation**: 
- Track migration frequency
- If no feature needs migration in a week, review if any pending schema improvements can be done
- Maintain momentum while staying flexible

---

### 4. Rollback Strategy

**Current**: Manual rollback (revert database or re-run scripts)

**Plans Mention**: Automated rollback procedures

**Decision Needed**:
- [ ] Is manual rollback sufficient?
- [ ] Need automated rollback for production?
- [ ] How critical is rollback capability?

**Recommendation**: Manual is fine for now. Add automated rollback when deploying to production VPS.

---

## ✅ Decisions Already Made

1. **SQLite First**: ✅ Done - Migrated to SQLite locally
2. **Numbered Scripts**: ✅ Done - Using 001, 002, etc. in `SQLite_migration/` folder
3. **Idempotent Migrations**: ✅ Done - All scripts check if changes exist before applying
4. **Status Checking**: ✅ Done - `check_migration_status.py` utility exists
5. **CSV Fallback**: ✅ Done - Can disable with `DISABLE_CSV_FALLBACK=true`
6. **Manual Migrations**: ✅ Decision - Continue manual approach (less cascading errors, more control)
7. **Migration Frequency**: ✅ Decision - Minimum one migration per week to keep app moving
8. **PostgreSQL Timeline**: ✅ Decision - Multiple approaches acceptable, decide when closer to VPS deployment

---

## 📋 Action Items

1. **Decide on PostgreSQL timeline** - When to convert?
2. **Decide on Alembic** - Use for PostgreSQL or stick with manual?
3. **Document decision** - Update plans with your choices
4. **Create PostgreSQL migration guide** - When ready to convert

---

## 💡 Recommendations Summary

Based on your current approach:

1. **Keep SQLite for local dev** - It's working well
2. **Convert to PostgreSQL when deploying to VPS** - Review all SQLite migrations, create unified PostgreSQL script
3. **Continue manual scripts for now** - Consider Alembic later if needed
4. **Keep ad-hoc migration frequency** - Batch only if you have many small changes
5. **Add automated rollback for production** - Manual is fine for local dev

These recommendations align with your current "SQLite first, PostgreSQL later" approach.

