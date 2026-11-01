/** Sign-in page: product blurb on the left, form on the right. No sign-up (authorised users only). */

import { type FormEvent, useState } from 'react'
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router'

import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { LogoMark } from '../components/Icons'
import { inputClass } from '../components/ui'

const FEATURES = [
  ['Live node status', 'Tilt, slope angle, acceleration and 6 more parameters from every LoRa node, updated every few seconds.'],
  ['Two-level alarms', 'Warning and critical thresholds with debounce, justification and a full change history.'],
  ['Site map & history', 'Node positions on a site map, and historical trends you can compare and export.'],
]

export function LoginPage() {
  const { isAuthenticated, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(
    params.get('expired') ? 'Your session has expired. Please sign in again.' : null,
  )
  const [busy, setBusy] = useState(false)

  if (isAuthenticated) return <Navigate to="/" replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      const from = (location.state as { from?: string } | null)?.from
      navigate(from && from !== '/login' ? from : '/', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setError('Incorrect email or password')
      else setError(err instanceof Error ? err.message : 'Sign-in failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-full lg:grid-cols-2">
      {/* Left: product blurb */}
      <div className="relative hidden flex-col justify-between overflow-hidden border-r border-line bg-panel p-12 lg:flex">
        <svg className="absolute inset-x-0 bottom-0 w-full opacity-30" viewBox="0 0 800 300" preserveAspectRatio="none" aria-hidden="true">
          <path d="M0 300 L0 210 L120 200 L190 150 L300 140 L360 95 L470 90 L540 50 L800 40 L800 300 Z" fill="#12233a" />
          <path d="M0 210 L120 200 L190 150 L300 140 L360 95 L470 90 L540 50 L800 40" fill="none" stroke="#2dd4bf" strokeWidth="2" strokeDasharray="6 6" />
          {[[150, 176], [330, 118], [505, 70], [690, 44]].map(([x, y]) => (
            <circle key={x} cx={x} cy={y} r="6" fill="#2dd4bf" />
          ))}
        </svg>
        <div className="relative flex items-center gap-3">
          <LogoMark />
          <span className="text-lg font-bold text-white">Slope Monitor</span>
        </div>
        <div className="relative max-w-md">
          <div className="eyebrow mb-3">Open-pit slope monitoring</div>
          <h1 className="text-4xl leading-tight font-bold tracking-tight text-white">
            Every sensor node on the slope, in one view.
          </h1>
          <ul className="mt-8 space-y-5">
            {FEATURES.map(([title, text]) => (
              <li key={title} className="flex gap-3">
                <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent" />
                <div>
                  <div className="text-sm font-semibold text-white">{title}</div>
                  <div className="text-sm text-muted">{text}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="relative text-xs text-muted">ENGG4601 thesis prototype · simulated data</div>
      </div>

      {/* Right: sign-in form */}
      <div className="flex items-center justify-center p-8">
        <form onSubmit={submit} className="w-full max-w-sm" noValidate>
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <LogoMark />
            <span className="text-lg font-bold text-white">Slope Monitor</span>
          </div>
          <div className="eyebrow mb-1">Authorised users only</div>
          <h2 className="text-2xl font-bold text-white">Sign in</h2>
          <p className="mt-1 text-sm text-muted">Accounts are created by an administrator.</p>

          {error && (
            <div className="mt-6 rounded-lg border border-crit/40 bg-crit/10 px-3 py-2 text-sm text-crit" role="alert">
              {error}
            </div>
          )}

          <label className="mt-6 block text-sm font-medium text-slate-300" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            required
            className={`${inputClass} mt-1.5`}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          <label className="mt-4 block text-sm font-medium text-slate-300" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            className={`${inputClass} mt-1.5`}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <button
            type="submit"
            disabled={busy || !email || !password}
            className="mt-6 w-full rounded-lg bg-accent py-2.5 text-sm font-semibold text-slate-950 hover:bg-teal-300 disabled:opacity-50"
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>

          {/* Demo credentials are only shown in development mode, never in a production build. */}
          {import.meta.env.DEV && (
            <div className="mt-6 rounded-lg border border-dashed border-line px-3 py-2 text-xs text-muted">
              Dev mode demo login: <span className="num text-slate-300">admin@example.com</span> /{' '}
              <span className="num text-slate-300">slope-demo-2026</span>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
