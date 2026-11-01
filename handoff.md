# Handoff: Multi-Node Slope Monitoring Dashboard

Read this whole file before writing any code. It describes what to build, the stack to use, the order to build it in, and how each part traces back to the user stories and requirements.

---

## 1. Context

- **Project:** University engineering thesis (UQ, ENGG4601). The goal is a web-based dashboard that shows real-time and historical data from multiple LoRa-connected sensor nodes on an open-pit mine slope.
- **Scope:** the software only. There is no hardware work. For now all data comes from a **simulator** (Section 9). Real LoRa ingestion comes later (Section 12), so the ingestion path must not assume the simulator.
- **The owner is new to coding.** Write clear, commented and conventional code. Prefer simple over clever. Explain what you did after each step (see `CLAUDE.md`).
- **Deadline pressure:** an interim report is due soon and needs screenshots of a working prototype. **Milestone 1 (Section 13) is the priority.** Get it fully working before starting anything else.

---

## 2. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend API | **Python + FastAPI** | The owner knows some Python, so the thesis-relevant logic (ingestion, validation, alert evaluation) stays readable to them. It also generates OpenAPI docs automatically at `/docs`. |
| Data models / validation | **Pydantic v2** (request and response schemas) + **SQLAlchemy 2.x** (ORM) | Standard pairing with FastAPI, with strong validation of incoming sensor payloads. |
| Database | **SQLite** for the prototype, through SQLAlchemy | Zero setup on Windows. Write it so switching to PostgreSQL later is a one-line connection-string change. Use **Alembic** for migrations. |
| Auth | **OAuth 2.0 password flow with bearer tokens**, using FastAPI's built-in `OAuth2PasswordBearer` and `OAuth2PasswordRequestForm` (as in the FastAPI security tutorial). The user submits email and password, the API returns a signed **JWT access token** (`PyJWT`), and the frontend sends it as `Authorization: Bearer <token>`. Passwords hashed with **argon2** (via `pwdlib` or `argon2-cffi`). | Meets "authorised user login" with the simplest standard approach. There is no public sign-up, and only accounts created by an admin can log in. FastAPI's `/docs` page gets a working **Authorize** button for free, which helps testing. It's a first-party app (the backend issues tokens for its own frontend), which is where this flow is acceptable. Don't use it for third-party clients. |
| Frontend | **React + TypeScript + Vite** | Standard single-page app setup, with a fast dev server. |
| Styling | **Tailwind CSS** | Makes the dark, data-dense look in the reference screenshots straightforward. |
| Data fetching | **TanStack Query** | Handles caching, loading and error states, and polling for "real-time". |
| Routing | **React Router** | |
| Charts | **Recharts** | Simple time-series line charts. |
| Map | **Leaflet + react-leaflet** | Free and open. Use OpenStreetMap tiles, or a dark basemap such as CARTO dark. Include the required attribution and check the tile provider's usage terms. |
| Simulator / LoRa bridge | **Python script** posting JSON to the ingest API | The same ingest endpoint later receives real data, from a serial LoRa receiver bridge or a LoRaWAN network-server webhook. |
| Tests | **pytest** (backend). Optionally **Vitest** for frontend logic. | Tests map to requirements, which the thesis needs as evidence. |

**Real-time approach:** the frontend polls every **5 seconds** with TanStack Query `refetchInterval`. LoRa nodes send data minutes or tens of seconds apart, so 5-second polling is effectively real-time and much simpler than WebSockets. Keep the data-access code isolated so it could switch to Server-Sent Events later.

Use current stable versions of everything. Check the official docs before writing setup code. Don't add other libraries without asking the owner first.

**Dev environment:** Windows, **Python 3.13** (run it as `py -3.13`), and the current **Node.js LTS**. Use a virtual environment (`py -3.13 -m venv .venv`).

---

## 3. Repository structure

