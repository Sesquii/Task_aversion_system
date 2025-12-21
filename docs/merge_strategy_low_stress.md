# Low-Stress Merge Strategy: When and How to Merge Branches

## Quick Answer: Merge Frequency

**Merge `dev` (migration) INTO `main` every 2-3 days** or after completing a logical unit of migration work (whichever comes first).

**Never merge `main` INTO `dev`** - always work forward from main to dev.

---

## The Golden Rule: Merge Direction

```
main (stable)
  ↓
dev (migration)  ← Always merge dev INTO main, never reverse
```

**Key principle:** Migration branch (`dev`) always starts from the latest `main`. You never merge `main` back into `dev` to "catch up". This prevents conflicts.

---

## Merge Frequency Strategy

### Option 1: Time-Based (Simplest)

**Merge every 2-3 days** if you've made progress on migration, even if it's not complete.

**Benefits:**
- Prevents branches from diverging too much
- Smaller merges = fewer conflicts
- Easier to review what changed
- Less cognitive load

**When to merge:**
- ✅ Every 2-3 days of active migration work
- ✅ After completing a logical chunk (e.g., "database models done")
- ✅ Before starting a big feature on main

**When NOT to merge:**
- ❌ Migration is broken/incomplete
- ❌ You're in the middle of debugging
- ❌ Haven't tested the migration work yet

### Option 2: Milestone-Based (More Controlled)

**Merge after completing migration milestones:**

1. Database models created ✅
2. Migration script works ✅
3. TaskManager supports dual backend ✅
4. InstanceManager supports dual backend ✅
5. All managers migrated ✅

Merge after each milestone, even if migration isn't complete.

**Benefits:**
- Clear, logical merge points
- Each merge is a meaningful checkpoint
- Easier to rollback if a milestone breaks something

### Option 3: Hybrid (Recommended)

**Use time-based frequency, but sync with milestones:**

- Merge at least every 3 days
- OR when you complete a milestone (whichever comes first)
- Never let branches drift more than 1 week apart

---

## Conflict Prevention Strategy

### 1. Keep Migration Changes Isolated

**Best practice:** Create new files for database code, modify existing files minimally.

**Example:**
```python
# ✅ Good: New file for database logic
backend/database.py          # NEW - database models
backend/migrate_data.py      # NEW - migration script
backend/task_manager.py      # Modified - adds dual backend support

# ❌ Avoid: Simultaneously refactoring and migrating same file
backend/task_manager.py      # Don't refactor AND migrate at same time
```

**Strategy:**
- Migration work: Add database support to managers
- Feature work: Keep on main, avoid refactoring managers during migration
- After migration merged: Then refactor/improve on main

### 2. Work on Different Files When Possible

**During migration phase:**
- `dev` branch: Focus on `backend/` files (database models, managers)
- `main` branch: Focus on `ui/` files (UI improvements, analytics)

