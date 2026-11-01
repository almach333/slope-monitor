# Manual test script: Milestone 1 "done when" checks

Use this to demonstrate the prototype and take screenshots for the report. It takes about 15 minutes, and most of that is waiting for N6's scheduled outage.

## 0. Prepare (fresh data)

Do sections 1 and 2 of the README first: install, then start the API and web app. Then reset the data and generate history:

```powershell
cd backend
..\.venv\Scripts\python -m scripts.seed --reset
cd ..\simulator
Remove-Item keys.json -ErrorAction SilentlyContinue
py -3.13 simulate.py backfill --days 7 --interval 60
py -3.13 simulate.py live --interval 10
```

Leave live mode running. It prints a line every 10 s, and `(N6)` in brackets means N6's packet was not received.

## 1. Login: R1

| # | Step | Expected | Screenshot |
|---|---|---|---|
| 1.1 | Open http://localhost:5173/devices while logged out | Redirected to the login page | |
| 1.2 | Sign in with a wrong password | "Incorrect email or password" | ✔ login error |
| 1.3 | Sign in with `admin@example.com` / `slope-demo-2026` | The Dashboard opens | ✔ login page |
| 1.4 | Click **Log out** (bottom of the sidebar), then press Back | You're on the login page and can't get back in without signing in | |

## 2. Dashboard: R2, R3, R9

| # | Step | Expected | Screenshot |
|---|---|---|---|
| 2.1 | Look at the stat cards | Nodes 6, Online 6 (or 5 during N6's outage), and Active alerts at least 3 | ✔ dashboard |
| 2.2 | Look at the node table | N4 and N5 are **Critical**, N1–N3 are **OK**. "Last seen" stays under 10 s. | |
| 2.3 | Watch for 15 s | The LIVE badge pulses, "last seen" and the values update, and the 6 h tilt chart grows | |
| 2.4 | Active alerts panel | N4 tilt change critical, N4 slope angle critical, N5 battery critical | |

## 3. Devices and Device detail: the 9 parameters (user stories)

| # | Step | Expected | Screenshot |
|---|---|---|---|
| 3.1 | Open **Devices** | 6 cards, each with tilt change, slope angle, acceleration, gyroscope, magnetic field, temperature, humidity, battery and movement | ✔ devices |
| 3.2 | N4 → **Inspect** → **7 days** | The tilt-change chart rises slowly, then curves up sharply in the last 2 days and crosses the dashed amber (1°) and red (2°) lines. Movement grows to several metres. | ✔ N4 detail |
| 3.3 | Try **1 h / 6 h / 24 h / Custom** | Charts redraw for the range. 7 days shows "x-minute averages". | |
| 3.4 | N5 → 7 days | The battery chart drains past 20 % and then 10 % | ✔ N5 battery |
| 3.5 | N6 → 7 days | The uplinks panel shows flagged readings and missed uplinks, and the charts have a visible gap (the 2-hour outage about 3 days ago) | |
| 3.6 | N6 → tick **Show flagged readings** | Red dots appear where spike readings (±99°, 20 g) were flagged. Untick it and they disappear. | ✔ N6 flagged |

## 4. Map: R4

| # | Step | Expected | Screenshot |
|---|---|---|---|
| 4.1 | Open **Map** | 6 circles at site scale (not a world map): green OK, red critical. Labelled "Placeholder site — not a real mine". | ✔ map |
| 4.2 | Click N4 | The popup shows status, tilt change, battery, movement and last seen, plus a link to the detail page. A dashed line runs from the reference position to the current position. | |

*Map tiles need internet. Without it, the circles still appear on a blank background.*

## 5. Alerts: R5, R7

| # | Step | Expected | Screenshot |
|---|---|---|---|
| 5.1 | **Alerts → Resolved** | N4 *Tilt change* **warning**, resolved with "Escalated to critical", **then** N4 tilt **critical** under Open. This is N4 going warning then critical. | ✔ alert history |
| 5.2 | Same list | N5 *Battery* warning → escalated → critical | |
| 5.3 | Same list | N6 *Offline* alert for the 2-hour gap in its history ("Data resumed") | |
| 5.4 | **Open** → **Acknowledge** on one alert | It moves to the Acknowledged tab. The sidebar badge drops by one, but the dashboard still counts it as active. | |

## 6. N6 goes offline live: R7, R9

N6 is silent for 5 minutes every 30 minutes (at :00–:05 and :30–:35 past each hour, UTC). Its offline threshold is 3 × 60 s.

| # | Step | Expected | Screenshot |
|---|---|---|---|
| 6.1 | About 3–4 minutes into a silent window, look at the Dashboard | N6 shows **Offline** (grey), the Offline card shows 1, and an N6 *Offline* warning alert appears | ✔ N6 offline |
| 6.2 | After the window ends | N6 is back to OK within about 10 s, and the offline alert moves to Resolved ("Data resumed") | |

## 7. Milestone 2 checks: R6, R10

| # | Step | Expected |
|---|---|---|
| 7.1 | Devices → **Add device**. Fill in the name and a 16-hex dev_eui, click the map, keep the 4 default rules, and **Register**. | A dialog shows the one-time API key with a Copy button and a warning |
| 7.2 | Clear one rule's justification and try to save | It's blocked with "Justification is required" |
| 7.3 | Device detail → **Edit alert rules** → Edit → change a threshold and give a reason → Save. Then open **Change history**. | The change is listed with who, when, old → new values, and the reason |
| 7.4 | Device detail → **Set baseline now** → confirm | Tilt change drops to about 0, and the slope-angle thresholds are recalculated (shown in a message) |
| 7.5 | **Results**: pick nodes, a parameter and a range | A comparison chart (one line per node) and a paginated table |
| 7.6 | Results → **Export CSV** | A `.csv` downloads with a header row and the readings in the range |

## 8. Automated tests

```powershell
cd backend
..\.venv\Scripts\python -m pytest -v
```
All tests should pass. Each test's docstring names the requirement it covers. See [TRACEABILITY.md](TRACEABILITY.md).
