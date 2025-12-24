---
name: Migration Preparation & Research Plan
overview: ""
todos:
  - id: 824aec1d-facf-478f-b53b-b0e64a065e08
    content: Research AI chatbot costs and integration complexity. Create docs/ai_chatbot_analysis.md with findings and recommendation (defer until core app stable)
    status: pending
---

# Migration Preparation & Research Plan

## Overview

This plan prepares you for migration by answering key questions and building foundational knowledge. Complete this preparation phase before committing to the final deployment plan. This reduces risk and anxiety by ensuring you understand the architecture and can make informed decisions.

**Key Context:**

- Goal: Scale to millions, but priority is increasing productivity hours (currently 1.5hrs/day)
- Friction points: Task aversion (brain says "can't do it"), delusion/grandiosity (dopamine from imagining vs building)
- VPS: Already have SSH access (took 1 hour to set up)
- Updates feel like big transitions when: >10 error repairs, UI breaks, doesn't look right
- Composite score: Your favorite feature, most useful element - need to decide if too nerdy for public

---

## Phase 0: Core Concept Education

### 0.1 Understanding the Database Stack

**Question:** "I don't know what SQLAlchemy is vs PostgreSQL"

**PostgreSQL:**

- **What it is:** A database server (like a file system, but for structured data)
- **Analogy:** Like Excel, but designed for applications to read/write data programmatically
- **Where it runs:** On a server (your VPS or locally on your computer)
- **What it stores:** Tables with rows and columns (similar to CSV, but optimized for queries)
- **How you interact:** SQL queries (SELECT, INSERT, UPDATE, DELETE)

**SQLAlchemy:**

- **What it is:** A Python library that lets you use Python code instead of writing SQL directly
- **Analogy:** Like pandas for databases - you write Python, it translates to SQL
- **Why use it:** 
  - Easier than writing raw SQL
  - Works with multiple databases (PostgreSQL, SQLite, MySQL)
  - Handles connections, transactions, errors automatically
- **Relationship:** SQLAlchemy talks to PostgreSQL (or SQLite for local testing)

**The Stack:**

```
Your Python App (NiceGUI)
    ↓ uses
SQLAlchemy (Python library)
    ↓ translates to
SQL queries
    ↓ executes on
PostgreSQL (database server)
    ↓ stores data in
Database files on disk
```

**Learning Resources:**

