# Slope Monitor

A web dashboard for real-time and historical data from LoRa sensor nodes on an open-pit mine slope (ENGG4601 thesis prototype). The data comes from a **simulator** for now. Real LoRa data will later use the same ingest API.

- **Backend:** Python 3.13, FastAPI, SQLAlchemy, SQLite (`backend/`)
- **Frontend:** React, TypeScript, Vite, Tailwind, TanStack Query, Recharts, Leaflet (`frontend/`)
- **Simulator:** plain Python, no extra installs (`simulator/`)

All commands below are for **Windows PowerShell**, run from the project folder `C:\Thesis Project`.

---

## 1. One-time setup

You need **Python 3.13** (`py -3.13 --version`), the **Node.js LTS** (`node --version`) and, optionally, **Git**.

```powershell
# Backend: virtual environment + libraries
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt

# Backend settings: copy the example, then put a long random SECRET_KEY in it
Copy-Item backend\.env.example backend\.env
py -3.13 -c "import secrets; print(secrets.token_urlsafe(48))"   # paste this as SECRET_KEY

# Create the database and the demo admin account
cd backend
..\.venv\Scripts\alembic upgrade head
..\.venv\Scripts\python -m scripts.seed
cd ..

# Frontend libraries
cd frontend
npm install
cd ..
```

`seed.py` prints the demo login: **admin@example.com / slope-demo-2026**. It's for local use only.

---

## 2. Run it (three terminals)

**Terminal 1: API server** (http://127.0.0.1:8000, interactive docs at http://127.0.0.1:8000/docs)
```powershell
cd backend
..\.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2: web app** (open http://localhost:5173)
```powershell
cd frontend
npm run dev
```

**Terminal 3: simulator.** First generate 7 days of history (about 1 minute), then send live data:
```powershell
cd simulator
py -3.13 simulate.py backfill --days 7 --interval 60
py -3.13 simulate.py live --interval 10
```
The simulator registers the 6 demo nodes automatically on first run and saves their API keys in `simulator\keys.json`. Leave live mode running. If you stop it and start it again later, it fills in the gap first.

---

## 3. Everyday tasks

| Task | Command |
|---|---|
| Start over with fresh demo data | `cd backend` then `..\.venv\Scripts\python -m scripts.seed --reset`, then delete `simulator\keys.json` and run the backfill again |
| Add a real user (asks for a password) | `cd backend` then `..\.venv\Scripts\python -m scripts.create_user --email jane@example.com --name "Jane Smith" --role engineer` |
| Run the backend tests | `cd backend` then `..\.venv\Scripts\python -m pytest -v` |
| Type-check the frontend | `cd frontend` then `npm run typecheck` |
| After changing `models.py` | `cd backend` then `..\.venv\Scripts\alembic revision --autogenerate -m "what changed"` and `..\.venv\Scripts\alembic upgrade head` |

The manual demo walkthrough (for screenshots) is in [docs/TESTING.md](docs/TESTING.md).

---

## 4. Good to know

- **`npm` "is not recognized":** VS Code was open while Node.js was installed. Fully quit VS Code (every window) and reopen it.
- **`npm.ps1 cannot be loaded because running scripts is disabled`:** either run `npm.cmd run dev` instead, or allow local scripts once for your user account with `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`.
- **`[WinError 10013]` when starting the API:** port 8000 is already in use, usually by another copy of the server that's still running. Close the other terminal (or stop that process) and try again.

- **Use `127.0.0.1`, not `localhost`, for the API.** On Windows, `localhost` tries IPv6 first and each request waits about 2 seconds. The simulator and the Vite proxy already use `127.0.0.1`.
- **Login sessions last 60 minutes** by default. For a long demo, set `ACCESS_TOKEN_EXPIRE_MINUTES=480` in `backend\.env` and restart the API.
- **Map tiles need internet.** OpenStreetMap tiles are darkened with CSS. Without internet, the markers still show on a blank background.
- **The site location is a placeholder** (UQ St Lucia), not a real mine. Change `SITE_CENTRE` in `simulator\config.py`.
- **Alert thresholds are placeholders,** not engineering limits. Real values come from the site's geotechnical engineer / TARP.
- **Times are shown in UTC** everywhere.

---

## 5. How it fits together

```
simulator / LoRa bridge ──POST /api/ingest (X-API-Key)──▶ FastAPI ──▶ SQLite
                                                            │
browser (React) ◀──── polls every 5 s (Bearer token) ───────┘
```

| Folder | What's inside |
|---|---|
| `backend/app/derived.py` | Tilt change, slope angle, magnitudes, GPS movement (computed when read, never stored) |
| `backend/app/quality.py` | Range and spike checks. Bad values are flagged, never dropped. |
| `backend/app/alerts.py` | Two-level alert engine with debounce, escalation, auto-resolve and offline detection |
| `backend/app/ingest_service.py` | The one `ingest_reading()` path that every data source uses |
| `backend/app/routers/` | The REST API (see `/docs`) |
| `backend/tests/` | pytest suite. Each test names the requirement (R1–R10) it covers. |
| `frontend/src/pages/` | Login, Dashboard, Devices, Device detail, New device, Results, Map, Alerts |
| `frontend/src/api/` | All data fetching (switching to Server-Sent Events later only touches this folder) |
| `simulator/` | 6 demo nodes: stable ×3, creeping slope (N4), low battery (N5), faulty (N6) |
| `bridge/serial_bridge.py` | Stub for a point-to-point LoRa receiver on a serial port (later) |

The LoRaWAN (The Things Stack) webhook is available at `POST /api/ingest/ttn`. See [docs/TRACEABILITY.md](docs/TRACEABILITY.md) for how each requirement is implemented and tested.
