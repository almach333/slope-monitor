/** Devices: one card per node with the latest value of all 9 parameters. */

import { Link } from 'react-router'

import { useNodes } from '../api/queries'
import type { NodeOut } from '../api/types'
import { PlusIcon } from '../components/Icons'
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge } from '../components/ui'
import { fmtAgo, fmtField, fmtUtc } from '../lib/format'
import { NINE_PARAMETERS, fieldLabel } from '../lib/parameters'

function NodeCard({ node }: { node: NodeOut }) {
  const values = node.latest?.values ?? {}
  return (
    <article className="flex flex-col rounded-xl border border-line bg-panel">
      <header className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <h2 className="truncate font-semibold text-white">{node.name}</h2>
          <div className="num text-xs text-muted">{node.dev_eui}</div>
        </div>
        <StatusBadge status={node.status} />
      </header>

      <dl className="grid flex-1 grid-cols-3 gap-px bg-line/60">
        {NINE_PARAMETERS.map((field) => (
          <div key={field} className="bg-panel px-3 py-2.5">
            <dt className="text-[0.68rem] tracking-wide text-muted uppercase">{fieldLabel(field)}</dt>
            <dd className="num mt-0.5 text-sm text-slate-100">{fmtField(field, values[field])}</dd>
          </div>
        ))}
      </dl>

      <footer className="flex items-center justify-between gap-2 border-t border-line px-4 py-2.5">
        <span className="text-xs text-muted" title={fmtUtc(node.last_seen)}>
          Last seen {fmtAgo(node.last_seen)}
        </span>
        <Link
          to={`/devices/${node.id}`}
          className="rounded-lg border border-line bg-panel-2 px-3 py-1 text-sm text-slate-200 hover:border-slate-600 hover:text-white"
        >
          Inspect →
        </Link>
      </footer>
    </article>
  )
}

export function DevicesPage() {
  const nodes = useNodes()
  return (
    <>
      <PageHeader eyebrow="Sensor network" title="Devices">
        <Link
          to="/devices/new"
          className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-slate-950 hover:bg-teal-300"
        >
          <PlusIcon width={16} height={16} /> Add device
        </Link>
      </PageHeader>

      {nodes.isPending ? (
        <LoadingState label="Loading devices…" />
      ) : nodes.isError ? (
        <ErrorState error={nodes.error} onRetry={() => nodes.refetch()} />
      ) : nodes.data.length === 0 ? (
        <EmptyState title="No devices yet">Use “Add device” to register your first node.</EmptyState>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {nodes.data.map((n) => (
            <NodeCard key={n.id} node={n} />
          ))}
        </div>
      )}
    </>
  )
}
