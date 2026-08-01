# Multi-Agent Startup Idea Validator

Six specialized agents research and challenge a startup idea, then return an
evidence-backed opportunity report and a score out of 100.

The design principle throughout: **the system must not flatter the founder.**
Every claim carries a source, a date, and a confidence level. Every number
declares whether it was sourced, calculated, or assumed. The critic can only
lower confidence, never raise it. And the score is computed by Python from
structured agent output — never by an LLM.

## Stack

| Component | Choice |
|---|---|
| Agent framework | Google ADK 2.0 (`google-adk` 2.6.1), Workflow graph runtime |
| Models | Gemini 3 series, tiered by cost |
| Backend | FastAPI + Pydantic |
| Database | Supabase Postgres via SQLAlchemy async + Alembic |
| Jobs | Postgres-backed runs + in-process asyncio worker + SSE |
| Frontend | Next.js 16, TypeScript, Tailwind |

## Architecture

```
                    manager
                       |
        +--------------+--------------+
        |              |              |
   market_search  competitor_search  persona_search     (parallel, max 3)
        |              |              |
   market_extract competitor_extract persona_extract
        |              |              |
        +--------------+--------------+
                       |
                  research_join                          (barrier)
                       |
                   financial -> critic -> reporter
```

### Search → Extract

Each research branch is **two nodes**, not one:

1. **Search node** — has the `google_search` tool, no output schema. Produces
   prose plus grounding metadata.
2. **Extract node** — has a strict Pydantic output schema, no tools, runs on
   the cheapest model.

This keeps structuring work on the lite tier, avoids depending on ADK's
version-dependent `output_schema`-with-tools behaviour, and creates the seam
where attribution is verified.

### Attribution is verified, not trusted

URLs a model *writes* can be invented. URLs in `grounding_metadata` are what
the search tool actually retrieved. Only the latter are accepted: any claim
citing an unretrieved URL is stripped of its source, downgraded from `fact` to
`estimate`, capped at 30% confidence, and reported to the UI. See
`app/llm/grounding.py` and `app/worker/execute.py`.

### Scoring is deterministic

`app/scoring/` contains no LLM call and never should. Agents propose a 0–1
rating per category; the scorer decides what the evidence is actually worth:

- Per-claim weight decays with age; undated evidence gets a fixed middling multiplier.
- A category's ceiling is set by its **best** evidence strength — anecdotes cap at 0.35, no evidence at 0.25.
- That ceiling is further scaled by the freshness of the best source, because coverage saturates and would otherwise let a stack of six-year-old reports score like fresh ones.
- Coverage has diminishing returns: ten weak citations never equal one strong study.
- Contradictions and unsound reasoning deduct fixed points.

Every adjustment can only hold a rating **down**. That is enforced by test
(`test_adjustments_only_ever_lower_a_rating`), not by convention.

### Cost control

Gemini 3 bills **per search query the model executes**, not per request, and
one call can trigger several. `app/llm/budget.py` enforces hard per-agent and
per-run caps by metering `web_search_queries` from grounding metadata.

Models are tiered: `flash-lite` for extraction, `flash` for research,
`3.6-flash` for critic and report. ADK's workflow runtime forces
`include_contents='none'` on single-turn nodes, so no conversation history
leaks between agents — only structured JSON crosses node boundaries.

## Setup

### Backend

```bash
cd backend
uv venv --python 3.11
uv pip install -r requirements.txt
cp .env.example .env      # fill in GEMINI_API_KEY and both Supabase URLs
alembic revision --autogenerate -m "initial"
alembic upgrade head
uvicorn app.main:app --reload
```

**Supabase connection strings — the two ports are not interchangeable:**

- `DATABASE_URL` → port **6543** (transaction pooler). The app disables
  asyncpg's statement cache here; without that you get intermittent
  "prepared statement does not exist" errors once connections are reused.
- `DATABASE_DIRECT_URL` → port **5432** (direct). Alembic refuses the pooler
  outright, since DDL through PgBouncer fails confusingly.

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

## Tests

```bash
cd backend && python -m pytest tests/ -q     # 74 tests, no network, no API key
```

| File | Covers |
|---|---|
| `test_scorer.py` | Staleness, coverage, ceilings, determinism, bounds |
| `test_critic_overrides.py` | The critic can lower a rating and never raise one |
| `test_grounding.py` | Source harvest, search metering, fabricated-URL detection |
| `test_pipeline.py` | Graph shape, fan-in barrier, model tiering, Search→Extract split |
| `test_end_to_end_offline.py` | Attribution → ledger → score → markdown |
| `test_api.py` | Run lifecycle, SSE replay, restart recovery, event bus |

**The load-bearing test** is `test_weak_idea_lands_in_the_bottom_band`: a
water-reminder app for everyone, free, with maximally enthusiastic agents and
nothing but Reddit upvotes as evidence. It must land in the 0–39 band. If it
ever passes while scoring well, the product is actively misleading founders.

Current discrimination across scenarios:

| Scenario | Score | Band |
|---|---:|---|
| No evidence, agents euphoric | 12.5 | high risk |
| Only anecdotes (×10) | 19.1 | high risk |
| A few weak sources | 30.6 | high risk |
| Strong evidence, 6 years old | 44.4 | weak |
| Moderate, fresh | 61.6 | promising |
| Strong + fresh | 85.5 | strong |

## Status

Working and verified: the full HTTP → job runner → ADK graph → Gemini path,
the scorer, attribution verification, SSE progress with replay, restart
recovery, and the frontend build.

Not yet exercised: a complete grounded run producing a real report. A live
smoke test reached the Gemini API and returned
`429 RESOURCE_EXHAUSTED` with `quota_limit_value: 0` for
`generativelanguage.googleapis.com` in `europe-west1` — the project has zero
quota for that region, which usually means billing is not active on that
project or the Gemini 3 model is not enabled for it. That is a Google-side
configuration item, not a code defect.

### Next

- Resolve the Gemini quota, then run the three seed ideas end to end.
- Per-section rerun (ADK's `rerun_on_resume` on individual nodes).
- Populate `research_cache` with pgvector similarity reuse.
- Supabase Auth to replace the single dev user.
- Generate frontend types from the FastAPI OpenAPI schema so they cannot drift.