```
slope-monitor/
├── HANDOFF.md            ← this file
├── CLAUDE.md             ← working rules for Claude Code
├── README.md             ← setup + run instructions (you write this, Windows-first)
├── reference/            ← UI reference screenshots (layout guide only, see Section 8)
├── docs/
│   └── DEVLOG.md         ← log of each work session (see CLAUDE.md)
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app, CORS, router registration
│   │   ├── config.py         # settings from environment variables (.env)
│   │   ├── db.py             # engine/session
│   │   ├── models.py         # SQLAlchemy models
│   │   ├── schemas.py        # Pydantic schemas
│   │   ├── auth.py           # password hashing, JWT create/verify, OAuth2PasswordBearer, current_user dependency
│   │   ├── derived.py        # derived quantities (slope angle, tilt change, movement)
│   │   ├── quality.py        # range checks / data-quality flags
│   │   ├── alerts.py         # alert rule evaluation + alert state changes
│   │   └── routers/          # auth.py, nodes.py, readings.py, alerts.py, ingest.py, dashboard.py
│   ├── alembic/
│   ├── scripts/
│   │   ├── create_user.py    # CLI: create an authorised user
│   │   └── seed.py           # create demo nodes + default alert rules
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/              # typed fetch functions + TanStack Query hooks
│   │   ├── components/       # StatCard, StatusBadge, NodeCard, TimeSeriesChart, Layout, Sidebar...
│   │   ├── pages/            # Login, Dashboard, Devices, DeviceDetail, NewDevice, Results, Map, Alerts
│   │   └── lib/              # formatting, units, constants
│   └── package.json
└── simulator/
    ├── simulate.py           # live mode + backfill mode
    └── scenarios.py          # stable / creeping / failing-battery / noisy / offline node behaviours
```

---

## 4. Sensor parameters (the 9 per-node parameters)

The user stories require these nine parameters per node, plus position and link quality. Store raw sensor values, and compute **derived** values server-side in `derived.py` so the logic lives in one testable place.

| # | Parameter | Stored / derived | Fields | Unit | Notes |
|---|---|---|---|---|---|
| 1 | **Tilt** | Derived | `tilt_change_x`, `tilt_change_y`, `tilt_change_total` | degrees | Change in inclination **since the node's baseline** (set at registration, or the median of the first N readings). This is the main slope-movement indicator. |
| 2 | **Slope angle** | Stored | `angle_x`, `angle_y` (and `angle_z` heading, optional) | degrees | Absolute inclination of the node about each axis, as reported by the IMU. Also derive `slope_angle` = overall inclination from horizontal, computed from the accelerometer gravity vector: `atan2(sqrt(ax²+ay²), az)`. |
| 3 | **Acceleration** | Stored | `acc_x`, `acc_y`, `acc_z` | g | Also derive `acc_magnitude`. At rest it is about 1 g. |
| 4 | **Gyroscope** | Stored | `gyro_x`, `gyro_y`, `gyro_z` | °/s | Rotation rate, near 0 at rest. Also derive `gyro_magnitude`. |
| 5 | **Magnetic field** | Stored | `mag_x`, `mag_y`, `mag_z` | µT | Also derive `mag_magnitude`. |
| 6 | **Temperature** | Stored | `temperature` | °C | |
| 7 | **Humidity** | Stored | `humidity` | %RH | |
| 8 | **Battery** | Stored | `battery_pct` (and `battery_v`, optional) | %, V | |
| 9 | **Movement** | Derived | `displacement_m` | metres | Horizontal distance between the latest GPS position and the node's reference position (haversine). Consumer GPS is only accurate to metres, so label this as coarse. |
| – | Position | Stored | `lat`, `lon` | WGS84 | Used for the map. |
| – | Link quality | Stored | `rssi`, `snr` | dBm, dB | Shown on device detail. Helps tell a radio problem from a slope problem. |

