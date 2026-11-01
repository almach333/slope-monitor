# Development log

## 2026-10-27: Session 1: full MVP build

**Built:**
- Dev environment: installed Node.js 24 LTS and Git (winget). Created the Python 3.13 venv.
- Backend (FastAPI): models and the Alembic migration, OAuth2/JWT login, ingest with quality flags, derived values, the alert engine (warning/critical, debounce, escalation, auto-resolve, offline detection), and the nodes/readings/alerts/rules/dashboard/export APIs. Also `create_user.py`, `seed.py`, and a TTN webhook stub.
- Simulator: 6 nodes (stable ×3, creeping N4, low-battery N5, faulty N6), with backfill and live modes.
- Frontend (React + Vite + Tailwind): Login, Dashboard, Devices, Device detail, New device (with rule editor and one-time API key), Results (comparison chart, table, CSV export), Map, Alerts.
- 73 pytest tests, each naming its requirement. Documentation: README, TESTING, TRACEABILITY.

**Decisions** (all in the approved plan and listed in `docs/TRACEABILITY.md`):
- Derived values are computed when read.
- The baseline is set automatically.
- Slope-angle rules use baseline offsets.
- Quality flags are per field.
- A rule has one active alert at a time.
- API keys are hashed with SHA-256.
- There's an audit history of rule changes.

**Problems found and fixed:**
- On Windows, `localhost` waits ~2 s per request (it tries IPv6 first). The simulator and Vite proxy now use `127.0.0.1`. This cut the backfill from 5.5 min to under 1 min.
- The offline checker ran during a backfill and created alerts for data that hadn't been uploaded yet. These premature alerts are now removed when the late data arrives.
- CARTO dark map tiles now require an API key. Switched to OpenStreetMap tiles darkened with CSS.
- `create-vite` failed (its template folder was missing), so the frontend config files were written by hand.

**Open / for the owner to confirm:**
- R8–R10 are still "proposed".
- Definitions of tilt, slope angle and movement (handoff §4). They're easy to change in `derived.py`.
- Manual "resolve" for alerts was not added (alerts resolve automatically). Say if you want it.
- Alerts near a threshold can flap (open/resolve several times) because of sensor noise. Hysteresis (a dead band) would fix this, but it isn't in the handoff spec.
- `pyserial` for the serial bridge isn't installed until approved.
