/** Small building blocks shared by every page. */

import type { ButtonHTMLAttributes, ReactNode } from 'react'

import type { AlertLevel, NodeStatus } from '../api/types'

// ------------------------------------------------------------------ layout

export function PageHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string
  title: string
  /** Buttons etc. shown on the right. */
  children?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <div className="eyebrow mb-1">{eyebrow}</div>
        <h1 className="text-3xl font-bold tracking-tight text-white">{title}</h1>
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  )
}

export function Panel({
  title,
  eyebrow,
  actions,
  children,
  className = '',
  bodyClassName = 'p-4',
}: {
  title?: ReactNode
  eyebrow?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <section className={`rounded-xl border border-line bg-panel ${className}`}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
          <div>
            {eyebrow && <div className="eyebrow">{eyebrow}</div>}
            {title && <h2 className="text-sm font-semibold text-white">{title}</h2>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  )
}

export function StatCard({
  label,
  value,
  sub,
  tone = 'default',
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  tone?: 'default' | 'ok' | 'warn' | 'crit' | 'offline'
}) {
  const accent = {
    default: 'text-white',
    ok: 'text-ok',
    warn: 'text-warn',
    crit: 'text-crit',
    offline: 'text-offline',
  }[tone]
  return (
    <div className="rounded-xl border border-line bg-panel px-5 py-4">
      <div className="eyebrow">{label}</div>
      <div className={`num mt-2 text-4xl font-bold ${accent}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
    </div>
  )
}

// ------------------------------------------------------------------ badges

const STATUS_STYLE: Record<NodeStatus, { label: string; cls: string; dot: string }> = {
  ok: { label: 'OK', cls: 'bg-ok/10 text-ok border-ok/30', dot: 'bg-ok' },
  warning: { label: 'Warning', cls: 'bg-warn/10 text-warn border-warn/30', dot: 'bg-warn' },
  critical: { label: 'Critical', cls: 'bg-crit/15 text-crit border-crit/40', dot: 'bg-crit' },
  offline: { label: 'Offline', cls: 'bg-offline/15 text-slate-300 border-offline/40', dot: 'bg-offline' },
}

export function StatusBadge({ status }: { status: NodeStatus }) {
  const s = STATUS_STYLE[status]
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-semibold ${s.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  )
}

export const STATUS_COLOUR: Record<NodeStatus, string> = {
  ok: '#34d399',
  warning: '#f59e0b',
  critical: '#ef4444',
  offline: '#64748b',
}

export function LevelBadge({ level }: { level: AlertLevel }) {
  const cls =
    level === 'critical' ? 'bg-crit/15 text-crit border-crit/40' : 'bg-warn/10 text-warn border-warn/30'
  return (
    <span className={`inline-flex rounded border px-1.5 py-0.5 text-[0.68rem] font-bold uppercase tracking-wider ${cls}`}>
      {level}
    </span>
  )
}

// ------------------------------------------------------------------ buttons

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'

export function Button({
  variant = 'secondary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  const styles: Record<ButtonVariant, string> = {
    primary: 'bg-accent text-slate-950 hover:bg-teal-300 font-semibold',
    secondary: 'border border-line bg-panel-2 text-slate-200 hover:border-slate-600 hover:text-white',
    ghost: 'text-muted hover:text-white hover:bg-panel-2',
    danger: 'border border-crit/40 bg-crit/10 text-crit hover:bg-crit/20',
  }
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}
      {...props}
    />
  )
}

/** Segmented control, e.g. time range or tabs. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { key: T; label: ReactNode }[]
  value: T
  onChange: (key: T) => void
  label: string
}) {
  return (
    <div role="tablist" aria-label={label} className="inline-flex rounded-lg border border-line bg-panel p-0.5">
      {options.map((o) => (
        <button
          key={o.key}
          type="button"
          role="tab"
          aria-selected={value === o.key}
          onClick={() => onChange(o.key)}
          className={`rounded-md px-3 py-1 text-sm transition-colors ${
            value === o.key ? 'bg-panel-2 font-semibold text-white shadow-inner' : 'text-muted hover:text-white'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

// ------------------------------------------------------------------ states

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-12 text-sm text-muted" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-accent" />
      {label}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="py-12 text-center">
      <div className="text-sm font-semibold text-slate-300">{title}</div>
      {children && <div className="mx-auto mt-1 max-w-md text-sm text-muted">{children}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : 'Something went wrong'
  return (
    <div className="rounded-lg border border-crit/30 bg-crit/5 px-4 py-6 text-center" role="alert">
      <div className="text-sm font-semibold text-crit">Couldn’t load this data</div>
      <div className="mt-1 text-sm text-muted">{message}</div>
      {onRetry && (
        <Button className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

/** Label + value row used in metadata lists. */
export function KeyValue({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd className="num text-right text-slate-100">{children}</dd>
    </div>
  )
}

export const inputClass =
  'w-full rounded-lg border border-line bg-ink px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-accent focus:outline-none'
