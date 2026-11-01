import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'

import { useAuth } from './AuthContext'

/** Wraps protected pages: anyone not signed in is sent to /login. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()
  const location = useLocation()
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return children
}
