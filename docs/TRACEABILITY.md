# Traceability: requirements → implementation → tests

R1–R7 are the owner's requirements. R8–R10 were proposed in the handoff and still need the owner's confirmation.

| ID | Requirement | Implemented by | Evidence (tests in `backend/tests/`) |
|---|---|---|---|
| R1 | Browser accessible, with authorised-user login | OAuth 2.0 password flow + JWT (`app/auth.py`, `routers/auth.py`). Argon2 password hashes. No sign-up: users come from `scripts/create_user.py`. Login page. 401 redirects to `/login`. In-memory login rate limit. | `test_auth.py`: correct login, same 401 for wrong password/unknown email, inactive user, missing/tampered/forged/expired token, `/me`, rate limit |
| R2 | Multi-node data and status shown simultaneously | `/api/dashboard/summary`, Dashboard table and cards, Devices grid, Map | `test_readings.py::test_dashboard_summary_counts`, `test_multi_node_series` |
| R3 | Historical and real-time data for each node | 5 s polling (`frontend/src/api/queries.ts`). `/api/nodes/{id}/readings` with downsampling. Device detail time ranges. Results page. | `test_ingest.py::test_valid_payload_is_stored`, `test_readings.py::test_downsampling_caps_points` |
| R4 | Node positions on a map | Map page (react-leaflet), fitted to site bounds, coloured by status, with a reference → current line | Manual: `docs/TESTING.md` §4 |
| R5 | Alert when slope tilt exceeds a safe limit | `tilt_change_total` and `slope_angle` rules. `app/alerts.py`. Auto baseline. | `test_alerts.py::test_tilt_alert_warning_then_critical_then_resolves`, `test_derived.py`, `test_rules.py::test_slope_angle_rule_waits_for_baseline_then_uses_offsets` |
| R6 | Safe limit can be set and changed, with justification | Rule editor (New device + Device detail). Required `justification`. `updated_by`/`updated_at`. `AlertRuleChange` audit history. | `test_rules.py`: create/update/delete without justification rejected, history records who/why/old/new |
| R7 | Multiple alert levels as a safety measure | Warning + critical per rule, debounce (K consecutive valid readings), escalation/de-escalation, auto-resolve, offline alerts | `test_alerts.py`: debounce, escalation, de-escalation, `lt` comparator, offline open/close |
| R8 *(proposed)* | Detect and flag invalid or missing data | `app/quality.py` (range + spike checks, per-field flags). Flagged values stored but excluded from alerts and baselines and hidden on charts. Gaps shown as breaks. Flagged/missed counts. | `test_quality.py`, `test_ingest.py::test_out_of_range_value_is_stored_with_a_flag`, `test_alerts.py::test_flagged_readings_are_ignored_by_alerts`, `test_readings.py::test_gaps_are_marked_with_null_points` |
| R9 *(proposed)* | Show node health (online/offline, battery, link quality) | Computed status, offline alerts, battery rule, RSSI/SNR chart | `test_alerts.py::test_offline_alert_opens_and_closes`, `test_battery_lt_rule` |
| R10 *(proposed)* | Export historical data | `/api/readings/export` (CSV), Results → Export CSV | `test_export.py` |

## Design decisions beyond the handoff (from the approved plan)

| Decision | Why |
|---|---|
| Derived values are computed when read, not stored | Changing the baseline or reference position would otherwise leave stale stored values |
| Automatic baseline from the median of the first 10 valid readings | Tilt alerts can't work without a baseline |
| Slope-angle rule stored as baseline offsets (+1°/+2°), "pending baseline" until one exists | Lets the New Device page set the rule before any data arrives |
| Per-field quality flags | A broken humidity sensor must not silence tilt alerts |
| One active alert per rule (escalation resolves the warning) | Avoids double-counting a warning and a critical for the same condition |
| Alert times use the reading's timestamp | Backfilled history shows the correct times |
| Device API keys hashed with SHA-256 | Keys are long random strings, so a fast hash is safe and allows lookup. Argon2 would make a 60k-reading backfill very slow. |
| Alerts resolve automatically only (no manual "resolve") | A manually resolved alert would just reopen while the condition persists |
| Rule change history table (`AlertRuleChange`) | Audit evidence for R6 |
