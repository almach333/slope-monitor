/** Device detail: metadata, latest reading, data quality, and one chart per parameter group. */

import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../api/client'
import { useAlertRules, useNode, useNodeReadings, useSetBaseline } from '../api/queries'
import type { AlertRule, NodeDetail } from '../api/types'
import { Modal } from '../components/Modal'
import { RulesManager } from '../components/RulesEditor'
import { TimeRangePicker } from '../components/TimeRangePicker'
import { TimeSeriesChart } from '../components/TimeSeriesChart'
import { Button, ErrorState, KeyValue, LoadingState, PageHeader, Panel, StatusBadge } from '../components/ui'
import { toRows } from '../lib/chartData'
import { DASH, fmtAgo, fmtCoord, fmtField, fmtNumber, fmtUtc } from '../lib/format'
import { CHART_GROUPS, FIELDS, SERIES_COLOURS, fieldLabel, fieldUnit } from '../lib/parameters'
import type { TimeRange } from '../lib/time'

/** All fields shown in the "Latest reading" list, in display order. */
const LATEST_FIELDS = [
  'tilt_change_x', 'tilt_change_y', 'tilt_change_total',
  'angle_x', 'angle_y', 'angle_z', 'slope_angle',
  'acc_x', 'acc_y', 'acc_z', 'acc_magnitude',
  'gyro_x', 'gyro_y', 'gyro_z', 'gyro_magnitude',
  'mag_x', 'mag_y', 'mag_z', 'mag_magnitude',
  'temperature', 'humidity', 'battery_pct', 'battery_v',
  'lat', 'lon', 'displacement_m', 'rssi', 'snr',
]

function MetadataPanel({ node }: { node: NodeDetail }) {
  return (
    <Panel title="Metadata">
      <dl className="divide-y divide-line/50">
        <KeyValue label="dev_eui">{node.dev_eui}</KeyValue>
        <KeyValue label="Reference position">{fmtCoord(node.ref_lat, node.ref_lon)}</KeyValue>
        <KeyValue label="Expected interval">{node.expected_interval_s} s</KeyValue>
        <KeyValue label="Baseline angle X / Y">
          {node.baseline_angle_x === null
            ? 'not set'
            : `${fmtNumber(node.baseline_angle_x, 2)}° / ${fmtNumber(node.baseline_angle_y, 2)}°`}
        </KeyValue>
        <KeyValue label="Baseline slope angle">
          {node.baseline_slope_angle === null ? 'not set' : `${fmtNumber(node.baseline_slope_angle, 2)}°`}
        </KeyValue>
        <KeyValue label="Baseline set">{node.baseline_set_at ? fmtUtc(node.baseline_set_at, false) : DASH}</KeyValue>
        <KeyValue label="Registered">{fmtUtc(node.created_at, false)}</KeyValue>
      </dl>
      {node.description && <p className="mt-3 text-sm text-muted">{node.description}</p>}
    </Panel>
  )
}

