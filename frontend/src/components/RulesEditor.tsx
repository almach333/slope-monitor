/**
 * Alert rule editing (requirement R6: limits can be set and changed, with justification).
 *
 * - NewRulesEditor: draft rules on the New Device page (saved with the node).
 * - RulesManager:   existing rules of a node (Device detail → "Edit alert rules"),
 *                   each change saved with a required reason, plus the change history.
 */

import { useState } from 'react'

import {
  useAlertDefaults,
  useAlertRules,
  useCreateRule,
  useDeleteRule,
  useRuleHistory,
  useUpdateRule,
} from '../api/queries'
import type { AlertRule, Comparator, RuleChange, RuleInput } from '../api/types'
import { fmtField, fmtUtc } from '../lib/format'
import { ALERT_PARAMETERS, fieldLabel, fieldUnit } from '../lib/parameters'
import { PlusIcon } from './Icons'
import { Button, EmptyState, ErrorState, LoadingState, inputClass } from './ui'

const DEFAULT_NOTE =
  "Threshold values are placeholders for the prototype. Site values come from the site's geotechnical engineer / Trigger Action Response Plan."

// ------------------------------------------------------------------ drafts

export interface RuleDraft {
  key: string
  parameter: string
  comparator: Comparator
  /** 'offset' = thresholds relative to the node's baseline (slope angle only). */
  mode: 'absolute' | 'offset'
  warning: string
  critical: string
  consecutive: string
  enabled: boolean
  justification: string
}

let draftCounter = 0
const newKey = () => `draft-${++draftCounter}`

const str = (v: number | null | undefined) => (v === null || v === undefined ? '' : String(v))

export function draftFromRule(rule: Partial<RuleInput>): RuleDraft {
  const offset = rule.warning_offset != null && rule.critical_offset != null
  return {
    key: newKey(),
    parameter: rule.parameter ?? 'tilt_change_total',
    comparator: rule.comparator ?? 'gt',
    mode: offset ? 'offset' : 'absolute',
    warning: str(offset ? rule.warning_offset : rule.warning_threshold),
    critical: str(offset ? rule.critical_offset : rule.critical_threshold),
    consecutive: str(rule.consecutive_readings ?? 3),
    enabled: rule.enabled ?? true,
    justification: rule.justification ?? '',
  }
}

export function draftToInput(d: RuleDraft): RuleInput {
  const w = Number(d.warning)
  const c = Number(d.critical)
  return {
    parameter: d.parameter,
    comparator: d.comparator,
    warning_threshold: d.mode === 'absolute' ? w : null,
    critical_threshold: d.mode === 'absolute' ? c : null,
    warning_offset: d.mode === 'offset' ? w : null,
    critical_offset: d.mode === 'offset' ? c : null,
    consecutive_readings: Number(d.consecutive),
    enabled: d.enabled,
    justification: d.justification.trim(),
  }
}

/** Same checks as the backend, so mistakes show up before saving. */
export function validateDraft(d: RuleDraft, requireJustification = true): string | null {
  if (d.warning.trim() === '' || Number.isNaN(Number(d.warning))) return 'Enter a number for the warning threshold'
  if (d.critical.trim() === '' || Number.isNaN(Number(d.critical))) return 'Enter a number for the critical threshold'
  const w = Number(d.warning)
  const c = Number(d.critical)
  if (d.comparator === 'gt' && !(c > w)) return 'For “greater than” rules, critical must be above warning'
  if (d.comparator === 'lt' && !(c < w)) return 'For “less than” rules, critical must be below warning'
  const k = Number(d.consecutive)
  if (!Number.isInteger(k) || k < 1 || k > 20) return 'Consecutive readings must be a whole number from 1 to 20'
  if (requireJustification && d.justification.trim().length < 10)
    return 'Justification is required (at least 10 characters)'
  return null
}

// ------------------------------------------------------------------ one rule's fields

