# Contributing to Multi-Agent Startup Idea Validator

Thank you for your interest in contributing to the Multi-Agent Startup Idea Validator! We welcome contributions to help improve agent workflows, evidence attribution verification, scoring accuracy, frontend visualization, and test coverage.

---

## 📜 Core Design Principles

Before contributing, please review our core architectural rules:

1. **The system must not flatter the founder**: Every claim requires a source, date, and confidence level. Critic agents can only lower confidence ratings, never raise them.
2. **Deterministic Scoring**: The scoring algorithm (`backend/app/scoring/`) contains **no LLM calls** and must remain strictly mathematical and deterministic.
3. **Verified Attribution**: URLs must come from search grounding metadata (`grounding_metadata`), not model-hallucinated text.
4. **Search → Extract Separation**: Research branches maintain a two-node split (Search node with tools + Extract node with Pydantic output schemas) to control Gemini API search costs and avoid context leakage.

---

## 🛠️ Development Setup

### Backend Setup (Python 3.11 + FastAPI)

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   uv venv --python 3.11
   # On Windows:
   .venv\Scripts\activate
   # On Linux/macOS:
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   uv pip install -r requirements.txt
   ```
4. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Fill in your `GEMINI_API_KEY`, `DATABASE_URL` (Supabase port 6543 pooler), and `DATABASE_DIRECT_URL` (Supabase port 5432 direct).

5. Apply database migrations:
   ```bash
   alembic revision --autogenerate -m "description"
   alembic upgrade head
   ```

6. Run the API dev server:
   ```bash
   uvicorn app.main:app --reload
   ```

### Frontend Setup (Next.js 16 + TypeScript + Tailwind)

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the Next.js development server:
   ```bash
   npm run dev
   ```
   Open `http://localhost:3000` in your browser. Visit `http://localhost:3000/preview` for fixture-driven UI design previews.

---

## 🧪 Testing Guidelines

We enforce rigorous unit and regression testing. All backend tests run offline without network requests or API keys.

Run the test suite:
```bash
cd backend
python -m pytest tests/ -q
```

### Key Test Invariants:
- **`test_adjustments_only_ever_lower_a_rating`**: Verifies that evidence processing and critic overrides never increase scores.
- **`test_weak_idea_lands_in_the_bottom_band`**: Ensures weak/unsubstantiated ideas do not receive high scores.

When introducing changes to scoring, workflows, or grounding, add tests covering edge cases and verify that all 74+ tests pass.

---

## 📋 Pull Request Process

1. **Fork & Branch**: Create a feature branch off `main` (e.g., `feature/custom-agent-node` or `fix/grounding-parser`).
2. **Code Style**: Follow PEP 8 for Python and standard TypeScript formatting guidelines.
3. **Run Tests**: Ensure `pytest` passes cleanly.
4. **Documentation**: Update `README.md` or internal docstrings if changing signatures, API schemas, or environment variables.
5. **Submit PR**: Open a pull request with a clear description of the problem solved and verification steps.

---

## 💬 Questions & Feedback

If you encounter a bug or have a feature suggestion, please open an Issue on GitHub with relevant logs and reproduction steps.