function QualityPanel({ node }: { node: NodeDetail }) {
  return (
    <Panel title="Uplinks & data quality">
      <div className="grid grid-cols-3 gap-2 text-center">
        {[
          ['Uplinks', node.counts.uplinks, 'text-white'],
          ['Flagged', node.counts.flagged, node.counts.flagged ? 'text-warn' : 'text-white'],
          ['Missed', node.counts.missed, node.counts.missed ? 'text-warn' : 'text-white'],
        ].map(([label, value, cls]) => (
          <div key={label as string} className="rounded-lg bg-panel-2 px-2 py-3">
            <div className={`num text-xl font-bold ${cls}`}>{(value as number).toLocaleString()}</div>
            <div className="eyebrow mt-1">{label}</div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-muted">
        Flagged readings failed a range or spike check: they are stored but excluded from alerts and hidden on charts by
        default. Missed uplinks are estimated from packet counters / gaps.
      </p>
    </Panel>
  )
}

function LatestPanel({ node }: { node: NodeDetail }) {
  const latest = node.latest
  return (
    <Panel
      title="Latest reading"
      actions={latest && <span className="num text-xs text-muted">{fmtAgo(latest.ts)}</span>}
    >
      {!latest ? (
        <p className="text-sm text-muted">No data received yet.</p>
      ) : (
        <>
          <div className="num mb-2 text-xs text-muted">
            {fmtUtc(latest.ts)} {latest.seq !== null && `· seq ${latest.seq}`}
          </div>
          {latest.quality_flags.length > 0 && (
            <div className="mb-2 rounded border border-warn/30 bg-warn/10 px-2 py-1 text-xs text-warn">
              Flagged: {latest.quality_flags.join(', ')}
            </div>
          )}
          <dl className="divide-y divide-line/50">
            {LATEST_FIELDS.map((f) => (
              <KeyValue key={f} label={fieldLabel(f)}>
                {fmtField(f, latest.values[f])}
              </KeyValue>
            ))}
          </dl>
        </>
      )}
    </Panel>
  )
}

function activeRule(rules: AlertRule[] | undefined, parameter?: string): AlertRule | undefined {
  if (!rules || !parameter) return undefined
  return rules.find((r) => r.parameter === parameter && r.enabled && !r.pending_baseline)
}

export function DeviceDetailPage() {
  const id = Number(useParams().id)
  const node = useNode(id)
  const rules = useAlertRules(id)
  const [range, setRange] = useState<TimeRange>({ key: '24h' })
  const [showFlagged, setShowFlagged] = useState(false)
  const readings = useNodeReadings(id, range, showFlagged)
  const [rulesOpen, setRulesOpen] = useState(false)
  const [baselineOpen, setBaselineOpen] = useState(false)
  const setBaseline = useSetBaseline(id)
  const [baselineMessage, setBaselineMessage] = useState<string | null>(null)

  const rows = useMemo(() => (readings.data ? toRows(readings.data.points) : []), [readings.data])

  if (node.isPending) return <LoadingState label="Loading device…" />
  if (node.isError) {
    if (node.error instanceof ApiError && node.error.status === 404) {
      return (
        <div className="py-16 text-center">
          <div className="text-lg font-semibold text-white">Device not found</div>
          <Link to="/devices" className="mt-2 inline-block text-accent hover:underline">
            ← Back to devices
          </Link>
        </div>
      )
    }
    return <ErrorState error={node.error} onRetry={() => node.refetch()} />
  }

  const n = node.data
  const from = readings.data ? Date.parse(readings.data.from) : 0
  const to = readings.data ? Date.parse(readings.data.to) : 0

  const confirmBaseline = () => {
    setBaseline.mutate(undefined, {
      onSuccess: (result) => {
        const updated = result.updated_rules
          .map((r) => `${fieldLabel(r.parameter)}: warning ${fmtNumber(r.warning_threshold, 2)}°, critical ${fmtNumber(r.critical_threshold, 2)}°`)
          .join('; ')
        setBaselineMessage(
          `Baseline set to ${fmtNumber(result.node.baseline_angle_x, 2)}° / ${fmtNumber(result.node.baseline_angle_y, 2)}°.` +
            (updated ? ` Updated thresholds — ${updated}.` : ''),
        )
        setBaselineOpen(false)
      },
    })
  }

  return (
    <>
      <div className="mb-2 text-sm">
        <Link to="/devices" className="text-muted hover:text-white">
          ← Devices
        </Link>
      </div>
      <PageHeader eyebrow={`Device · ${n.dev_eui}`} title={n.name}>
        <StatusBadge status={n.status} />
        <Button onClick={() => setBaselineOpen(true)}>Set baseline now</Button>
        <Button variant="primary" onClick={() => setRulesOpen(true)}>
          Edit alert rules
        </Button>
      </PageHeader>

      {baselineMessage && (
        <div className="mb-4 flex items-start justify-between gap-3 rounded-lg border border-ok/30 bg-ok/10 px-4 py-2 text-sm text-ok" role="status">
          <span>{baselineMessage}</span>
          <button type="button" className="text-muted hover:text-white" onClick={() => setBaselineMessage(null)}>
            ✕
          </button>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[22rem_1fr]">
        <div className="space-y-6">
          <MetadataPanel node={n} />
          <QualityPanel node={n} />
          <LatestPanel node={n} />
        </div>

        <div className="min-w-0">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <TimeRangePicker value={range} onChange={setRange} />
            <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-muted">
              <input
                type="checkbox"
                className="accent-[#2dd4bf]"
                checked={showFlagged}
                onChange={(e) => setShowFlagged(e.target.checked)}
              />
              Show flagged readings
            </label>
          </div>

          {readings.isPending ? (
            <LoadingState label="Loading readings…" />
          ) : readings.isError ? (
            <ErrorState error={readings.error} onRetry={() => readings.refetch()} />
          ) : (
            <>
              {rows.length === 0 && (
                <div className="mb-4 rounded-lg border border-line bg-panel px-4 py-3 text-sm text-muted">
                  No readings in this time range.
                </div>
              )}
              {readings.data.bucket_s > 0 && (
                <div className="mb-3 text-xs text-muted">
                  Showing {fmtNumber(readings.data.bucket_s / 60, 1)}-minute averages ({rows.length} points).
                </div>
              )}
              <div className="grid gap-4 2xl:grid-cols-2">
                {CHART_GROUPS.map((group) => {
                  const rule = activeRule(rules.data, group.ruleParameter)
                  const fields = [...group.fields, ...(group.rightFields ?? [])]
                  const lines = fields.map((f, i) => ({
                    key: f,
                    label: fieldLabel(f),
                    colour: SERIES_COLOURS[i % SERIES_COLOURS.length],
                    right: group.rightFields?.includes(f),
                  }))
                  const unit = fieldUnit(group.fields[0])
                  return (
                    <Panel
                      key={group.title}
                      title={
                        <>
                          {group.title} <span className="font-normal text-muted">({unit || 'value'})</span>
                        </>
                      }
                      actions={
                        <span className="text-xs text-muted">
                          {group.title === 'Tilt change' && n.baseline_angle_x === null
                            ? 'no baseline yet'
                            : group.note}
                          {group.rightFields && `RSSI left axis · SNR (${fieldUnit(group.rightFields[0])}) right axis`}
                        </span>
                      }
                    >
                      <TimeSeriesChart
                        data={rows}
                        lines={lines}
                        fromMs={from}
                        toMs={to}
                        unit={unit}
                        rightUnit={group.rightFields ? fieldUnit(group.rightFields[0]) : ''}
                        decimals={Math.min(FIELDS[group.fields[0]]?.decimals ?? 2, 3)}
                        warning={rule && fields.includes(rule.parameter) ? rule.warning_threshold : null}
                        critical={rule && fields.includes(rule.parameter) ? rule.critical_threshold : null}
                        markFlagged={showFlagged}
                        height={190}
                      />
                      {rule && !fields.includes(rule.parameter) && (
                        <div className="mt-1 text-xs text-muted">
                          Alert rule on {fieldLabel(rule.parameter).toLowerCase()}: warning{' '}
                          {fmtField(rule.parameter, rule.warning_threshold)}, critical{' '}
                          {fmtField(rule.parameter, rule.critical_threshold)}
                        </div>
                      )}
                    </Panel>
                  )
                })}
              </div>
            </>
          )}
        </div>
      </div>

      <Modal open={rulesOpen} onClose={() => setRulesOpen(false)} title={`Alert rules — ${n.name}`} wide>
        <RulesManager nodeId={id} />
      </Modal>

      <Modal open={baselineOpen} onClose={() => setBaselineOpen(false)} title="Set baseline now?">
        <p className="text-sm text-slate-300">
          The tilt baseline will be set to the median of this node’s last 10 valid readings. Tilt change is measured
          from the baseline, so all tilt-change values (including history) will be recalculated.
        </p>
        <p className="mt-2 text-sm text-slate-300">
          Slope-angle rules defined relative to the baseline will get new thresholds. Only do this after confirming the
          node is stable (e.g. after installation or maintenance).
        </p>
        {setBaseline.isError && (
          <div className="mt-3 rounded border border-crit/40 bg-crit/10 px-3 py-2 text-sm text-crit">
            {setBaseline.error.message}
          </div>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <Button onClick={() => setBaselineOpen(false)}>Cancel</Button>
          <Button variant="primary" disabled={setBaseline.isPending} onClick={confirmBaseline}>
            {setBaseline.isPending ? 'Setting…' : 'Set baseline'}
          </Button>
        </div>
      </Modal>
    </>
  )
}
