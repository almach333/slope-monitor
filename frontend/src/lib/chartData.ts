/** Convert API responses into rows for TimeSeriesChart. */

import type { ChartPoint, MultiSeries } from '../api/types'
import type { ChartLine, ChartRow } from '../components/TimeSeriesChart'
import { NODE_COLOURS } from './parameters'

/** Device detail: API points -> rows with a numeric time `t`. */
export function toRows(points: ChartPoint[]): ChartRow[] {
  return points.map((p) => {
    const row: ChartRow = { t: Date.parse(p.ts), flagged: p.flagged }
    for (const [key, value] of Object.entries(p)) {
      if (key !== 'ts' && key !== 'flagged' && key !== 'gap') row[key] = value as number | null
    }
    return row
  })
}

/** Multi-node series -> one chart line per node, each with its own data. */
export function nodeLines(series: MultiSeries | undefined): ChartLine[] {
  if (!series) return []
  return series.series.map((s, i) => ({
    key: 'v',
    label: s.name,
    colour: NODE_COLOURS[i % NODE_COLOURS.length],
    data: s.points.map((p) => ({ t: Date.parse(p.ts), v: p.v })),
  }))
}
