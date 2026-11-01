/** Alerts: Open / Acknowledged / Resolved tabs with an Acknowledge button. */

import { useState } from 'react'
import { Link } from 'react-router'

import { useAcknowledgeAlert, useAlerts } from '../api/queries'
import type { Alert, AlertStatus } from '../api/types'
import { Button, EmptyState, ErrorState, LevelBadge, LoadingState, PageHeader, Panel, Segmented } from '../components/ui'
import { fmtAgo, fmtAlertValue, fmtUtc } from '../lib/format'
import { fieldLabel } from '../lib/parameters'

const PAGE_SIZE = 50

const TABS: { key: AlertStatus; label: string; help: string }[] = [
  { key: 'open', label: 'Open', help: 'New alerts that nobody has acknowledged yet.' },
  {
    key: 'acknowledged',
    label: 'Acknowledged',
    help: 'Seen by an engineer. They stay here until the condition clears (resolves automatically).',
  },
  {
    key: 'resolved',
    label: 'Resolved',
    help: 'Closed automatically after the set number of normal readings, on escalation/de-escalation, or when data resumed.',
  },
]

function TabCount({ status }: { status: AlertStatus }) {
  const q = useAlerts({ status, limit: 1 })
  return <span className="num ml-1.5 text-xs text-muted">{q.data?.total ?? ''}</span>
}

function parameterName(p: string) {
  return p === 'offline' ? 'Offline' : fieldLabel(p)
}

export function AlertsPage() {
  const [tab, setTab] = useState<AlertStatus>('open')
  const [page, setPage] = useState(0)
  const alerts = useAlerts({ status: tab, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
  const ack = useAcknowledgeAlert()

  const changeTab = (t: AlertStatus) => {
    setTab(t)
    setPage(0)
  }
  const total = alerts.data?.total ?? 0
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const columns = ['Opened', 'Node', 'Parameter', 'Level', 'Value', 'Threshold', 'Message']
  if (tab === 'acknowledged') columns.push('Acknowledged')
  if (tab === 'resolved') columns.push('Resolved')
  if (tab === 'open') columns.push('')

  const row = (a: Alert) => (
    <tr key={a.id} className={`border-b border-line/60 last:border-0 ${a.level === 'critical' ? 'bg-crit/[0.04]' : ''}`}>
      <td className="num px-4 py-2.5 whitespace-nowrap" title={fmtUtc(a.opened_at)}>
        {fmtUtc(a.opened_at, false)}
        <div className="text-xs text-muted">{fmtAgo(a.opened_at)}</div>
      </td>
      <td className="px-4 py-2.5 whitespace-nowrap">
        <Link to={`/devices/${a.node_id}`} className="font-semibold text-white hover:underline">
          {a.node_name}
        </Link>
      </td>
      <td className="px-4 py-2.5 whitespace-nowrap">{parameterName(a.parameter)}</td>
      <td className="px-4 py-2.5">
        <LevelBadge level={a.level} />
      </td>
      <td className="num px-4 py-2.5 whitespace-nowrap">{fmtAlertValue(a.parameter, a.value)}</td>
      <td className="num px-4 py-2.5 whitespace-nowrap">{fmtAlertValue(a.parameter, a.threshold)}</td>
      <td className="px-4 py-2.5 text-slate-300">{a.message}</td>
      {tab === 'acknowledged' && (
        <td className="num px-4 py-2.5 whitespace-nowrap text-muted">{fmtUtc(a.acknowledged_at, false)}</td>
      )}
      {tab === 'resolved' && (
        <td className="num px-4 py-2.5 whitespace-nowrap text-muted">
          {fmtUtc(a.resolved_at, false)}
          {a.resolution_note && <div className="font-sans text-xs">{a.resolution_note}</div>}
        </td>
      )}
      {tab === 'open' && (
        <td className="px-4 py-2.5 text-right">
          <Button disabled={ack.isPending && ack.variables === a.id} onClick={() => ack.mutate(a.id)}>
            Acknowledge
          </Button>
        </td>
      )}
    </tr>
  )

  return (
    <>
      <PageHeader eyebrow="Safety" title="Alerts">
        <Segmented
          label="Alert status"
          value={tab}
          onChange={changeTab}
          options={TABS.map((t) => ({
            key: t.key,
            label: (
              <>
                {t.label}
                <TabCount status={t.key} />
              </>
            ),
          }))}
        />
      </PageHeader>

      <p className="mb-4 text-sm text-muted">{TABS.find((t) => t.key === tab)?.help}</p>
      {ack.isError && (
        <div className="mb-4 rounded-lg border border-crit/40 bg-crit/10 px-3 py-2 text-sm text-crit">{ack.error.message}</div>
      )}

      <Panel bodyClassName="overflow-x-auto">
        {alerts.isPending ? (
          <LoadingState label="Loading alerts…" />
        ) : alerts.isError ? (
          <ErrorState error={alerts.error} onRetry={() => alerts.refetch()} />
        ) : alerts.data.items.length === 0 ? (
          <EmptyState title={`No ${tab} alerts`} />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line bg-panel-2 text-left text-xs text-muted">
                {columns.map((c) => (
                  <th key={c} className="px-4 py-2 font-medium whitespace-nowrap">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>{alerts.data.items.map(row)}</tbody>
          </table>
        )}
      </Panel>

      {pages > 1 && (
        <div className="mt-4 flex items-center justify-end gap-3 text-sm text-muted">
          <Button disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            ← Newer
          </Button>
          <span className="num">
            Page {page + 1} of {pages}
          </span>
          <Button disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>
            Older →
          </Button>
        </div>
      )}
    </>
  )
}