- [SQLAlchemy Tutorial](https://docs.sqlalchemy.org/en/20/tutorial/) (official, start with "Working with Data")
- [PostgreSQL vs SQLite](https://www.postgresql.org/about/) (when to use which)
- **Simple analogy:** Think of PostgreSQL as the engine, SQLAlchemy as the steering wheel

---

## Phase 1: Research Tasks (Answer Key Questions)

### 1.1 Mobile vs Desktop Assessment

**Research Question:** Should mobile version come before or after migration?

**Tasks:**

1. **Test current app on mobile browser:**

   - Open app on phone browser (localhost:8080 via network IP or ngrok)
   - Document: What works? What breaks? What's unusable?
   - Take screenshots of key pages

2. **Analyze usage patterns:**

   - When would you use this on mobile? (quick task completion, checking dashboard)
   - When would you use on desktop? (creating tasks, detailed analytics, data entry)
   - Which is primary use case?

3. **NiceGUI mobile support research:**

   - Check NiceGUI documentation for mobile/responsive design
   - Research: Does NiceGUI work well on mobile browsers?
   - What CSS framework does it use? (Tailwind - check mobile responsiveness)

4. **Decision Framework:**

   - **If mobile is critical:** Mobile-first responsive design before migration
   - **If desktop is primary:** Migrate first, add mobile later
   - **If both needed:** Responsive design during migration (adds complexity)

**Output:** Create `docs/mobile_assessment.md` with findings and recommendation

---

### 1.2 VPS Setup Difficulty Assessment

**Research Question:** Is VPS setup harder than local PostgreSQL setup?

**Tasks:**

1. **Local PostgreSQL Setup (Week 1 experiment):**

   - Install PostgreSQL on Windows (or WSL if preferred)
   - Create database and user
   - Test connection from Python
   - Document: Time taken, errors encountered, difficulty level (1-10)
   - **Goal:** Get `backend/database.py` working locally with PostgreSQL

2. **VPS Setup Research:**

   - Research: Ubuntu 22.04 VPS setup guides
   - Document: Steps required (SSH access, package installation, firewall, etc.)
   - Compare complexity to local PostgreSQL setup
   - Identify potential error points

3. **Difficulty Comparison:**

   - **Local PostgreSQL:** ~2-4 hours (installation + connection testing)
   - **VPS Setup:** ~4-8 hours (if first time: SSH, security, nginx, systemd)
   - **VPS is harder because:** Remote access, security concerns, multiple services (nginx, systemd), debugging is harder

4. **Risk Mitigation:**

   - If local PostgreSQL is hard → VPS will be harder
   - If local PostgreSQL is easy → VPS is manageable with good guide
   - **Recommendation:** Master local PostgreSQL first, then VPS feels like "same thing, but remote"

**Output:** Create `docs/setup_difficulty_assessment.md` with comparison and risk assessment

---

### 1.3 Chatbot Feasibility Research

**Research Question:** When is the right time to add chatbot? How easy is it now?

**Tasks:**

1. **Current State of Chatbot Deployment:**

   - Research: How are chatbots being deployed in 2024-2025?
   - GitHub: Search for "chatbot integration" in Python web apps
   - Look for: NiceGUI + chatbot examples, Flask/FastAPI + chatbot patterns
   - Document: Common approaches (API-based vs self-hosted)

2. **Cost Analysis:**

   - **OpenAI API:** Cost per message, monthly estimates for 100/1000/10000 users
   - **Anthropic (Claude):** Pricing comparison
   - **Open Source:** Self-hosted options (Ollama, local LLMs) - setup complexity
   - **Hybrid:** Rule-based + AI fallback

3. **Development Complexity:**

   - **API Integration:** Time to integrate OpenAI/Anthropic API
   - **Self-Hosted:** Time to set up Ollama or similar
   - **Rule-Based:** Time to build rule engine
   - **Custom Training:** Feasibility of training on your app's data

4. **Barrier to Entry Assessment:**

   - **2024:** What was required? (API keys, complex setup)
   - **2025:** What's easier now? (Better libraries, lower costs, simpler APIs)
   - **Trend:** Is it getting easier or harder?

5. **Opportunity Cost Analysis:**

   - **Time to build chatbot:** X hours
   - **Time to improve analytics:** Y hours
   - **Value comparison:** Which drives more productivity for you?
   - **User value:** Which drives more engagement?

6. **Decision Framework:**

   - **If < 1 week to integrate + < $0.10/user/month:** Consider for Phase 2
   - **If > 2 weeks or > $0.50/user/month:** Defer to Phase 3+
   - **If unclear:** Prototype with free tier, measure, decide later

**Output:** Create `docs/chatbot_feasibility_analysis.md` with:

- Current state of chatbot deployment
- Cost breakdown
- Development time estimates
- Recommendation with timeline

---

### 1.4 Iterative Development Workflow Design

**Research Question:** How to enable regular online updates without big migrations?

**Tasks:**

1. **Current Workflow Analysis:**

   - Document: How you currently develop (local changes, test, commit)
   - Identify: Friction points (OneDrive sync, file locking, manual testing)
   - Pain points: What makes updates feel like "big transitions"?

2. **Git Workflow Research:**

   - **Feature branches:** Develop features in isolation
   - **Staging environment:** Test on VPS before production
   - **CI/CD basics:** Automated testing and deployment (optional, advanced)
   - **Hot reloading:** Can NiceGUI auto-reload on code changes? (for development)

3. **Database Migration Strategy:**

   - **Current Approach:** Piece-by-piece migrations in `SQLite_migration/` folder
   - **Numbered Scripts:** Each migration is numbered (001, 002, etc.) and can be run independently
   - **SQLite-First:** All migrations are SQLite-specific for now, will be converted to PostgreSQL later
   - **Idempotent:** All migrations check if changes already exist before applying
   - **Rollback:** Manual rollback by reverting database or re-running migration scripts
   - **Versioning:** Tracked by migration script numbers and `check_migration_status.py`
   - **Future:** Once all SQLite migrations are complete, review and create unified PostgreSQL migration

4. **Deployment Workflow Design:**
   ```
   Local Development (main branch)
       ↓
   Test Locally (PostgreSQL)
       ↓
   Push to dev branch
       ↓
   Deploy to VPS (automated or manual script)
       ↓
   Test on VPS
       ↓
   If issues: Rollback or fix
   ```

5. **Friction Reduction:**

   - **Automated deployment script:** One command to deploy
   - **Database migration script:** One command to update schema
   - **Health checks:** Verify deployment worked
   - **Rollback procedure:** Quick way to revert

**Output:** Create `docs/iterative_workflow.md` with:

- Recommended git workflow
- Deployment process (step-by-step)
- Migration process (how to update database schema)
- Rollback procedures

---

## Phase 2: Architecture Decisions

### 2.1 Feature Set for Online Version

**Based on your input:** Option D (full features) with stripped-down analytics

**Decision Tasks:**

1. **Core Features (Always Online):**

   - ✅ Task creation, initialization, completion, cancellation
   - ✅ Basic dashboard (task list, recommendations)
   - ✅ Settings page

2. **Analytics Features (Stripped Down for Public):**

   - **Current:** Very busy, many metrics, complex visualizations
   - **Public Version:** 
     - Key metrics only (relief score, stress level, completion rate)
     - Simple charts (line graphs, not complex dashboards)
     - Hide advanced metrics (composite score, detailed correlations)
   - **Local Version:** Full analytics for your exploration

3. **Advanced Features (Local Only Initially):**

   - Composite score page (your personal tool)
   - Gap handling (edge case, not needed for public)
   - Data guide (documentation, not critical)
   - Tutorial (nice-to-have, can add later)

4. **Feature Flag System:**

   - Use environment variable: `ENABLE_ADVANCED_ANALYTICS=true/false`
   - Public version: `false` (shows simple analytics)
   - Your local version: `true` (shows everything)
   - Same codebase, different config

**Output:** Create `docs/feature_set_decision.md` with:

- List of features for online vs local
- Feature flag configuration
- UI simplification plan for analytics

---

### 2.2 Database Architecture Design

**Decision Tasks:**

1. **Database Choice:**

   - **Local Development:** SQLite (easier, no server needed)
   - **Production:** PostgreSQL (scales better, more features)
   - **Migration Path:** SQLAlchemy supports both via `DATABASE_URL`

2. **Schema Design:**

   - Map CSV files to database tables:
     - `tasks.csv` → `Task` table
     - `task_instances.csv` → `TaskInstance` table
     - `emotions.csv` → `Emotion` table
     - `user_preferences.csv` → `User` table (for future multi-user)
     - `survey_responses.csv` → `SurveyResponse` table
   - **JSON Columns:** Store `predicted` and `actual` as JSONB (PostgreSQL) or TEXT (SQLite)

3. **Migration Strategy:**

   - **One-time:** CSV → Database migration script
   - **Ongoing:** Use database for all new data
   - **Backup:** Keep CSV export capability for data portability

4. **Connection Management:**

   - **Local:** Direct connection to SQLite file
   - **Production:** Connection pool to PostgreSQL (handles multiple users)

**Output:** Create `docs/database_architecture.md` with:

- Table schemas (SQLAlchemy models)
- Migration plan (CSV → Database)
- Connection configuration
- Backup strategy

---

## Phase 3: Risk Assessment & Mitigation

### 3.1 Migration Risk Analysis

**Identify Risks:**

1. **Data Loss Risk:**

   - **Risk:** Migration script fails, data corrupted
   - **Mitigation:** Backup CSV files, test migration on copy, rollback script

2. **Downtime Risk:**

   - **Risk:** App breaks during migration, users can't access
   - **Mitigation:** Deploy to staging first, test thoroughly, quick rollback

3. **Complexity Risk:**

   - **Risk:** Migration is harder than expected, takes weeks
   - **Mitigation:** Start with local PostgreSQL, validate approach, then VPS

4. **Performance Risk:**

   - **Risk:** Database is slower than CSV (unlikely, but possible)
   - **Mitigation:** Benchmark queries, optimize if needed

5. **Anxiety/Incompetence Risk:**

   - **Risk:** Fear of making mistakes prevents progress
   - **Mitigation:** 
     - Start small (local PostgreSQL only)
     - Test thoroughly at each step
     - Have rollback plan
     - Remember: CSV still works, can always go back

**Output:** Create `docs/risk_assessment.md` with:

- Risk matrix (likelihood vs impact)
- Mitigation strategies for each risk
- Rollback procedures

---

## Phase 4: Week 1 Experiment Plan

### 4.1 Local PostgreSQL Setup (Guaranteed Week 1)

**Goal:** Get PostgreSQL working locally, validate the approach is feasible

**Steps:**

1. **Install PostgreSQL:**

   - Windows: Download from postgresql.org or use WSL
   - Create database: `task_aversion_dev`
   - Create user: `taskuser` with password
   - Test connection: `psql -U taskuser -d task_aversion_dev`

2. **Create Database Models:**

   - Create `backend/database.py` with SQLAlchemy models
   - Start with one table: `Task` (simplest)
   - Define model, test creating table

3. **Test Basic Operations:**

   - Create a task via SQLAlchemy
   - Read tasks from database
   - Update a task
   - Delete a task
   - Compare to CSV operations (should feel similar)

4. **Migration Test:**

   - Write script to migrate `tasks.csv` → `Task` table
   - Verify: Row counts match, sample data correct
   - Test rollback: Export database → CSV, compare

5. **Integration Test:**

   - Modify `TaskManager` to use database (with feature flag)
   - Test: Create task via UI, verify in database
   - Test: Read tasks in UI, verify from database

**Success Criteria:**

- ✅ PostgreSQL installed and running
- ✅ Can create/read/update/delete tasks via SQLAlchemy
- ✅ Migration script works (CSV → Database)
- ✅ UI works with database backend
- ✅ Can switch back to CSV if needed

**Time Estimate:** 8-12 hours (spread over week)

**If This Works:** Proceed to VPS deployment

**If This Fails:** Research more, ask for help, or reconsider approach

**Output:** Create `docs/week1_experiment_results.md` with:

- What worked
- What didn't work
- Time taken
- Difficulty assessment (1-10)
- Decision: Proceed to VPS or need more research?

---

## Phase 5: Decision Points

### 5.1 After Week 1 Experiment

**Decision Tree:**

```
Week 1: Local PostgreSQL Setup
    ↓
    ├─ Success (feels manageable)
    │   ↓
    │   Proceed to VPS deployment (Week 2-3)
    │   ↓
    │   Final Deployment Plan
    │
    └─ Struggling (too complex, errors)
        ↓
        Research more / Get help
        ↓
        Reassess: Wait longer? Different approach?
```

### 5.2 After Research Phase

**Decisions to Make:**

1. **Mobile Priority:**

   - [ ] Mobile-first (redesign UI before migration)
   - [ ] Desktop-first (migrate, add mobile later)
   - [ ] Responsive (both during migration)

2. **Chatbot Timeline:**

   - [ ] Phase 2 (after core migration)
   - [ ] Phase 3 (after analytics migration)
   - [ ] Defer (focus on core features)

3. **Feature Set:**

   - [ ] Minimal (core features only)
   - [ ] Stripped-down analytics (your preference)
   - [ ] Full features (everything online)

4. **Migration Approach:**

   - [ ] Gradual (minimal version first, iterate)
   - [ ] Complete (migrate everything at once)
   - [ ] Wait (continue development, migrate later)

---

## Deliverables

### Documentation Files to Create:

1. **`docs/mobile_assessment.md`**

   - Current mobile usability test results
   - Usage pattern analysis
   - Recommendation: Mobile-first, desktop-first, or responsive

2. **`docs/setup_difficulty_assessment.md`**

   - Local PostgreSQL setup experience
   - VPS setup research
   - Difficulty comparison
   - Risk assessment

3. **`docs/chatbot_feasibility_analysis.md`**

   - Current state of chatbot deployment
   - Cost analysis
   - Development complexity
   - Timeline recommendation

4. **`docs/iterative_workflow.md`**

   - Git workflow design
   - Deployment process
   - Migration process
   - Rollback procedures

5. **`docs/feature_set_decision.md`**

   - Features for online vs local
   - Feature flag configuration
   - Analytics simplification plan

6. **`docs/database_architecture.md`**

   - Table schemas
   - Migration plan
   - Connection configuration

7. **`docs/risk_assessment.md`**

   - Risk matrix
   - Mitigation strategies
   - Rollback procedures

8. **`docs/week1_experiment_results.md`**

   - Experiment outcomes
   - Difficulty assessment
   - Go/no-go decision

### Learning Resources:

- SQLAlchemy tutorial (linked in Phase 0.1)
- PostgreSQL basics
- NiceGUI deployment examples
- Git workflow best practices

---

## Timeline

### Week 1: Core Education + Local Experiment

- **Day 1-2:** Read SQLAlchemy/PostgreSQL basics, understand concepts
- **Day 3-5:** Install local PostgreSQL, create database models, test basic operations
- **Day 6-7:** Write migration script, test with real data, document results

### Week 2: Research Phase

- **Day 1-2:** Mobile assessment (test app on phone, research NiceGUI mobile)
- **Day 3-4:** VPS setup research, compare to local setup
- **Day 5-6:** Chatbot feasibility research
- **Day 7:** Iterative workflow design

### Week 3: Architecture Decisions

- **Day 1-2:** Feature set decisions, create feature flag plan
- **Day 3-4:** Database architecture design
- **Day 5-6:** Risk assessment
- **Day 7:** Review all research, make final decisions

### Week 4: Final Plan Creation

- Create comprehensive deployment plan based on research
- Include all decisions made
- Ready to execute

---

## Success Criteria

**Preparation phase is complete when:**

1. ✅ You understand SQLAlchemy vs PostgreSQL
2. ✅ You've tested local PostgreSQL and it works
3. ✅ You've researched mobile, VPS, chatbot, and workflow
4. ✅ You've made architecture decisions (features, database design)
5. ✅ You've assessed risks and have mitigation plans
6. ✅ You feel confident to proceed (or know what to research more)

**Then:** Create final deployment plan with all decisions baked in.

---

## Next Steps

1. **Start Week 1:** Install PostgreSQL locally, follow experiment plan
2. **Document everything:** Create the docs as you research
3. **Ask questions:** If stuck, pause and research more
4. **After Week 1:** Assess difficulty, decide if ready for VPS
5. **After Research:** Make architecture decisions
6. **Final Step:** Create comprehensive deployment plan

---

## Notes

- **No pressure:** This is preparation, not commitment. You can always wait longer.
- **Start small:** Local PostgreSQL is low-risk. If it's too hard, you know before investing in VPS.
- **Iterative:** Each research task informs the next. Don't need to do everything at once.
- **Learning focus:** The goal is understanding, not speed. Take time to learn properly.
- **Anxiety management:** Small steps reduce anxiety. Week 1 experiment is just local testing, no production risk.