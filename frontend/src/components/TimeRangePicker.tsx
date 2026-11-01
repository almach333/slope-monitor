/** 1 h / 6 h / 24 h / 7 days / Custom selector. Custom times are entered in UTC. */

import { useState } from 'react'

import { RANGE_OPTIONS, type RangeKey, type TimeRange, fromUtcInputValue, resolveRange, toUtcInputValue } from '../lib/time'
import { Button, Segmented, inputClass } from './ui'

export function TimeRangePicker({ value, onChange }: { value: TimeRange; onChange: (r: TimeRange) => void }) {
  const [draft, setDraft] = useState(() => {
    const r = resolveRange(value.key === 'custom' ? value : { key: '24h' })
    return { from: toUtcInputValue(r.from), to: toUtcInputValue(r.to) }
  })

  const select = (key: RangeKey) => {
    if (key === 'custom') onChange({ key, from: fromUtcInputValue(draft.from), to: fromUtcInputValue(draft.to) })
    else onChange({ key })
  }
  const invalid = !draft.from || !draft.to || draft.from >= draft.to

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Segmented
        label="Time range"
        options={RANGE_OPTIONS.map((o) => ({ key: o.key, label: o.label }))}
        value={value.key}
        onChange={select}
      />
      {value.key === 'custom' && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          <input
            type="datetime-local"
            aria-label="From (UTC)"
            className={`${inputClass} w-auto py-1`}
            value={draft.from}
            onChange={(e) => setDraft((d) => ({ ...d, from: e.target.value }))}
          />
          to
          <input
            type="datetime-local"
            aria-label="To (UTC)"
            className={`${inputClass} w-auto py-1`}
            value={draft.to}
            onChange={(e) => setDraft((d) => ({ ...d, to: e.target.value }))}
          />
          <span>UTC</span>
          <Button
            disabled={invalid}
            onClick={() => onChange({ key: 'custom', from: fromUtcInputValue(draft.from), to: fromUtcInputValue(draft.to) })}
          >
            Apply
          </Button>
        </div>
      )}
    </div>
  )
}
