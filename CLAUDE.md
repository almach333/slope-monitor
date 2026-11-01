# Working rules for Claude Code (Slope Monitor)

These rules are distilled from `handoff.md`. Read `handoff.md` before changing anything substantial.

## About the owner
- University engineering thesis (UQ, ENGG4601). The owner is **new to coding**.
- Write clear, commented, conventional code. Prefer simple over clever.
- After each step, explain in plain language what was done and why.

## Rules
- Stack is fixed: FastAPI + Pydantic v2 + SQLAlchemy 2 + SQLite/Alembic (backend), React + TypeScript + Vite + Tailwind + TanStack Query + React Router + Recharts + react-leaflet (frontend). See `handoff.md` section 2.
- **Do not add libraries** beyond those in `handoff.md` / the approved plan without asking the owner.
- Windows dev environment: Python is run as `py -3.13`; a venv lives at `.venv/` in the project root.
- All thesis-relevant logic lives in small, pure, tested modules: `backend/app/derived.py`, `quality.py`, `alerts.py`.
- Every ingest route (simulator, future TTN webhook, future serial bridge) must call the one `ingest_reading()` function in `backend/app/ingest_service.py`.
- Name or docstring each test with the requirement ID it covers (R1–R10) — the owner cites these as thesis evidence.
- Never commit `.env`, `*.db` or `simulator/keys.json`.

## Session log
- At the end of each work session, append an entry to `docs/DEVLOG.md`: date, what was built, decisions made, anything left open.
