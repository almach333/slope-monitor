/** Site map: every node as a circle coloured by status, with a popup of its latest values. */

import { Fragment, useMemo } from 'react'
import { Circle, CircleMarker, MapContainer, Polyline, Popup, Tooltip } from 'react-leaflet'
import { Link } from 'react-router'

import { useNodes } from '../api/queries'
import type { NodeStatus } from '../api/types'
import { DEFAULT_CENTRE, DarkTiles, FitBounds, nodePosition } from '../components/SiteMap'
import { ErrorState, LoadingState, PageHeader, STATUS_COLOUR, StatusBadge } from '../components/ui'
import { fmtAgo, fmtField } from '../lib/format'

const LEGEND: NodeStatus[] = ['ok', 'warning', 'critical', 'offline']

export function MapPage() {
  const nodes = useNodes()
  const points = useMemo(
    () => (nodes.data ?? []).map(nodePosition).filter((p): p is [number, number] => p !== null),
    [nodes.data],
  )

  return (
    <>
      <PageHeader eyebrow="Site overview" title="Map" />
      {nodes.isPending ? (
        <LoadingState label="Loading map…" />
      ) : nodes.isError ? (
        <ErrorState error={nodes.error} onRetry={() => nodes.refetch()} />
      ) : (
        <div className="relative overflow-hidden rounded-xl border border-line" style={{ height: 'calc(100vh - 13rem)', minHeight: 420 }}>
          <MapContainer center={points[0] ?? DEFAULT_CENTRE} zoom={16} className="h-full w-full" scrollWheelZoom>
            <DarkTiles />
            <FitBounds points={points} />
            {nodes.data.map((node) => {
              const pos = nodePosition(node)
              if (!pos) return null
              const colour = STATUS_COLOUR[node.status]
              const ref: [number, number] | null =
                node.ref_lat !== null && node.ref_lon !== null ? [node.ref_lat, node.ref_lon] : null
              const v = node.latest?.values ?? {}
              return (
                <Fragment key={node.id}>
                  {/* Reference position (dashed) and a line to where the node is now = movement. */}
                  {ref && (
                    <>
                      <Circle center={ref} radius={6} pathOptions={{ color: '#94a3b8', weight: 1, dashArray: '3 4', fill: false }} />
                      <Polyline positions={[ref, pos]} pathOptions={{ color: colour, weight: 1.5, dashArray: '2 4' }} />
                    </>
                  )}
                  <CircleMarker
                    center={pos}
                    radius={10}
                    pathOptions={{ color: '#0b1220', weight: 2, fillColor: colour, fillOpacity: 0.95 }}
                  >
                    <Tooltip permanent direction="right" offset={[12, 0]} className="node-label">
                      {node.name.split(' ')[0]}
                    </Tooltip>
                    <Popup minWidth={220}>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between gap-3">
                          <span className="font-semibold text-white">{node.name}</span>
                          <StatusBadge status={node.status} />
                        </div>
                        <dl className="num space-y-0.5 text-xs">
                          {[
                            ['Tilt change', fmtField('tilt_change_total', v.tilt_change_total)],
                            ['Battery', fmtField('battery_pct', v.battery_pct)],
                            ['Movement', fmtField('displacement_m', v.displacement_m)],
                            ['Last seen', fmtAgo(node.last_seen)],
                          ].map(([k, val]) => (
                            <div key={k} className="flex justify-between gap-4">
                              <dt className="text-muted">{k}</dt>
                              <dd className="text-slate-100">{val}</dd>
                            </div>
                          ))}
                        </dl>
                        <Link to={`/devices/${node.id}`} className="inline-block text-xs font-semibold text-accent hover:underline">
                          Open device details →
                        </Link>
                      </div>
                    </Popup>
                  </CircleMarker>
                </Fragment>
              )
            })}
          </MapContainer>

          <div className="pointer-events-none absolute top-3 left-14 z-[1000] rounded-lg border border-line bg-ink/85 px-3 py-2 text-xs">
            <div className="font-semibold text-white">Placeholder site — not a real mine</div>
            <div className="text-muted">Dashed line: reference position → current GPS position</div>
          </div>
          <div className="absolute bottom-6 left-3 z-[1000] flex gap-3 rounded-lg border border-line bg-ink/85 px-3 py-2 text-xs">
            {LEGEND.map((s) => (
              <span key={s} className="inline-flex items-center gap-1.5 capitalize text-slate-300">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: STATUS_COLOUR[s] }} />
                {s}
              </span>
            ))}
          </div>
        </div>
      )}
    </>
  )
}