> **Open questions (confirm with the owner and supervisor, but don't block on them):** whether "tilt" and "slope angle" are meant as defined above, and whether "movement" should be GPS displacement (as above) or vibration/seismic activity. Implement the definitions above, and keep them in `derived.py` so they're easy to change.

---

## 5. Data model

- **User:** `id`, `email` (unique), `password_hash`, `name`, `role` (`admin` | `engineer`), `is_active`, `created_at`, `last_login_at`.
- **Node:** `id`, `name`, `dev_eui` (unique hardware ID string), `description`, `ref_lat`, `ref_lon`, `baseline_angle_x`, `baseline_angle_y` (nullable until set), `expected_interval_s` (default 60), `api_key_hash`, `created_at`, `is_active`.
- **Reading:** `id`, `node_id` (FK), `ts` (UTC, when measured), `received_at`, `seq` (optional packet counter), all stored fields from Section 4, and `quality_flags` (JSON list, e.g. `["acc_out_of_range"]`). Unique constraint on (`node_id`, `ts`) to reject duplicates. Index (`node_id`, `ts`).
- **AlertRule:** `id`, `node_id` (FK), `parameter` (enum, Section 7), `comparator` (`gt` | `lt`), `warning_threshold`, `critical_threshold`, `consecutive_readings` (default 3), `justification` (**required** text, e.g. the reason or reference for the value), `enabled`, `updated_by`, `updated_at`.
- **Alert:** `id`, `node_id`, `rule_id` (nullable for system alerts such as offline), `level` (`warning` | `critical`), `parameter`, `value`, `threshold`, `message`, `status` (`open` | `acknowledged` | `resolved`), `opened_at`, `acknowledged_by`, `acknowledged_at`, `resolved_at`.

**Node status** is computed, not stored:
- `offline` if there's no reading for more than 3 × `expected_interval_s`.
- Otherwise `critical`, then `warning`, then `ok`, based on the node's open alerts.

---

## 6. API

All endpoints are under `/api`. All endpoints except `/api/auth/token` and `/api/ingest` require a valid bearer token. A missing or invalid token gets 401 with a `WWW-Authenticate: Bearer` header.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/token` | OAuth 2.0 token endpoint. Form-encoded `username` (the email) and `password`, which is what `OAuth2PasswordRequestForm` expects. Returns `{"access_token": "...", "token_type": "bearer", "expires_in": 3600}`. A wrong email or password returns 401 with the same generic message for both, and an inactive user returns 401. |
| GET | `/api/auth/me` | Returns the current user. |
| GET | `/api/dashboard/summary` | Counts (nodes, online, offline, open alerts by level), plus each node's latest reading and status. |
| GET | `/api/nodes` | List nodes, each with status and latest reading (including derived values). |
| POST | `/api/nodes` | Register a node. Returns a **one-time plaintext API key** for ingestion. Optionally creates initial alert rules. |
| GET | `/api/nodes/{id}` | Node metadata, latest reading and status. |
| PATCH | `/api/nodes/{id}` | Edit name, description, reference position, interval or baseline. |
| POST | `/api/nodes/{id}/baseline` | Set the tilt baseline from the median of the last N valid readings. |
| GET | `/api/nodes/{id}/readings?from=&to=&fields=&max_points=` | Historical readings. Downsample on the server to at most `max_points` (default 500), using a time-bucket average, so charts stay fast. |
| GET | `/api/readings/export?node_ids=&from=&to=` | CSV download. |
| GET / POST / PATCH / DELETE | `/api/nodes/{id}/alert-rules` | Manage a node's alert rules. `justification` is required on create and update. |
| GET | `/api/alerts?status=&node_id=` | Alert list. |
| POST | `/api/alerts/{id}/acknowledge` | Acknowledge an alert. |
| POST | `/api/ingest` | **Device data in.** Header `X-API-Key: <node key>`. Body is one reading, or a list of readings, in the schema below. |

**Ingest payload (JSON):**
```json
{
  "dev_eui": "70b3d57ed0000001",
  "ts": "2026-10-27T08:00:00Z",
  "seq": 1234,
  "lat": -27.4975, "lon": 153.0137,
  "angle_x": 1.92, "angle_y": -0.41, "angle_z": 87.3,
  "acc_x": 0.033, "acc_y": -0.007, "acc_z": 0.999,
  "gyro_x": 0.12, "gyro_y": -0.05, "gyro_z": 0.02,
  "mag_x": 21.4, "mag_y": -4.9, "mag_z": -43.1,
  "temperature": 24.6, "humidity": 58.1,
  "battery_pct": 87.0, "battery_v": 3.92,
  "rssi": -96, "snr": 6.5
}
```

Ingest flow:
1. Authenticate the key against the node.
2. Validate types. Missing optional fields are allowed.
3. Run range checks (Section 10). Out-of-range values are **flagged but still stored**. Never silently drop data.
4. Reject duplicates (same node and timestamp) with a 200 and `duplicate: true`.
5. Compute derived values.
6. Evaluate alert rules (Section 7).
7. Return 201.

---

## 7. Alerts

Parameters a rule can watch: `tilt_change_total`, `slope_angle`, `acc_magnitude`, `battery_pct`, `displacement_m`, `temperature`, `humidity`, `gyro_magnitude`, `mag_magnitude`. The user stories explicitly require **battery, acceleration and slope angle**. Tilt is required by R5.

- **Two levels per rule (R7):**
  - `warning` fires at `warning_threshold`.
  - `critical` fires at `critical_threshold`.
  - A rule is a "stacked" alarm: it moves from warning to critical as the value worsens.
- **Debounce:** a level fires only after `consecutive_readings` valid readings in a row breach it. Readings flagged as bad don't count. This avoids false alarms from single noisy readings.
- **Lifecycle:** one open alert per (rule, level).
  - A breach opens it, and continued breaches keep it open (no duplicates).
  - It resolves automatically after `consecutive_readings` normal readings.
  - Engineers can acknowledge it, which stops it showing as new but keeps it until resolved.
- **Offline alert:** a background check runs every 30 s and opens a `warning` alert of type `offline` when a node passes its offline threshold. It resolves when data resumes. Use FastAPI lifespan with a simple asyncio loop, and add no scheduler library.
- **Default rules,** created by `seed.py` and offered on the New Device page:

| Parameter | Comparator | Warning | Critical |
|---|---|---|---|
| `tilt_change_total` | gt | 1.0° | 2.0° |
| `slope_angle` | gt | node's baseline slope angle + 1.0° | node's baseline slope angle + 2.0° |

The slope-angle thresholds are calculated when the node's baseline is set, then stored as absolute numbers. Until the node has a baseline, the rule is created **disabled**.
| `acc_magnitude` | gt | 1.2 g | 1.5 g |
| `battery_pct` | lt | 20 % | 10 % |

**Defaults are placeholders, not engineering limits.**
- In the UI, the justification field must be filled in.
- Show a visible note: "Threshold values are placeholders for the prototype. Site values come from the site's geotechnical engineer / Trigger Action Response Plan."

---

## 8. Pages and UI

**Visual reference:** `reference/01-login.png` through `05-map.png`.
- Match their **overall layout and feel**: dark theme, left sidebar navigation, large bold page titles with small uppercase "eyebrow" labels, KPI stat cards, bordered panels, monospace numbers, green/amber/red status colours.
- **Do not copy** the name "LoRaTrack", the logo, or the "Made with …" badge.
- Use the app name **"Slope Monitor"**, or ask the owner.
- Use a mine-site context, not a world map.

Global layout:
- A left sidebar with Dashboard, Devices, Results, Map and Alerts.
- The signed-in user and a logout button at the bottom of the sidebar.
- A top bar with a "LIVE" indicator (it pulses when the last poll succeeded) and the current UTC time.

| Route | Page | Contents |
|---|---|---|
| `/login` | **Login** | Split layout as in `01-login.png`: product blurb on the left, sign-in form on the right. Email and password only. On submit, POST to `/api/auth/token`, store the token (Section 11), and redirect to `/`. Show "Incorrect email or password" on 401. **No "Create account" link** (authorised users only), and no demo credentials shown in production mode. |
| `/` | **Dashboard** | 4 stat cards: Nodes, Online, Offline, Active alerts. "Node status" table with name, dev_eui, status badge, tilt change, slope angle, battery, temperature, RSSI and last seen. "Active alerts" panel on the right, newest first, coloured by level. "Live readings" strip: a small multi-node line chart of `tilt_change_total`, last 6 h. Polls every 5 s. |
| `/devices` | **Devices** | Card grid as in `03-devices.png`, one card per node. Header shows status badge, name and dev_eui. Body shows a compact grid of the **9 parameters'** latest values: tilt change, slope angle, acceleration (magnitude), gyro (magnitude), magnetic (magnitude), temperature, humidity, battery and movement. Buttons: **Inspect** (goes to detail) and **+ Add device** (goes to New Device). |
| `/devices/:id` | **Device detail** | As in `04-device-detail.png`. Left column: Metadata (dev_eui, reference position, expected interval, baseline), Latest reading (all fields, with units), and an Uplinks count. Right: a grid of time-series charts, one per parameter group (tilt X/Y/total, slope angle, acceleration X/Y/Z, gyroscope X/Y/Z, magnetic X/Y/Z, temperature, humidity, battery, movement, RSSI/SNR). Time-range selector: 1 h, 6 h, 24 h, 7 days, custom. Warning and critical threshold lines on charts that have rules. Points flagged as bad are hidden by default, with a "show flagged" toggle. Buttons: "Set baseline now" and "Edit alert rules". |
| `/devices/new` | **New device** | Form: name, dev_eui, description, reference lat/lon (click a small map to place), expected interval. Below it, an **Alert conditions** section, pre-filled with the default rules for **battery, acceleration and slope angle** (plus tilt). Each row: enable toggle, warning, critical, consecutive readings, and justification (required). On save, show the one-time API key with a copy button and a warning that it won't be shown again. The same rules editor is reused from Device detail via "Edit alert rules". |
| `/results` | **Results (history)** | Pick one or more nodes, one parameter, and a date range. Shows a comparison line chart (one line per node) and a paginated table of readings below it. **Export CSV** button. |
| `/map` | **Map** | As in `05-map.png`, but fit the bounds to the nodes (site scale, not world). Circle markers coloured by status. Popup shows name, status, tilt change, battery, last seen and a link to the detail page. Optional: a dashed circle at each node's reference position to show movement. |
| `/alerts` | **Alerts** | Tabs for Open, Acknowledged and Resolved. Table with time, node, parameter, level, value, threshold and message. Acknowledge button. |

Every page needs proper **loading, empty and error states**. Format all numbers with units and sensible decimals.

---

## 9. Simulator

`simulator/simulate.py`:
- Registers nodes through the API if they don't exist (or reads keys from a local `simulator/keys.json`).
- Posts readings to `/api/ingest`.

Two modes:
- `py -3.13 simulate.py backfill --days 7 --interval 60` generates history quickly, so the charts have data straight away.
- `py -3.13 simulate.py live --interval 10` sends one reading per node every N seconds, so the dashboard visibly updates.

Default to **6 nodes** with these scenarios (see `scenarios.py`):

| Node | Scenario | Behaviour |
|---|---|---|
| N1, N2, N3 | Stable | Small noise around a fixed tilt. Daily temperature and humidity cycle. Slow battery drain. |
| N4 | **Creeping slope** | Tilt increases slowly, then **accelerates** over the last ~2 days (progressive failure). GPS displacement grows. It must cross warning, then critical. |
| N5 | **Low battery** | Battery drains fast and crosses 20 %, then 10 %. |
| N6 | **Faulty / intermittent** | Occasional spike readings (e.g. ±99) that must be flagged, dropped packets (gaps), and one outage longer than the offline threshold. |

Realism requirements:
- Generate angles first, then derive the accelerometer gravity components from them, so slope angle and acceleration agree.
- At rest the gyroscope is near 0 °/s with noise.
- The magnetic field is roughly constant (Earth's field, about 50 µT total) with noise.
- RSSI is a per-node base (−80 to −110 dBm) with noise. SNR roughly follows RSSI.
- Positions are clustered within ~500 m of a placeholder site centre. Make the site centre configurable, and **label it as a placeholder, not a real mine**.
- Use a fixed random seed option for reproducible tests.

---

## 10. Data quality

Implement in `quality.py`:
- **Range checks** (flag values outside them):
  - angles ±90°
  - acceleration ±16 g
  - gyroscope ±2000 °/s
  - temperature −40 to 85 °C
  - humidity 0–100 %
  - battery 0–100 %
  - latitude and longitude within valid ranges
- **Spike check:** flag a tilt jump of more than 10° from the previous valid reading.
- **Handling:** flagged values are stored, excluded from alert evaluation and derived baselines, and hidden in charts by default.
- **Gaps:** charts show missing data as gaps (don't connect the line across gaps longer than 3 × the interval).
- **Per-node counts:** show the number of flagged readings and missed uplinks on Device detail.

---

## 11. Security basics

- Settings come from `.env` (`SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`, `ACCESS_TOKEN_EXPIRE_MINUTES`, default 60). Commit `.env.example`, never `.env`.
- **Tokens:**
  - JWT signed with HS256 and `SECRET_KEY`, with claims `sub` (user id), `exp` and `iat`.
  - Verify the signature and expiry on every request, and reject inactive users.
  - Never log tokens or put them in URLs.
- **Frontend token handling:**
  - Keep the token in memory (an auth context) and mirror it to `sessionStorage`, so a page refresh keeps you signed in and closing the tab signs you out.
  - Attach it as `Authorization: Bearer` in one shared fetch helper.
  - On any 401, clear it and redirect to `/login`.
  - **Logout** clears the stored token. Tokens are stateless, so there's no server call, and the short expiry limits the risk.
  - Add a comment noting the trade-off: browser-stored tokens can be read by any script injected into the page (XSS), which is acceptable for a prototype with no third-party scripts.
- Passwords hashed with argon2.
- Device API keys are stored **hashed**, and the plaintext is shown once.
- Add basic login rate limiting (an in-memory counter is enough for the prototype).
- CORS is restricted to the frontend's dev origin.
- Users are created only with `backend/scripts/create_user.py --email ... --role ...`, which prompts for the password. The `seed.py` script creates one demo admin, with credentials printed to the console.

---

## 12. Later: real LoRa data (not now, but design for it)

- **LoRaWAN** (e.g. RAK4630 nodes with a gateway and a network server such as The Things Stack): add `/api/ingest/ttn`, which accepts the network server's uplink webhook, decodes the payload, maps it to the ingest schema, and calls the same internal ingest function.
- **Point-to-point LoRa** (e.g. a REYAX RYLR998 receiver on a PC serial port): add `bridge/serial_bridge.py`, which reads lines from the serial port (`pyserial`), parses them, and POSTs them to `/api/ingest`.
- Either way, keep **one internal `ingest_reading()` function** that every route calls.

---

## 13. Milestones (build in this order)

**Milestone 1, interim prototype (priority, needed for screenshots):**
1. Backend skeleton: models, Alembic migration, auth, `create_user.py` and `seed.py`.
2. Ingest endpoint with validation, quality flags and derived values.
3. Simulator backfill and live modes.
4. Frontend: layout and sidebar, Login, Dashboard, Devices, Device detail (charts and time range), Map.
5. Alert engine with default rules, active alerts shown on the Dashboard and Alerts page.
6. The README states the exact Windows commands to install, seed, simulate and run.

**Milestone 1 is done when:** the owner can log in, see 6 nodes updating live, inspect each node's 9 parameters over time, see nodes on a site map, see N4 go warning then critical, see N5 raise a battery alert, and see N6 go offline and show flagged readings.

**Milestone 2:**
- New Device page with the alert rule editor (and justification).
- Results page with comparison and CSV export.
- Alert acknowledge and resolve.
- Baseline setting.

**Milestone 3:**
- Tests completed (Section 15).
- UI polish, plus empty and error states everywhere.
- Real LoRa bridge stub (Section 12).

---

## 14. Traceability

### Requirements → implementation

R1–R7 are the owner's. R8–R10 are **proposed, so confirm with the owner**.

| ID | Requirement | Implemented by |
|---|---|---|
| R1 | Browser accessible, with authorised-user login | Login page, OAuth 2.0 password flow issuing bearer JWTs, argon2 password hashing, no public sign-up, accounts created by admin via `create_user.py` |
| R2 | Multi-node data and status shown simultaneously | Dashboard table and stat cards, Devices grid, Map |
| R3 | Historical and real-time data for each node | 5 s polling on Dashboard and Device detail. Device detail time ranges. Results page. |
| R4 | Node positions on a map | Map page (Leaflet), fitted to site bounds, colour by status |
| R5 | Alert when slope tilt exceeds a safe limit | `tilt_change_total` and `slope_angle` rules, alert engine |
| R6 | Safe limit can be set and changed, with justification | Alert rule editor, required `justification`, audit fields `updated_by` and `updated_at` |
| R7 | Multiple alert levels as a safety measure | Warning and critical levels per rule, debounce, offline alerts |
| R8 *(proposed)* | Detect and flag invalid or missing data | `quality.py`, flagged-point handling, gap display, per-node counts |
| R9 *(proposed)* | Show node health (online/offline, battery, link quality) | Computed status, offline alert, battery rule, RSSI/SNR charts |
| R10 *(proposed)* | Export historical data | CSV export endpoint and Results page button |

### User stories → pages

| User story ("As an engineer I want to…") | Page | Acceptance check |
|---|---|---|
| …log in to access the website | Login | Wrong password shows an error. Protected routes redirect to `/login`. Logout clears the session. |
| …see summaries and status of devices and alerts on the dashboard | Dashboard | Stat cards match node and alert counts. Alerts panel lists open alerts. |
| …see the status of nodes on the dashboard | Dashboard | Each node shows OK, Warning, Critical or Offline correctly against the simulator scenarios. |
| …see real-time data of each node on the dashboard | Dashboard | Values update within about 5 s of the simulator posting. The LIVE indicator is shown. |
| …see the tilt of each node on the devices page | Devices, Device detail | Tilt change is shown per node, with a chart on detail. |
| …see the acceleration of each node | Devices, Device detail | Magnitude on the card. X, Y and Z chart on detail. |
| …see the temperature of each node | Devices, Device detail | |
| …see the humidity of each node | Devices, Device detail | |
| …see the movement of each node | Devices, Device detail | Displacement in metres. N4's grows over time. |
| …see the battery of each node | Devices, Device detail | N5 visibly drains. |
| …see the gyroscope of each node | Devices, Device detail | |
| …see the slope angle from each node | Devices, Device detail | |
| …see the magnetic field of each node | Devices, Device detail | |
| …set an alert condition for battery on the new device page | New device | Rule saved, and an alert fires when crossed. |
| …set an alert condition for acceleration on the new device page | New device | Same. |
| …set an alert condition for slope angle on the new device page | New device | Same. |
| …see historical data of each node on the results page | Results | Choosing a node, parameter and range shows a chart and table. CSV downloads. |
| …see the nodes' locations on a map | Map | All nodes plotted. Popup shows the latest values and links to detail. |

---

## 15. Tests (pytest, backend)

Name or docstring each test with the requirement it covers. The owner will cite these as evidence in the thesis.

- **Auth (R1):**
  - a correct email and password returns a bearer token
  - a wrong password returns 401, and an unknown email gets the same 401 message
  - an inactive user can't get a token
  - protected endpoints return 401 with no token, a tampered token, or an expired token
  - a valid token returns the right user from `/api/auth/me`
- **Ingest:** a valid payload is stored, a bad API key gets 401, a duplicate timestamp isn't stored twice, an out-of-range value is stored with a flag (R8).
- **Derived:** slope angle from a known gravity vector, tilt change against the baseline, and haversine displacement for a known distance.
- **Alerts (R5, R7):** no alert before `consecutive_readings`, warning then critical escalation, auto-resolve, flagged readings ignored, the battery `lt` comparator, and the offline alert opening and closing.
- **Rules (R6):** creating or updating a rule without a justification is rejected.
- **Export (R10):** the CSV has headers and matches the readings in range.

Also write a short manual test script in `docs/TESTING.md` that walks through Milestone 1's "done when" checks, step by step, so the owner can repeat them and take screenshots.