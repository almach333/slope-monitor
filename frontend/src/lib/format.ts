/** Number and time formatting. All times are shown in UTC. */

import { FIELDS } from './parameters'

export const DASH = '—'

export function fmtNumber(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH
  return value.toFixed(decimals)
}

/** A field's value with its unit and sensible decimals, e.g. "1.234°" or "87.0 %". */
export function fmtField(field: string, value: number | null | undefined): string {
  const meta = FIELDS[field]
  if (value === null || value === undefined) return DASH
  if (!meta) return fmtNumber(value)
  const n = value.toFixed(meta.decimals)
  if (!meta.unit) return n
  return meta.unit === '°' ? `${n}°` : `${n} ${meta.unit}`
}

const pad = (n: number) => String(n).padStart(2, '0')

/** "2026-10-27 08:59:10 UTC" */
export function fmtUtc(iso: string | null | undefined, withSeconds = true): string {
  if (!iso) return DASH
  const d = new Date(iso)
  const date = `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`
  const time = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}${withSeconds ? `:${pad(d.getUTCSeconds())}` : ''}`
  return `${date} ${time} UTC`
}

/** Short tick label for chart axes: "08:59" or "10-27 08:59" for long ranges. */
export function fmtTick(ms: number, spanMs: number): string {
  const d = new Date(ms)
  const time = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`
  if (spanMs <= 36 * 3600_000) return time
  return `${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${time}`
}

/** "12 s ago", "5 min ago", "3 h ago", "2 d ago" */
export function fmtAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return 'never'
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000))
  if (s < 60) return `${s} s ago`
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return `${Math.floor(s / 86400)} d ago`
}

export function fmtDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s`
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)} min`
  return `${(seconds / 3600).toFixed(1)} h`
}

/** Format an alert's value/threshold (offline alerts are durations in seconds). */
export function fmtAlertValue(parameter: string, value: number | null): string {
  if (value === null) return DASH
  if (parameter === 'offline') return fmtDuration(value)
  return fmtField(parameter, value)
}

export function fmtCoord(lat: number | null, lon: number | null): string {
  if (lat === null || lon === null) return DASH
  return `${lat.toFixed(6)}, ${lon.toFixed(6)}`
}
