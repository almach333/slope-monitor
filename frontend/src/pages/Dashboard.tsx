/** Dashboard: stat cards, node status table, active alerts, live tilt chart. Polls every 5 s. */

import { useMemo } from 'react'
import { Link, useNavigate } from 'react-router'

import { useDashboardSummary, useSeries } from '../api/queries'
import type { Alert } from '../api/types'
import { TimeSeriesChart } from '../components/TimeSeriesChart'
import { EmptyState, ErrorState, LevelBadge, LoadingState, PageHeader, Panel, StatCard, StatusBadge } from '../components/ui'
import { nodeLines } from '../lib/chartData'
import { fmtAgo, fmtField, fmtUtc } from '../lib/format'
import type { TimeRange } from '../lib/time'

const LIVE_RANGE: TimeRange = { key: '6h' }

function AlertItem({ alert }: { alert: Alert }) {
  const border = alert.level === 'critical' ? 'border-l-crit' : 'border-l-warn'
  return (
    <li className={`border-l-2 ${border} px-4 py-3`}>
      <div className="flex items-center justify-between gap-2">
        <Link to={`/devices/${alert.node_id}`} className="text-sm font-semibold text-white hover:underline">
          {alert.node_name}
        </Link>
        <div className="flex items-center gap-1.5">
          {alert.status === 'open' && (
            <span className="rounded bg-accent/15 px-1.5 text-[0.65rem] font-bold tracking-wider text-accent uppercase">
              new
            </span>
          )}
          <LevelBadge level={alert.level} />
        </div>
      </div>
      <div className="mt-1 text-sm text-slate-300">{alert.message}</div>
      <div className="num mt-1 text-xs text-muted" title={fmtUtc(alert.opened_at)}>
        {fmtUtc(alert.opened_at, false)} · {fmtAgo(alert.opened_at)}
      </div>
    </li>
  )
}

export function DashboardPage() {
  const summary = useDashboardSummary()
  const series = useSeries('tilt_change_total', null, LIVE_RANGE, 240)
  const navigate = useNavigate()

  const lines = useMemo(() => nodeLines(series.data), [series.data])
  const range = series.data ? { from: Date.parse(series.data.from), to: Date.parse(series.data.to) } : null

  if (summary.isPending) return <LoadingState label="Loading dashboard…" />
  if (summary.isError) return <ErrorState error={summary.error} onRetry={() => summary.refetch()} />

  const { counts, nodes, active_alerts: alerts } = summary.data
  const now = Date.parse(summary.data.server_time)

  return (
    <>
      <PageHeader eyebrow="Overview" title="Dashboard" />

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Nodes" value={counts.nodes} sub="registered" />
        <StatCard label="Online" value={counts.online} tone="ok" sub="reporting on schedule" />
        <StatCard
          label="Offline"
          value={counts.offline}
          tone={counts.offline ? 'offline' : 'default'}
          sub="no data for 3 × interval"
        />
        <StatCard
          label="Active alerts"
          value={counts.alerts_active}
          tone={counts.alerts_critical ? 'crit' : counts.alerts_warning ? 'warn' : 'default'}
          sub={
            <>
              <span className="text-crit">{counts.alerts_critical} critical</span> ·{' '}
              <span className="text-warn">{counts.alerts_warning} warning</span> · {counts.alerts_new} new
            </>
          }
        />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Panel title="Node status" eyebrow="All nodes" className="xl:col-span-2" bodyClassName="overflow-x-auto">
          {nodes.length === 0 ? (
            <EmptyState title="No nodes registered yet">
              Add a device, or run the simulator (<span className="num">simulate.py setup</span>).
            </EmptyState>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line bg-panel-2 text-left text-xs text-muted">
                  {['Node', 'Status', 'Tilt change', 'Slope angle', 'Battery', 'Temp', 'RSSI', 'Last seen'].map((h) => (
                    <th key={h} className="px-4 py-2 font-medium whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {nodes.map((n) => {
                  const v = n.latest?.values ?? {}
                  return (
                    <tr
                      key={n.id}
                      className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-panel-2"
                      onClick={() => navigate(`/devices/${n.id}`)}
                    >
                      <td className="px-4 py-2.5">
                        <Link to={`/devices/${n.id}`} className="font-semibold text-white hover:underline">
                          {n.name}
                        </Link>
                        <div className="num text-xs text-muted">{n.dev_eui}</div>
                      </td>
                      <td className="px-4 py-2.5">
                        <StatusBadge status={n.status} />
                      </td>
                      <td className="num px-4 py-2.5 whitespace-nowrap">{fmtField('tilt_change_total', v.tilt_change_total)}</td>
                      <td className="num px-4 py-2.5 whitespace-nowrap">{fmtField('slope_angle', v.slope_angle)}</td>
                      <td
                        className={`num px-4 py-2.5 whitespace-nowrap ${
                          (v.battery_pct ?? 100) < 20 ? 'text-warn' : ''
                        }`}
                      >
                        {fmtField('battery_pct', v.battery_pct)}
                      </td>
                      <td className="num px-4 py-2.5 whitespace-nowrap">{fmtField('temperature', v.temperature)}</td>
                      <td className="num px-4 py-2.5 whitespace-nowrap">{fmtField('rssi', v.rssi)}</td>
                      <td className="num px-4 py-2.5 whitespace-nowrap text-muted" title={fmtUtc(n.last_seen)}>
                        {fmtAgo(n.last_seen, now)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel
          title="Active alerts"
          eyebrow="Newest first"
          actions={
            <Link to="/alerts" className="text-xs font-semibold text-accent hover:underline">
              All alerts →
            </Link>
          }
          bodyClassName="max-h-[26rem] overflow-y-auto"
        >
          {alerts.length === 0 ? (
            <EmptyState title="No active alerts">All nodes are within their thresholds.</EmptyState>
          ) : (
            <ul className="divide-y divide-line/60">
              {alerts.map((a) => (
                <AlertItem key={a.id} alert={a} />
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="Live readings — tilt change, last 6 h" eyebrow="All nodes" className="mt-6">
        {series.isPending ? (
          <LoadingState />
        ) : series.isError ? (
          <ErrorState error={series.error} onRetry={() => series.refetch()} />
        ) : lines.length === 0 || !range ? (
          <EmptyState title="No readings in the last 6 hours" />
        ) : (
          <TimeSeriesChart data={[]} lines={lines} fromMs={range.from} toMs={range.to} unit="°" decimals={3} height={220} />
        )}
      </Panel>
    </>
  )
}