function RuleFields({
  draft,
  onChange,
  parameterLocked,
  justificationLabel = 'Justification',
  justificationPlaceholder = 'Why this limit? e.g. TARP reference, geotechnical advice',
}: {
  draft: RuleDraft
  onChange: (d: RuleDraft) => void
  parameterLocked?: boolean
  justificationLabel?: string
  justificationPlaceholder?: string
}) {
  const set = (patch: Partial<RuleDraft>) => onChange({ ...draft, ...patch })
  const unit = draft.mode === 'offset' ? '° from baseline' : fieldUnit(draft.parameter)
  const small = `${inputClass} py-1.5`
  return (
    <div className="grid gap-3 md:grid-cols-[auto_1.6fr_0.9fr_1fr_1fr_0.8fr]">
      <label className="flex items-center gap-2 pt-6 text-sm text-slate-300">
        <input
          type="checkbox"
          className="accent-[#2dd4bf]"
          checked={draft.enabled}
          onChange={(e) => set({ enabled: e.target.checked })}
        />
        On
      </label>
      <label className="text-xs text-muted">
        Parameter
        <select
          className={`${small} mt-1`}
          value={draft.parameter}
          disabled={parameterLocked}
          onChange={(e) =>
            set({
              parameter: e.target.value,
              mode: e.target.value === 'slope_angle' ? draft.mode : 'absolute',
            })
          }
        >
          {ALERT_PARAMETERS.map((p) => (
            <option key={p} value={p}>
              {fieldLabel(p)} ({fieldUnit(p)})
            </option>
          ))}
        </select>
        {draft.parameter === 'slope_angle' && (
          <span className="mt-1 flex gap-3 text-[0.7rem]">
            {(['offset', 'absolute'] as const).map((m) => (
              <label key={m} className="inline-flex items-center gap-1">
                <input type="radio" checked={draft.mode === m} onChange={() => set({ mode: m })} />
                {m === 'offset' ? 'baseline +' : 'absolute'}
              </label>
            ))}
          </span>
        )}
      </label>
      <label className="text-xs text-muted">
        Alarm when
        <select
          className={`${small} mt-1`}
          value={draft.comparator}
          onChange={(e) => set({ comparator: e.target.value as Comparator })}
        >
          <option value="gt">above (&gt;)</option>
          <option value="lt">below (&lt;)</option>
        </select>
      </label>
      <label className="text-xs text-warn">
        Warning <span className="text-muted">({unit})</span>
        <input className={`${small} num mt-1`} inputMode="decimal" value={draft.warning} onChange={(e) => set({ warning: e.target.value })} />
      </label>
      <label className="text-xs text-crit">
        Critical <span className="text-muted">({unit})</span>
        <input className={`${small} num mt-1`} inputMode="decimal" value={draft.critical} onChange={(e) => set({ critical: e.target.value })} />
      </label>
      <label className="text-xs text-muted">
        Consecutive
        <input className={`${small} num mt-1`} inputMode="numeric" value={draft.consecutive} onChange={(e) => set({ consecutive: e.target.value })} />
      </label>
      <label className="text-xs text-muted md:col-span-6">
        {justificationLabel} <span className="text-crit">*</span>
        <textarea
          rows={2}
          className={`${small} mt-1`}
          placeholder={justificationPlaceholder}
          value={draft.justification}
          onChange={(e) => set({ justification: e.target.value })}
        />
      </label>
    </div>
  )
}

function PlaceholderNote({ note = DEFAULT_NOTE }: { note?: string }) {
  return (
    <div className="mb-4 rounded-lg border border-warn/30 bg-warn/5 px-3 py-2 text-xs text-warn">
      ⚠ {note} A level fires only after the set number of consecutive valid readings breach it.
    </div>
  )
}

// ------------------------------------------------------------------ New Device

export function NewRulesEditor({ drafts, onChange }: { drafts: RuleDraft[]; onChange: (d: RuleDraft[]) => void }) {
  const defaults = useAlertDefaults()
  return (
    <div>
      <PlaceholderNote note={defaults.data?.note} />
      <div className="space-y-3">
        {drafts.map((d, i) => {
          const error = validateDraft(d)
          return (
            <div key={d.key} className="rounded-lg border border-line bg-panel-2 p-3">
              <RuleFields draft={d} onChange={(nd) => onChange(drafts.map((x, j) => (j === i ? nd : x)))} />
              <div className="mt-2 flex items-center justify-between gap-2">
                <span className="text-xs text-crit">{error}</span>
                <Button variant="ghost" onClick={() => onChange(drafts.filter((_, j) => j !== i))}>
                  Remove
                </Button>
              </div>
            </div>
          )
        })}
      </div>
      <Button
        className="mt-3"
        onClick={() => onChange([...drafts, draftFromRule({ parameter: 'displacement_m', comparator: 'gt', justification: '' })])}
      >
        <PlusIcon width={16} height={16} /> Add rule
      </Button>
    </div>
  )
}

