# Changelog

All notable changes to the **Multi-Agent Startup Idea Validator** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-01

### Added
- **Multi-Agent Workflow Engine**: Powered by Google ADK 2.0 (`google-adk` 2.6.1) with parallel execution graph (Market, Competitor, and Persona research branches with a barrier join before Financial, Critic, and Reporter nodes).
- **Search → Extract Node Architecture**: Two-node design separating web search tools from Pydantic output schema extraction to optimize Gemini 3 API costs and prevent context leakage.
- **Deterministic Scorer Engine**: Non-LLM mathematical scoring system enforcing evidence decay, source freshness scaling, anecdote capping (max 0.35 ceiling), and strict deduction rules.
- **Grounding & Attribution Verification**: Automatic cross-checking of extracted claims against `grounding_metadata` URLs to strip unverified sources and cap confidence at 30%.
- **FastAPI & Supabase Backend**: Async Postgres storage layer via SQLAlchemy + Alembic, supporting transaction pooling and Server-Sent Events (SSE) for real-time progress streaming.
- **Next.js 16 Frontend**: Full TypeScript client featuring live SSE run subscription, interactive Recharts financial column graphs with stat tiles, theme switching (light/dark accessibility tokens), and fixture preview page (`/preview`).
- **Comprehensive Offline Test Suite**: 74+ pytest unit tests validating scoring bounds, critic overrides, attribution enforcement, pipeline fan-in barriers, and end-to-end markdown generation without requiring external API keys.
- **Project Documentation & Governance**: Added `LICENSE` (MIT), `CONTRIBUTING.md`, and `CHANGELOG.md` files.