**If you need to modify same file:**
- Complete migration work first, merge it
- Then work on features (they'll have migration code in place)

### 3. Use Feature Flags (Advanced)

Merge migration code early but keep it disabled:

```python
# In task_manager.py (merged to main early)
use_database = os.getenv('DATABASE_URL') is not None

if use_database:
    # Database code (present but disabled)
else:
    # CSV code (still active)
```

This way:
- Migration code is merged (reduces future conflicts)
- Database backend disabled by default (reduces risk)
- Features can be added without touching database code
- Enable database when ready

---

## Practical Merge Workflow

### Step-by-Step: Safe Merge Process

```bash
# 1. Make sure main is up to date
git checkout main
git pull origin main  # If you have remote

# 2. Commit any work-in-progress on dev
git checkout dev
git add .
git commit -m "WIP: Add database models"  # Or complete feature name

# 3. Merge dev into main
git checkout main
git merge dev

# 4. If conflicts occur (see conflict resolution below)
# 5. Test the merged result
python task_aversion_app/app.py

# 6. If everything works, commit merge
git commit  # Complete the merge if conflicts were resolved

# 7. Push if using remote (optional)
git push origin main

# 8. Continue work on dev
git checkout dev
# Continue migration work...
```

### What If There Are Conflicts?

**Don't panic!** Conflicts are normal and fixable.

**Step 1: See what conflicted**
```bash
git status  # Shows conflicted files
```

**Step 2: Open conflicted files**
Look for markers like:
```
<<<<<<< HEAD (main)
# Code from main branch
=======
# Code from dev branch
>>>>>>> dev
```

**Step 3: Keep both changes**
Usually you want:
- Keep migration code (database support)
- Keep feature code (UI improvements)
- Merge them together

**Step 4: Resolve and test**
```bash
# Edit files to resolve conflicts
# Remove the <<<<<< markers and combine code appropriately

# Mark conflicts as resolved
git add <conflicted-file>

# Complete the merge
git commit
```

**Step 5: Test thoroughly**
```bash
python task_aversion_app/app.py  # Make sure it works!
```

---

## Recommended Schedule

### Weekly Rhythm (Low Stress)

**Monday-Wednesday:**
- Work on migration on `dev` branch
- Commit progress daily

**Wednesday Evening:**
- Merge `dev` into `main`
- Test merged version
- Resolve any conflicts

**Thursday-Friday:**
- Continue migration on `dev`
- Work on features on `main` (if desired)

**Friday Evening:**
- Merge `dev` into `main` again
- Test everything works

**Weekend:**
- Use stable `main` branch for daily use
- Pause migration or continue on `dev`

**Benefits:**
- Predictable merge schedule
- Branches never drift more than 3-4 days
- Conflicts are small and manageable
- Weekend is stable for daily use

### Daily Rhythm (If Active Migration)

**Every Evening:**
- Commit migration work on `dev`
- Merge into `main` if made significant progress
- Test merged version
- Next day: Continue on `dev` from fresh `main`

**Benefits:**
- Minimal divergence between branches
- Conflicts are rare (branches stay in sync)
- More frequent but smaller merges

---

## Conflict Frequency Expectation

### Realistic Expectations

**If you follow these strategies:**
- **Merging every 2-3 days:** 0-1 conflicts per merge (usually 0)
- **Merging every week:** 1-3 conflicts per merge
- **Merging every 2 weeks:** 3-5 conflicts per merge (more complex)

**Most conflicts happen when:**
- Both branches modify the same function
- Both branches add imports to the same file
- Both branches modify the same class definition

**Rare conflicts when:**
- Migration touches `backend/` files
- Features touch `ui/` files
- Different parts of same file modified

---

## Emergency: Too Many Conflicts?

If you find yourself with many conflicts (>5 files):

### Option 1: Abort and Merge More Frequently

```bash
git merge --abort  # Cancel the merge
git checkout dev
# Work on dev, merge more frequently going forward
```

### Option 2: Accept Theirs (If Migration Takes Priority)

```bash
# Keep dev branch changes (migration code)
git checkout --theirs <file>
git add <file>
git commit
```

### Option 3: Accept Ours (If Features Take Priority)

```bash
# Keep main branch changes (feature code)
git checkout --ours <file>
git add <file>
# Manually add migration code back
git commit
```

### Option 4: Use Merge Tool

```bash
git mergetool  # Opens visual merge tool (if configured)
```

---

## Reducing Cognitive Load: Simple Rules

### Rule 1: Merge Direction
**Always merge `dev` INTO `main`** - never reverse.

### Rule 2: Merge Frequency
**Every 2-3 days or after milestones** - whichever comes first.

### Rule 3: File Strategy
**Migration = backend files, Features = UI files** (when possible).

### Rule 4: Test After Merge
**Always test after merging** - catch issues early.

### Rule 5: Small Merges
**Small, frequent merges > Large, infrequent merges.**

---

## Your Specific Situation: Recommended Approach

Given your 30% higher cognitive stress:

### **Minimal Stress Strategy:**

1. **Merge every 3 days** (set a calendar reminder)
2. **Merge direction:** Always `dev` → `main` (never reverse)
3. **File isolation:** 
   - Migration: Focus on `backend/` files
   - Features: Focus on `ui/` files (if working on features)
4. **Merge checklist:**
   - ✅ Migration work committed on dev
   - ✅ Test migration locally on dev
   - ✅ Merge dev into main
   - ✅ Test merged version
   - ✅ If conflicts: resolve, test, commit
   - ✅ Continue on dev

### Weekly Schedule Example:

```
Monday:    Work on migration (dev)
Tuesday:   Work on migration (dev)
Wednesday: Merge dev → main, test (evening)
Thursday:  Work on migration (dev)
Friday:    Work on migration (dev) OR features (main)
Saturday:  Use stable main for daily use
Sunday:    Rest or continue migration (dev)
```

### If You Miss a Merge (No Panic)

**Missed 5 days?** Still merge. Conflicts might be slightly more complex, but still manageable.

**Missed 2 weeks?** Still merge. You might have 2-3 conflicts, but you can resolve them.

**The key:** Don't let perfect be the enemy of good. Regular merges are better than perfect timing.

---

## Troubleshooting Common Issues

### Issue: "I forgot to merge for a week"

**Solution:** Merge now. It's fine. Resolve conflicts as they come.

### Issue: "I'm scared of conflicts"

**Solution:** 
- Merge more frequently (every 2 days instead of 3)
- Keep migration and features in different files when possible
- Remember: conflicts are fixable, not catastrophic

### Issue: "Migration is broken, should I merge?"

**Solution:** 
- If migration is broken, don't merge yet
- Fix it on dev first, then merge
- Exception: If you need to test something on main, merge but don't enable database yet (use feature flag)

### Issue: "I want to work on features but migration isn't done"

**Solution:**
- Work on features on main (stable CSV backend)
- Continue migration on dev
- Merge when migration milestone complete
- Features will work with both backends (if migration code is well-designed)

---

## Summary: Your Merge Strategy

**Frequency:** Every 2-3 days (or after milestones)

**Direction:** Always `dev` → `main` (never reverse)

**Expectation:** 0-1 conflicts per merge (usually 0)

**Stress level:** Low - small, frequent merges are easy

**Key rule:** Don't overthink it. Merge regularly, resolve conflicts as they come, test after merging.

---

## Quick Reference Card

```
┌─────────────────────────────────────┐
│  MERGE STRATEGY QUICK REFERENCE     │
├─────────────────────────────────────┤
│                                     │
│  Frequency:  Every 2-3 days        │
│  Direction:  dev → main (always)   │
│  Conflicts:  0-1 per merge (usual) │
│  Test:       Always after merge    │
│                                     │
│  If conflicts:                     │
│  1. See what conflicted            │
│  2. Keep both changes (usually)    │
│  3. Test thoroughly                │
│  4. Commit and continue            │
│                                     │
└─────────────────────────────────────┘
```

**Remember:** The goal is progress, not perfection. Regular merges reduce stress more than avoiding merges does.
