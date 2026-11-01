/** Results (history): compare one parameter across nodes, browse readings, export CSV. */

import { useEffect, useMemo, useState } from 'react'

import { apiDownload, qs } from '../api/client'
import { useNodes, useReadingsPage, useSeries } from '../api/queries'
import { DownloadIcon } from '../components/Icons'
import { TimeRangePicker } from '../components/TimeRangePicker'
import { TimeSeriesChart } from '../components/TimeSeriesChart'
import { Button, EmptyState, ErrorState, LoadingState, PageHeader, Panel, inputClass } from '../components/ui'
import { nodeLines } from '../lib/chartData'
import { fmtField, fmtUtc } from '../lib/format'
import { FIELDS, NINE_PARAMETERS, NODE_COLOURS, RESULT_FIELDS, fieldLabel, fieldUnit } from '../lib/parameters'
import { type TimeRange, resolveRange } from '../lib/time'

const PAGE_SIZE = 50

export function ResultsPage() {
  const nodes = useNodes()
  const [selected, setSelected] = useState<number[] | null>(null)
  const [field, setField] = useState('tilt_change_total')
  const [range, setRange] = useState<TimeRange>({ key: '24h' })
  const [page, setPage] = useState(1)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)

  // Select every node by default once they have loaded.
  useEffect(() => {
    if (nodes.data && selected === null) setSelected(nodes.data.map((n) => n.id))
  }, [nodes.data, selected])
  useEffect(() => setPage(1), [selected, range])

  const nodeIds = selected ?? []
  const series = useSeries(field, nodeIds, range, 500)
  const table = useReadingsPage(nodeIds, range, page, PAGE_SIZE)
  const lines = useMemo(() => nodeLines(series.data), [series.data])
  // Keep each node's colour stable however the selection changes.
  const colourOf = (id: number) => NODE_COLOURS[(nodes.data?.findIndex((n) => n.id === id) ?? 0) % NODE_COLOURS.length]
  const colouredLines = lines.map((l, i) => ({ ...l, colour: colourOf(series.data!.series[i].node_id) }))

  const toggle = (id: number) =>
    setSelected((s) => (s?.includes(id) ? s.filter((x) => x !== id) : [...(s ?? []), id]))

  const exportCsv = async () => {
    setExporting(true)
    setExportError(null)
    try {
      const { from, to } = resolveRange(range)
      await apiDownload(`/api/readings/export${qs({ node_ids: nodeIds.join(','), from, to })}`, 'readings.csv')
    } catch (e) {
      setExportError(e instanceof Error ? e.message : 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  const totalPages = table.data ? Math.max(1, Math.ceil(table.data.total / PAGE_SIZE)) : 1
  const tableFields = Array.from(new Set([field, ...NINE_PARAMETERS]))

  return (
    <>
      <PageHeader eyebrow="History" title="Results">
        <Button variant="primary" disabled={!nodeIds.length || exporting} onClick={exportCsv}>
          <DownloadIcon width={16} height={16} /> {exporting ? 'Exporting…' : 'Export CSV'}
        </Button>
      </PageHeader>
      {exportError && <div className="mb-4 rounded-lg border border-crit/40 bg-crit/10 px-3 py-2 text-sm text-crit">{exportError}</div>}

      <Panel className="mb-6">
        <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
          <div>
            <div className="eyebrow mb-2">Nodes</div>
            {nodes.isPending ? (
              <LoadingState />
            ) : nodes.isError ? (
              <ErrorState error={nodes.error} />
            ) : (
              <div className="flex flex-wrap gap-2">
                {nodes.data.map((n, i) => {
                  const on = nodeIds.includes(n.id)
                  return (
                    <button
                      key={n.id}
                      type="button"
                      aria-pressed={on}
                      onClick={() => toggle(n.id)}
                      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm ${
                        on ? 'border-slate-500 bg-panel-2 text-white' : 'border-line text-muted hover:text-white'
                      }`}
                    >
                      <span className="h-2 w-2 rounded-full" style={{ background: on ? NODE_COLOURS[i % NODE_COLOURS.length] : '#334155' }} />
                      {n.name}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
          <label className="text-sm">
            <div className="eyebrow mb-2">Parameter</div>
            <select className={`${inputClass} min-w-56`} value={field} onChange={(e) => setField(e.target.value)}>
              {RESULT_FIELDS.map((f) => (
                <option key={f} value={f}>
                  {fieldLabel(f)} ({fieldUnit(f)})
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="mt-4">
          <div className="eyebrow mb-2">Date range</div>
          <TimeRangePicker value={range} onChange={setRange} />
        </div>
      </Panel>

      <Panel title={`${fieldLabel(field)} — node comparison`} eyebrow={`Unit: ${fieldUnit(field) || 'none'}`} className="mb-6">
        {!nodeIds.length ? (
          <EmptyState title="Select at least one node" />
        ) : series.isPending ? (
          <LoadingState />
        ) : series.isError ? (
          <ErrorState error={series.error} onRetry={() => series.refetch()} />
        ) : series.data.series.every((s) => s.points.length === 0) ? (
          <EmptyState title="No readings in this range" />
        ) : (
          <TimeSeriesChart
            data={[]}
            lines={colouredLines}
            fromMs={Date.parse(series.data.from)}
            toMs={Date.parse(series.data.to)}
            unit={fieldUnit(field)}
            decimals={Math.min(FIELDS[field]?.decimals ?? 2, 3)}
            height={300}
          />
        )}
      </Panel>

      <Panel
        title="Readings"
        eyebrow={table.data ? `${table.data.total.toLocaleString()} readings, newest first` : undefined}
        bodyClassName="overflow-x-auto"
      >
        {!nodeIds.length ? (
          <EmptyState title="Select at least one node" />
        ) : table.isPending ? (
          <LoadingState />
        ) : table.isError ? (
          <ErrorState error={table.error} onRetry={() => table.refetch()} />
        ) : table.data.items.length === 0 ? (
          <EmptyState title="No readings in this range" />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line bg-panel-2 text-left text-xs text-muted">
                <th className="px-3 py-2 font-medium">Time (UTC)</th>
                <th className="px-3 py-2 font-medium">Node</th>
                {tableFields.map((f) => (
                  <th key={f} className="px-3 py-2 font-medium whitespace-nowrap">
                    {fieldLabel(f)}
                  </th>
                ))}
                <th className="px-3 py-2 font-medium">Flags</th>
              </tr>
            </thead>
            <tbody>
              {table.data.items.map((r) => (
                <tr key={r.id} className="border-b border-line/60 last:border-0">
                  <td className="num px-3 py-1.5 whitespace-nowrap">{fmtUtc(r.ts).replace(' UTC', '')}</td>
                  <td className="px-3 py-1.5 whitespace-nowrap">{r.node_name}</td>
                  {tableFields.map((f) => (
                    <td key={f} className={`num px-3 py-1.5 whitespace-nowrap ${f === field ? 'text-white' : 'text-slate-400'}`}>
                      {fmtField(f, r.values[f])}
                    </td>
                  ))}
                  <td className="px-3 py-1.5 text-xs text-warn">{r.quality_flags.join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {table.data && totalPages > 1 && (
        <div className="mt-4 flex items-center justify-end gap-3 text-sm text-muted">
          <Button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            ← Newer
          </Button>
          <span className="num">
            Page {page} of {totalPages.toLocaleString()}
          </span>
          <Button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Older →
          </Button>
        </div>
      )}
    </>
  )
}
