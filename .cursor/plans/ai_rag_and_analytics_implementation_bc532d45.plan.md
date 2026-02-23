---
name: AI RAG and analytics implementation
overview: "Final implementation plan for local LLM integration, RAG on app data, and analytics improvements: Cloudflare Tunnel for reachability, backend AI plumbing, analytics codebase review, then RAG pipeline and insights. Option 3 (minimal plumbing first) with path to full RAG."
todos: []
isProject: false
---

# AI Recommendations, RAG, and Analytics 

## Decisions Summary

- **Reachability:** **Cloudflare Tunnel** (free, no per-request usage, stable hostnames; failed AI attempts when PC is off do not waste quota). Tailscale as optional privacy alternative; ngrok noted for comparison only.
- **AI strategy:** RAG + rule-based (outliers, notes, emotion–efficiency) for data-driven answers; MCP later if LLM should perform actions.
- **Scope:** Option 3 — minimal AI plumbing first, then cleanup/mobile clarity — with path to full RAG. RAG on app data is in scope; codebase review for analytics performance and feature clarity first.
- **Recommendation metrics:** Audit/fix of `recommendations_by_category` metric direction (high vs low is good) is a **separate task** (other chat).
- **App:** taskaversionsystem.com (VPS). All AI calls go through app backend (no browser → external origin), so no CORS.

---

## Phase 0: Local LLM + Cloudflare Tunnel (your PC)


| Step | Action                                                                                                                                                                                                                                                                                              |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0.1  | Install and run a local LLM on your PC (e.g. **Ollama** on Windows with GPU).                                                                                                                                                                                                                       |
| 0.2  | Expose it over HTTP (Ollama API or thin wrapper) on a local port (e.g. `localhost:11434`).                                                                                                                                                                                                          |
| 0.3  | Install **cloudflared** and create a **named Cloudflare Tunnel** from a subdomain (e.g. `llm.taskaversionsystem.com` or a Cloudflare-provided hostname) to `http://localhost:11434`. Use a Cloudflare account and, if desired, a domain you control (can be taskaversionsystem.com or a free zone). |
| 0.4  | Document the public tunnel URL and how to update the app config if it ever changes.                                                                                                                                                                                                                 |


**Why Cloudflare:** Free; no per-request limits for tunnel traffic; failed requests when PC is off do not burn usage; scales well; more privacy-attuned than ngrok.

---

## Phase 1: Backend AI plumbing (no UI)


| Step | Action                                                                                                                                                                                                                                                               |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1.1  | Add config: `AI_ENDPOINT_URL` (Cloudflare Tunnel URL to your PC), optional `AI_API_KEY` for cloud fallback, and a simple “use local vs cloud” behavior.                                                                                                              |
| 1.2  | Add a single backend route (e.g. `POST /api/ai/chat` or `/api/ai/complete`) that: accepts prompt + optional context; calls `AI_ENDPOINT_URL` when set (local) or cloud when key is set; returns model response; handles timeouts and “AI unavailable” (e.g. PC off). |
| 1.3  | Ensure all AI usage goes through this route (browser only talks to the app → no CORS).                                                                                                                                                                               |
| 1.4  | Optional: show a short disclaimer in the app (e.g. “Free AI may be unavailable when the host PC is offline”).                                                                                                                                                        |


**Result:** App can call your local LLM (or cloud) from the VPS; no RAG or new UI yet.

---

## Phase 2: Analytics codebase review (performance + features)


| Step | Action                                                                                                                                     |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| 2.1  | List and prioritize analytics entry points: dashboard metrics, analytics page, composite score, relief summary, correlation analysis, etc. |
| 2.2  | Review each for redundant work, N+1 or heavy queries, missing caching, and formula clarity.                                                |
| 2.3  | Focus on **correlation analysis** and related features: verify logic and efficiency; simplify where useful.                                |
| 2.4  | Apply low-risk optimizations (caching, query consolidation) and document “Phase 2” vs “later” refactors.                                   |


**Result:** Faster analytics and clearer metrics as a base for RAG and insights.

---

## Phase 3: RAG pipeline on app data (data-driven Q&A)


| Step | Action                                                                                                                                                                                                                                                                                                               |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 3.1  | Define RAG data sources (per user, auth-scoped): task instances (ids, names, dates, relief/stress/load, duration); **notes** on instances; emotion and efficiency-related fields.                                                                                                                                    |
| 3.2  | Choose indexing: precomputed chunks (e.g. per instance or per week) and/or embeddings (e.g. notes + short summaries) with a small vector store (e.g. SQLite + sqlite-vec). Add **rule-based outlier detection** (e.g. relief z-score or IQR); store or inject results as structured “outlier events” or text chunks. |
| 3.3  | Build retrieval: given user question + user_id, retrieve relevant chunks and optional rule-based outlier summaries; build a context string for the LLM.                                                                                                                                                              |
| 3.4  | Wire retrieval into the AI route: backend builds context with RAG + rules, sends to local/cloud LLM, returns answer. Test via API or a minimal “ask” box.                                                                                                                                                            |


**Result:** AI answers grounded in task history, notes, and outliers; encourages detailed notes.

---

## Phase 4: RAG for analytics insights (narrative + feature clarity)


| Step | Action                                                                                                                                                               |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 4.1  | Use the same RAG pipeline + rule-based stats to generate short interpretations (e.g. “This week’s relief was high; notable outliers: …”; “Stress and efficiency …”). |
| 4.2  | Surface these where appropriate: e.g. “AI insight” on dashboard or analytics page, or a small “Ask your data” / “Insights” panel.                                    |
| 4.3  | Optionally use RAG (and/or a codebase pass) to label which analytics are “core” vs “experimental” and simplify or hide the rest over time.                           |


**Result:** Analytics feel more insightful and data-driven; RAG helps clarify which features matter.

---

## Phase 5 (optional / later): MCP for actions

- If you want the LLM to **change** data (e.g. create task, log completion): define a small MCP server or tool-API exposed by the app (e.g. `list_my_tasks`, `create_task`, `get_instance`). Have the LLM call these via your backend; keep auth and validation in the app. Can wait until after RAG is useful.

---

## Dependency order

```
Phase 0 (LLM + Cloudflare Tunnel)  →  Phase 1 (backend route + config)
         ↓
Phase 2 (analytics codebase review)  ←  can run in parallel with 0/1
         ↓
Phase 3 (RAG on app data: index, retrieve, rule-based outliers)
         ↓
Phase 4 (RAG for analytics insights)
         ↓
Phase 5 (MCP, optional)
```

---

## RAG vs MCP (reference)

- **RAG:** Retrieve task history, notes, outliers, emotion–efficiency stats; LLM answers from that context. Does not change data. Best for: “mention specific high/low relief instances,” “use notes,” “emotions and efficiency.”
- **MCP:** LLM calls tools (e.g. query PostgreSQL, create task). Use when you want the assistant to **act** on the app. Add after RAG is in place if desired.

---

## Out-of-scope (other task)

- Audit and fix `recommendations_by_category` metric direction (high vs low is good) in `backend/analytics.py` — handled in a separate chat/task.

---

## Key files (reference)

- Config / route: [ task_aversion_app/app.py ] (add `AI_ENDPOINT_URL`, optional `/api/ai/...` route or module).
- Analytics: [ task_aversion_app/backend/analytics.py ] (review in Phase 2; RAG will consume its outputs).
- Recommendations UI: [ task_aversion_app/ui/dashboard.py ] (refresh_recommendations, Smart Recommendations).
- RAG: new backend module(s) for indexing, retrieval, and context building; integrate with Phase 1 AI route in Phase 3.