// ------------------------------------------------------------------ existing rules

function describeRule(r: AlertRule): string {
  const sign = r.comparator === 'gt' ? '>' : '<'
  if (r.pending_baseline)
    return `${sign} baseline +${r.warning_offset}° / +${r.critical_offset}° (pending baseline)`
  const offset = r.warning_offset != null ? ` (baseline +${r.warning_offset}° / +${r.critical_offset}°)` : ''
  return `${sign} ${fmtField(r.parameter, r.warning_threshold)} warning · ${fmtField(r.parameter, r.critical_threshold)} critical${offset}`
}

function ExistingRule({ rule, nodeId }: { rule: AlertRule; nodeId: number }) {
  const update = useUpdateRule(nodeId)
  const remove = useDeleteRule(nodeId)
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [draft, setDraft] = useState<RuleDraft>(() => ({ ...draftFromRule(rule), justification: '' }))
  const [deleteReason, setDeleteReason] = useState('')
  const error = validateDraft(draft)

  const save = () => {
    const input = draftToInput(draft)
    update.mutate(
      {
        id: rule.id,
        body: {
          comparator: input.comparator,
          enabled: input.enabled,
          consecutive_readings: input.consecutive_readings,
          ...(draft.mode === 'offset'
            ? { warning_offset: input.warning_offset, critical_offset: input.critical_offset }
            : { warning_threshold: input.warning_threshold, critical_threshold: input.critical_threshold }),
          justification: input.justification,
        },
      },
      { onSuccess: () => setEditing(false) },
    )
  }

  return (
    <div className="rounded-lg border border-line bg-panel-2 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-white">{fieldLabel(rule.parameter)}</span>
            {!rule.enabled && <span className="rounded bg-offline/30 px-1.5 text-[0.65rem] uppercase text-slate-300">off</span>}
          </div>
          <div className="num mt-0.5 text-sm text-slate-300">{describeRule(rule)}</div>
          <div className="mt-0.5 text-xs text-muted">
            {rule.consecutive_readings} consecutive readings · updated {fmtUtc(rule.updated_at, false)}
          </div>
          <div className="mt-1 text-xs text-muted italic">“{rule.justification}”</div>
        </div>
        {!editing && !deleting && (
          <div className="flex gap-2">
            <Button
              onClick={() => {
                setDraft({ ...draftFromRule(rule), justification: '' })
                setEditing(true)
              }}
            >
              Edit
            </Button>
            <Button variant="danger" onClick={() => setDeleting(true)}>
              Delete
            </Button>
          </div>
        )}
      </div>

      {editing && (
        <div className="mt-3 border-t border-line pt-3">
          <RuleFields
            draft={draft}
            onChange={setDraft}
            parameterLocked
            justificationLabel="Reason for this change"
            justificationPlaceholder="Why is this limit being changed? (recorded in the history)"
          />
          {update.isError && <div className="mt-2 text-sm text-crit">{update.error.message}</div>}
          <div className="mt-2 flex items-center justify-end gap-2">
            <span className="mr-auto text-xs text-crit">{error}</span>
            <Button onClick={() => setEditing(false)}>Cancel</Button>
            <Button variant="primary" disabled={!!error || update.isPending} onClick={save}>
              {update.isPending ? 'Saving…' : 'Save change'}
            </Button>
          </div>
        </div>
      )}

      {deleting && (
        <div className="mt-3 border-t border-line pt-3">
          <label className="text-xs text-muted">
            Reason for deleting this rule <span className="text-crit">*</span>
            <textarea rows={2} className={`${inputClass} mt-1`} value={deleteReason} onChange={(e) => setDeleteReason(e.target.value)} />
          </label>
          {remove.isError && <div className="mt-2 text-sm text-crit">{remove.error.message}</div>}
          <div className="mt-2 flex justify-end gap-2">
            <Button onClick={() => setDeleting(false)}>Cancel</Button>
            <Button
              variant="danger"
              disabled={deleteReason.trim().length < 10 || remove.isPending}
              onClick={() => remove.mutate({ id: rule.id, justification: deleteReason.trim() })}
            >
              Delete rule
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

function summariseChange(c: RuleChange): string {
  const v = (c.new_values ?? c.old_values ?? {}) as Record<string, unknown>
  const param = fieldLabel(String(v.parameter ?? ''))
  const fmt = (values: Record<string, unknown> | null) =>
    values ? `${values.warning_threshold ?? '–'} / ${values.critical_threshold ?? '–'}` : ''
  switch (c.action) {
    case 'created':
      return `${param} rule created (${fmt(c.new_values)})`
    case 'deleted':
      return `${param} rule deleted (was ${fmt(c.old_values)})`
    case 'baseline':
      return `${param} thresholds recalculated from baseline: ${fmt(c.old_values)} → ${fmt(c.new_values)}`
    default:
      return `${param}: ${fmt(c.old_values)} → ${fmt(c.new_values)}${
        c.old_values?.enabled !== c.new_values?.enabled ? (c.new_values?.enabled ? ' · enabled' : ' · disabled') : ''
      }`
  }
}

function RuleHistory({ nodeId }: { nodeId: number }) {
  const history = useRuleHistory(nodeId, true)
  if (history.isPending) return <LoadingState />
  if (history.isError) return <ErrorState error={history.error} />
  if (!history.data.length) return <EmptyState title="No changes recorded" />
  return (
    <ol className="space-y-2">
      {history.data.map((c) => (
        <li key={c.id} className="rounded-lg border border-line px-3 py-2 text-sm">
          <div className="flex flex-wrap justify-between gap-2 text-xs text-muted">
            <span className="num">{fmtUtc(c.changed_at)}</span>
            <span>{c.changed_by_name ?? 'System'}</span>
          </div>
          <div className="mt-0.5 text-slate-200">{summariseChange(c)}</div>
          <div className="mt-0.5 text-xs text-muted italic">“{c.justification}”</div>
        </li>
      ))}
    </ol>
  )
}

export function RulesManager({ nodeId }: { nodeId: number }) {
  const rules = useAlertRules(nodeId)
  const create = useCreateRule(nodeId)
  const defaults = useAlertDefaults()
  const [adding, setAdding] = useState<RuleDraft | null>(null)
  const [tab, setTab] = useState<'rules' | 'history'>('rules')
  const addError = adding ? validateDraft(adding) : null

  return (
    <div>
      <div className="mb-4 flex gap-4 border-b border-line text-sm">
        {(['rules', 'history'] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-1 pb-2 ${tab === t ? 'border-accent text-white' : 'border-transparent text-muted hover:text-white'}`}
          >
            {t === 'rules' ? 'Rules' : 'Change history'}
          </button>
        ))}
      </div>

      {tab === 'history' ? (
        <RuleHistory nodeId={nodeId} />
      ) : (
        <>
          <PlaceholderNote note={defaults.data?.note} />
          {rules.isPending ? (
            <LoadingState />
          ) : rules.isError ? (
            <ErrorState error={rules.error} onRetry={() => rules.refetch()} />
          ) : (
            <div className="space-y-3">
              {rules.data.length === 0 && <EmptyState title="No alert rules for this node" />}
              {rules.data.map((r) => (
                <ExistingRule key={`${r.id}-${r.updated_at}`} rule={r} nodeId={nodeId} />
              ))}
            </div>
          )}

          {adding ? (
            <div className="mt-4 rounded-lg border border-accent/40 bg-panel-2 p-3">
              <div className="mb-2 text-sm font-semibold text-white">New rule</div>
              <RuleFields draft={adding} onChange={setAdding} />
              {create.isError && <div className="mt-2 text-sm text-crit">{create.error.message}</div>}
              <div className="mt-2 flex items-center justify-end gap-2">
                <span className="mr-auto text-xs text-crit">{addError}</span>
                <Button onClick={() => setAdding(null)}>Cancel</Button>
                <Button
                  variant="primary"
                  disabled={!!addError || create.isPending}
                  onClick={() => create.mutate(draftToInput(adding), { onSuccess: () => setAdding(null) })}
                >
                  Add rule
                </Button>
              </div>
            </div>
          ) : (
            <Button className="mt-4" onClick={() => setAdding(draftFromRule({ parameter: 'tilt_change_total', comparator: 'gt' }))}>
              <PlusIcon width={16} height={16} /> Add rule
            </Button>
          )}
        </>
      )}
    </div>
  )
}
