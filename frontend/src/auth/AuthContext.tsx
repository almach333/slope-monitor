/**
 * Login state for the whole app.
 *
 * login() posts email + password to the OAuth 2.0 token endpoint and keeps
 * the returned token (see api/client.ts for where it is stored). logout()
 * just forgets the token: tokens are stateless, so there is no server call,
 * and their short expiry limits the risk.
 */

import { useQueryClient } from '@tanstack/react-query'
import { type ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'

import { ApiError, getToken, setToken, setUnauthorizedHandler } from '../api/client'
import type { TokenResponse } from '../api/types'

interface AuthState {
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(getToken())
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const logout = useCallback(() => {
    setToken(null)
    setTokenState(null)
    queryClient.clear() // forget cached data from this session
    navigate('/login', { replace: true })
  }, [navigate, queryClient])

  // Any 401 from the API (e.g. token expired) signs the user out.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setTokenState(null)
      queryClient.clear()
      navigate('/login?expired=1', { replace: true })
    })
  }, [navigate, queryClient])

  const login = useCallback(async (email: string, password: string) => {
    // OAuth2PasswordRequestForm expects form fields "username" and "password".
    const response = await fetch('/api/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: email, password }),
    }).catch(() => {
      throw new ApiError(0, 'Cannot reach the server. Is the backend running?')
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw new ApiError(response.status, body.detail ?? 'Sign-in failed')
    }
    const data = (await response.json()) as TokenResponse
    setToken(data.access_token)
    setTokenState(data.access_token)
  }, [])

  const value = useMemo(() => ({ isAuthenticated: token !== null, login, logout }), [token, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
