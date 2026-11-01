/** Time ranges for charts ("last 6 h", or a custom from/to). */

export type RangeKey = '1h' | '6h' | '24h' | '7d' | 'custom'

export interface TimeRange {
  key: RangeKey
  /** Only for 'custom': ISO timestamps. */
  from?: string
  to?: string
}

export const RANGE_OPTIONS: { key: RangeKey; label: string; hours?: number }[] = [
  { key: '1h', label: '1 h', hours: 1 },
  { key: '6h', label: '6 h', hours: 6 },
  { key: '24h', label: '24 h', hours: 24 },
  { key: '7d', label: '7 days', hours: 24 * 7 },
  { key: 'custom', label: 'Custom' },
]

/** Relative ranges end at "now", so they keep updating (polling). */
export function isLiveRange(range: TimeRange): boolean {
  return range.key !== 'custom'
}

/** Turn a range into concrete from/to ISO timestamps (computed at fetch time). */
export function resolveRange(range: TimeRange): { from: string; to: string } {
  if (range.key === 'custom' && range.from && range.to) {
    return { from: range.from, to: range.to }
  }
  const hours = RANGE_OPTIONS.find((o) => o.key === range.key)?.hours ?? 24
  const to = new Date()
  const from = new Date(to.getTime() - hours * 3600_000)
  return { from: from.toISOString(), to: to.toISOString() }
}

/** Value for an <input type="datetime-local"> showing a UTC time. */
export function toUtcInputValue(iso: string): string {
  return iso.slice(0, 16)
}

/** Parse an <input type="datetime-local"> value, treating it as UTC. */
export function fromUtcInputValue(value: string): string {
  return new Date(`${value}:00Z`).toISOString()
}
