/** App shell: left sidebar, top bar (LIVE indicator + UTC clock) and the page. */

import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router'

import { useDashboardSummary, useMe } from '../api/queries'
import type { Alert } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { fmtUtc } from '../lib/format'
import { AlertIcon, CloseIcon, DashboardIcon, DevicesIcon, LogoMark, LogoutIcon, MapIcon, ResultsIcon } from './Icons'

const NAV = [
  { to: '/', label: 'Dashboard', icon: DashboardIcon, end: true },
  { to: '/devices', label: 'Devices', icon: DevicesIcon, end: false },
  { to: '/results', label: 'Results', icon: ResultsIcon, end: false },
  { to: '/map', label: 'Map', icon: MapIcon, end: false },
  { to: '/alerts', label: 'Alerts', icon: AlertIcon, end: false },
]

function Sidebar({ newAlerts }: { newAlerts: number }) {
  const { logout } = useAuth()
  const me = useMe()
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-line bg-panel">
      <Link to="/" className="flex items-center gap-2.5 px-5 py-5">
        <LogoMark />
        <div>
          <div className="text-sm font-bold tracking-tight text-white">Slope Monitor</div>
          <div className="text-[0.65rem] uppercase tracking-widest text-muted">LoRa sensor network</div>
        </div>
      </Link>

      <nav className="flex-1 space-y-0.5 px-3" aria-label="Main">
        {NAV.map(({ to, label, icon: NavIcon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                isActive ? 'bg-panel-2 font-semibold text-white' : 'text-muted hover:bg-panel-2 hover:text-white'
              }`
            }
          >
            <NavIcon />
            <span className="flex-1">{label}</span>
            {to === '/alerts' && newAlerts > 0 && (
              <span className="num rounded-full bg-crit px-1.5 text-[0.7rem] font-bold text-white">{newAlerts}</span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-line p-4">
        <div className="mb-3 min-w-0">
          <div className="truncate text-sm font-semibold text-slate-100">{me.data?.name ?? '…'}</div>
          <div className="truncate text-xs text-muted">
            {me.data?.email} {me.data && <span className="uppercase">· {me.data.role}</span>}
          </div>
        </div>
        <button
          type="button"
          onClick={logout}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-line px-3 py-1.5 text-sm text-muted hover:border-slate-600 hover:text-white"
        >
          <LogoutIcon width={16} height={16} /> Log out
        </button>
      </div>
    </aside>
  )
}

function UtcClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])
  return <span className="num text-sm text-slate-300">{fmtUtc(now.toISOString())}</span>
}

/** Green pulsing "LIVE" when the last poll succeeded recently; red if polling fails. */
function LiveIndicator({ ok, updatedAt }: { ok: boolean; updatedAt: number }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])
  const fresh = ok && updatedAt > 0 && now - updatedAt < 15_000
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-bold tracking-widest ${
        fresh ? 'border-ok/30 bg-ok/10 text-ok' : 'border-crit/40 bg-crit/10 text-crit'
      }`}
      title={fresh ? 'Data is updating every 5 seconds' : 'Not receiving updates from the server'}
    >
      <span className={`h-2 w-2 rounded-full ${fresh ? 'live-dot bg-ok' : 'bg-crit'}`} />
      {fresh ? 'LIVE' : 'NO CONNECTION'}
    </span>
  )
}

/** Pops up when a new critical alert appears while the app is open. */
function CriticalToasts({ alerts }: { alerts: Alert[] | undefined }) {
  const seen = useRef<Set<number> | null>(null)
  const [toasts, setToasts] = useState<Alert[]>([])

  useEffect(() => {
    if (!alerts) return
    if (seen.current === null) {
      // First load: remember existing alerts, don't pop them up.
      seen.current = new Set(alerts.map((a) => a.id))
      return
    }
    const fresh = alerts.filter((a) => !seen.current!.has(a.id))
    fresh.forEach((a) => seen.current!.add(a.id))
    const critical = fresh.filter((a) => a.level === 'critical')
    if (critical.length) setToasts((t) => [...critical, ...t].slice(0, 3))
  }, [alerts])

  useEffect(() => {
    if (!toasts.length) return
    const timer = setTimeout(() => setToasts((t) => t.slice(0, -1)), 12_000)
    return () => clearTimeout(timer)
  }, [toasts])

  if (!toasts.length) return null
  return (
    <div className="fixed right-5 bottom-5 z-[2000] w-96 space-y-2" aria-live="assertive">
      {toasts.map((a) => (
        <div key={a.id} className="rounded-xl border border-crit/50 bg-[#2a0f12] p-4 shadow-2xl" role="alert">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-xs font-bold tracking-widest text-crit uppercase">New critical alert</div>
              <div className="mt-1 text-sm font-semibold text-white">{a.node_name}</div>
              <div className="mt-0.5 text-sm text-slate-300">{a.message}</div>
              <Link to="/alerts" className="mt-2 inline-block text-xs font-semibold text-accent hover:underline">
                View alerts →
              </Link>
            </div>
            <button
              type="button"
              aria-label="Dismiss"
              className="text-muted hover:text-white"
              onClick={() => setToasts((t) => t.filter((x) => x.id !== a.id))}
            >
              <CloseIcon width={16} height={16} />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

export function Layout() {
  // The summary poll drives the LIVE indicator, the alert badge and toasts.
  const summary = useDashboardSummary()
  return (
    <div className="flex h-full">
      <Sidebar newAlerts={summary.data?.counts.alerts_new ?? 0} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-line bg-ink/80 px-8 py-3 backdrop-blur">
          <span className="text-xs text-muted">Placeholder site · prototype data from simulator</span>
          <div className="flex items-center gap-4">
            <UtcClock />
            <LiveIndicator ok={!summary.isError} updatedAt={summary.dataUpdatedAt} />
          </div>
        </header>
        <main className="flex-1 overflow-y-auto px-8 py-7">
          <Outlet />
        </main>
      </div>
      <CriticalToasts alerts={summary.data?.active_alerts} />
    </div>
  )
}
