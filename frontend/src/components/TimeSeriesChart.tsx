/**
 * Time-series line chart (Recharts) used on Device detail, Dashboard and Results.
 *
 * - X axis is time in UTC.
 * - `null` values break the line, so gaps in the data show as gaps.
 * - Optional warning / critical threshold lines (dashed amber / red).
 * - Optional red dots on readings that were flagged as bad.
 */

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { DotItemDotProps } from 'recharts/types/util/types'

import { fmtTick, fmtUtc } from '../lib/format'

export interface ChartLine {
  key: string
  label: string
  colour: string
  /** Draw against the right-hand axis (for a second unit, e.g. SNR next to RSSI). */
  right?: boolean
  /** Own data for this line (used when each node has its own timestamps). */
  data?: ChartRow[]
}

export type ChartRow = { t: number; flagged?: boolean } & Record<string, number | null | boolean | undefined>

interface Props {
  data: ChartRow[]
  lines: ChartLine[]
  fromMs: number
  toMs: number
  unit?: string
  rightUnit?: string
  decimals?: number
  warning?: number | null
  critical?: number | null
  markFlagged?: boolean
  height?: number
}

const AXIS = { stroke: '#334155', tick: { fill: '#94a3b8', fontSize: 11 } }

export function TimeSeriesChart({
  data,
  lines,
  fromMs,
  toMs,
  unit = '',
  rightUnit = '',
  decimals = 2,
  warning,
  critical,
  markFlagged = false,
  height = 200,
}: Props) {
  const span = toMs - fromMs
  const hasRight = lines.some((l) => l.right)
  const unitSuffix = (u: string) => (u === '°' ? '°' : u ? ` ${u}` : '')

  return (
    <div>
      {/* Legend */}
      <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        {lines.map((l, i) => (
          <span key={`${l.key}-${i}`} className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-3 rounded" style={{ background: l.colour }} />
            {l.label}
          </span>
        ))}
        {warning != null && (
          <span className="inline-flex items-center gap-1.5">
            <span className="w-3 border-t border-dashed border-warn" /> warning
          </span>
        )}
        {critical != null && (
          <span className="inline-flex items-center gap-1.5">
            <span className="w-3 border-t border-dashed border-crit" /> critical
          </span>
        )}
      </div>

      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 4, right: hasRight ? 0 : 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="t"
            type="number"
            scale="time"
            domain={[fromMs, toMs]}
            tickFormatter={(v: number) => fmtTick(v, span)}
            minTickGap={40}
            {...AXIS}
          />
          <YAxis
            yAxisId="left"
            width={58}
            domain={['auto', 'auto']}
            tickFormatter={(v: number) => `${Number(v.toFixed(decimals))}`}
            {...AXIS}
          />
          {hasRight && (
            <YAxis
              yAxisId="right"
              orientation="right"
              width={44}
              domain={['auto', 'auto']}
              tickFormatter={(v: number) => `${Number(v.toFixed(1))}`}
              {...AXIS}
            />
          )}
          <Tooltip
            contentStyle={{ background: '#121b2e', border: '1px solid #1e293b', borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: '#94a3b8', marginBottom: 4 }}
            labelFormatter={(v) => fmtUtc(new Date(Number(v)).toISOString())}
            formatter={(value, name, item) => {
              const line = lines.find((l) => l.key === item.dataKey && (!l.data || l.label === name))
              const u = line?.right ? rightUnit : unit
              const v = typeof value === 'number' ? `${value.toFixed(decimals)}${unitSuffix(u)}` : String(value)
              return [v, line?.label ?? String(name)]
            }}
          />
          {warning != null && (
            <ReferenceLine yAxisId="left" y={warning} stroke="#f59e0b" strokeDasharray="5 4" ifOverflow="extendDomain" />
          )}
          {critical != null && (
            <ReferenceLine yAxisId="left" y={critical} stroke="#ef4444" strokeDasharray="5 4" ifOverflow="extendDomain" />
          )}
          {lines.map((l, i) => (
            <Line
              key={`${l.key}-${i}`}
              yAxisId={l.right ? 'right' : 'left'}
              data={l.data}
              dataKey={l.key}
              name={l.label}
              stroke={l.colour}
              strokeWidth={1.6}
              connectNulls={false}
              isAnimationActive={false}
              dot={
                markFlagged
                  ? (props: DotItemDotProps) =>
                      (props.payload as ChartRow | undefined)?.flagged && props.cy != null ? (
                        <circle key={props.index} cx={props.cx} cy={props.cy} r={3.5} fill="#ef4444" stroke="none" />
                      ) : (
                        <g key={props.index} />
                      )
                  : false
              }
              activeDot={{ r: 3 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
