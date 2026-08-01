# Multi-Agent Startup Idea Validator

> **An evidence-backed startup validation engine powered by Google ADK 2.0 & Gemini 3.**  
> Six specialized agents research, challenge, and score startup ideas on a scale of 0–100 — without flattery.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
  - [Agent Graph Workflow](#agent-graph-workflow)
  - [Search → Extract Node Separation](#search--extract-node-separation)
  - [Verified Source Attribution](#attribution-is-verified-not-trusted)
  - [Deterministic Scoring Engine](#scoring-is-deterministic)
  - [Cost & Rate Control](#cost-control)
- [Setup & Quick Start](#setup)
  - [Backend Setup](#backend)
  - [Frontend Setup](#frontend)
- [Frontend Architecture & Design Tokens](#frontend-architecture)
  - [Component Map](#component-map)
  - [Design Tokens & Accessibility](#design-tokens)
  - [Chart Visualization Rules](#chart-decisions)
- [Testing & Validation](#tests)
- [Status & Roadmap](#status)
- [Governance](#governance)

---

## Overview

Six specialized agents research and challenge a startup idea, then return an evidence-backed opportunity report and a score out of 100.

> [!IMPORTANT]
> **Core Design Principle**: The system **must not flatter the founder**.
> - Every claim carries a source, a date, and a confidence level.
> - Every metric declares whether it was *sourced*, *calculated*, or *assumed*.
> - The critic agent can **only lower confidence**, never raise it.
> - The final score is computed by Python from structured agent output — **never by an LLM**.

---

## Key Features

- 🧠 **Google ADK 2.0 Execution Graph**: Parallel research execution for Market, Competitor, and Persona analysis with a barrier join.
- 🔍 **Strict Attribution Verification**: Compares cited URLs against `grounding_metadata`. Fabricated URLs are un-sourced and capped at 30% confidence.
- 📐 **Deterministic Scoring Engine**: Pure Python rating calculation enforcing decay by age, evidence ceilings (anecdotes capped at 0.35), source freshness scaling, and diminishing returns.
- ⚡ **Real-Time SSE Streaming**: Async FastAPI pipeline pushing live run steps, agent outputs, and progress logs directly to Next.js.
- 🎨 **Accessible & Responsive Design System**: Dark/light theme support, contrast-validated categorical palettes, and an isolated fixture preview route (`/preview`).

---

## Tech Stack

| Component | Choice | Details |
|---|---|---|
| **Agent Framework** | Google ADK 2.0 (`google-adk` 2.6.1) | Workflow graph runtime |
| **Models** | Gemini 3 Series | Tiered by cost (`flash-lite`, `flash`, `3.6-flash`) |
| **Backend API** | FastAPI + Pydantic | Async REST + Server-Sent Events (SSE) |
| **Database** | Supabase Postgres | SQLAlchemy async + Alembic migrations |
| **Worker Engine** | Asyncio Worker | Postgres-backed run queue |
| **Frontend** | Next.js 16 + TypeScript + Tailwind | App Router with interactive Recharts visualization |

---

## Architecture

### Agent Graph Workflow

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

### Search → Extract Node Separation

Each research branch is **two nodes**, not one:

1. **Search node** — has the `google_search` tool, no output schema. Produces prose plus grounding metadata.
2. **Extract node** — has a strict Pydantic output schema, no tools, runs on the cheapest model (`flash-lite`).

This keeps structuring work on the lite tier, avoids depending on ADK's version-dependent `output_schema`-with-tools behaviour, and creates the seam where attribution is verified.

### Attribution is Verified, Not Trusted

URLs a model *writes* can be invented. URLs in `grounding_metadata` are what the search tool actually retrieved. Only the latter are accepted: any claim citing an unretrieved URL is stripped of its source, downgraded from `fact` to `estimate`, capped at 30% confidence, and reported to the UI. See [`app/llm/grounding.py`](file:///d:/founder%20ai/backend/app/llm/grounding.py) and [`app/worker/execute.py`](file:///d:/founder%20ai/backend/app/worker/execute.py).

### Scoring is Deterministic

[`app/scoring/`](file:///d:/founder%20ai/backend/app/scoring/) contains no LLM call and never should. Agents propose a 0–1 rating per category; the scorer decides what the evidence is actually worth:

- Per-claim weight decays with age; undated evidence gets a fixed middling multiplier.
- A category's ceiling is set by its **best** evidence strength — anecdotes cap at 0.35, no evidence at 0.25.
- That ceiling is further scaled by the freshness of the best source, because coverage saturates and would otherwise let a stack of six-year-old reports score like fresh ones.
- Coverage has diminishing returns: ten weak citations never equal one strong study.
- Contradictions and unsound reasoning deduct fixed points.

Every adjustment can only hold a rating **down**. That is enforced by test ([`test_adjustments_only_ever_lower_a_rating`](file:///d:/founder%20ai/backend/tests/test_critic_overrides.py)), not by convention.

### Cost Control

Gemini 3 bills **per search query the model executes**, not per request, and one call can trigger several. [`app/llm/budget.py`](file:///d:/founder%20ai/backend/app/llm/budget.py) enforces hard per-agent and per-run caps by metering `web_search_queries` from grounding metadata.

Models are tiered: `flash-lite` for extraction, `flash` for research, `3.6-flash` for critic and report. ADK's workflow runtime forces `include_contents='none'` on single-turn nodes, so no conversation history leaks between agents — only structured JSON crosses node boundaries.

---

## Setup

### Backend

```bash
cd backend
uv venv --python 3.11
uv pip install -r requirements.txt
cp .env.example .env      # Fill in GEMINI_API_KEY and both Supabase URLs
alembic revision --autogenerate -m "initial"
alembic upgrade head
uvicorn app.main:app --reload
```

> [!NOTE]
> **Supabase Connection Strings — The two ports are not interchangeable:**
> - `DATABASE_URL` → port **6543** (transaction pooler). The app disables asyncpg's statement cache here; without that you get intermittent "prepared statement does not exist" errors once connections are reused.
> - `DATABASE_DIRECT_URL` → port **5432** (direct). Alembic refuses the pooler outright, since DDL through PgBouncer fails confusingly.

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

Visit [`/preview`](http://localhost:3000/preview) for the report rendered against fixture data — it needs no backend, no API key and no completed run, so layout and both colour schemes can be inspected in isolation. It is not linked from the main app navigation.

---

## Frontend Architecture

### Component Map

```
src/
├── app/
│   ├── page.tsx              # Submission form + run history
│   ├── runs/[id]/page.tsx    # Live progress → full report view
│   └── preview/page.tsx      # Fixture-driven design preview
├── hooks/useRunStream.ts     # SSE subscription → derived view state
├── components/
│   ├── ui/                   # Card, Section, Callout, StatTile, BulletList
│   ├── charts/ScenarioChart  # Recharts columns + stat tiles + table view
│   └── report/               # ScorePanel, Evidence, Sections, Report
└── lib/api.ts                # Client + contracts mirroring Pydantic schemas
```

The report renders from the **structured JSON**, not the markdown blob. The markdown exists for download; displaying it would discard every distinction the schema works to preserve — sourced vs assumed, fresh vs dated, fact vs hypothesis.

### Design Tokens

`globals.css` defines surfaces, ink, and two strictly separated palettes. Dark mode is stepped for the dark surface rather than being an inverted flip, and is declared under both `prefers-color-scheme` and `[data-theme]` so a theme toggle wins in either direction.

- **Chart series** use validated categorical slots 1–2 (blue `#2a78d6` / orange `#eb6834`; dark `#3987e5` / `#d95926`). Both modes pass the lightness band, chroma floor, CVD separation (ΔE 24.7 light / 26.8 dark, target ≥ 8), normal-vision floor and 3:1 contrast checks.
- **Score bands** use the reserved status palette and are never a series colour. Two of the four status steps sit below 3:1 on the light surface, so status colour is only ever applied to a *mark* — a glyph, a dot, a tinted chip — while the text beside it stays in primary ink. That is why the hero score number is ink rather than its band colour.

### Chart Decisions

- **Grouped columns, revenue against costs.** The founder's real question is whether it clears its costs and under which assumptions — a magnitude comparison.
- **Break-even customers are stat tiles, not a second axis.** Different unit; a dual axis would invent a relationship the data does not contain.
- Columns capped at 24px with 4px rounded data-ends and a 2px surface gap; solid hairline gridlines; axis ticks snapped to 1/2/2.5/5 × 10ⁿ steps.
- Legend always present (two series), and a **table view** twin means no value is reachable only by hovering.

---

## Tests

```bash
cd backend && python -m pytest tests/ -q     # 74 tests, no network, no API key
```

| Test File | Covers |
|---|---|
| `test_scorer.py` | Staleness, coverage, ceilings, determinism, bounds |
| `test_critic_overrides.py` | The critic can lower a rating and never raise one |
| `test_grounding.py` | Source harvest, search metering, fabricated-URL detection |
| `test_pipeline.py` | Graph shape, fan-in barrier, model tiering, Search→Extract split |
| `test_end_to_end_offline.py` | Attribution → ledger → score → markdown |
| `test_api.py` | Run lifecycle, SSE replay, restart recovery, event bus |

> [!IMPORTANT]
> **The Load-Bearing Test**: `test_weak_idea_lands_in_the_bottom_band`
> A water-reminder app for everyone, free, with maximally enthusiastic agents and nothing but Reddit upvotes as evidence. It **must** land in the 0–39 band. If it ever passes while scoring well, the product is actively misleading founders.

### Discrimination Across Test Scenarios

| Scenario | Score | Band |
|---|---:|---|
| No evidence, agents euphoric | 12.5 | High Risk |
| Only anecdotes (×10) | 19.1 | High Risk |
| A few weak sources | 30.6 | High Risk |
| Strong evidence, 6 years old | 44.4 | Weak |
| Moderate, fresh | 61.6 | Promising |
| Strong + fresh | 85.5 | Strong |

---

## Status & Roadmap

### Working and Verified
- Full HTTP → job runner → ADK graph → Gemini path
- Scorer engine & evidence scaling
- Grounding attribution verification
- SSE progress streaming with replay
- Restart recovery & frontend UI build

### Known Google API Issue
A live smoke test reached the Gemini API and returned `429 RESOURCE_EXHAUSTED` with `quota_limit_value: 0` for `generativelanguage.googleapis.com` in `europe-west1` — indicating billing activation or Gemini 3 model enablement is required on the Google Cloud project. This is a Google-side project setting, not a codebase defect.

### Next Steps
- [ ] Resolve Gemini Cloud quota and run seed ideas end-to-end.
- [ ] Implement per-section rerun support via ADK's `rerun_on_resume`.
- [ ] Integrate `research_cache` using `pgvector` for similarity reuse.
- [ ] Upgrade to Supabase Auth to replace the single dev user model.
- [ ] Auto-generate frontend TypeScript types from FastAPI OpenAPI schemas.

---

## Governance

- 📄 **License**: Distributed under the [MIT License](file:///d:/founder%20ai/LICENSE).
- 🤝 **Contributing**: Read our [Contributing Guidelines](file:///d:/founder%20ai/CONTRIBUTING.md) to get started.
- 📜 **Changelog**: View historical updates in the [Changelog](file:///d:/founder%20ai/CHANGELOG.md).
