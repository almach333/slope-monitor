/**
 * The one shared fetch helper. Every API call goes through apiFetch(), which:
 *  - adds the "Authorization: Bearer <token>" header,
 *  - turns error responses into an ApiError with the server's message,
 *  - on any 401, clears the token and sends the user back to /login.
 *
 * Token storage: the token lives in memory and is mirrored to sessionStorage,
 * so refreshing the page keeps you signed in but closing the tab signs you out.
 * Trade-off: anything stored in the browser can be read by a script injected
 * into the page (XSS). That is acceptable for this prototype, which loads no
 * third-party scripts; a production system might use httpOnly cookies instead.
 */

const TOKEN_KEY = 'slope-monitor-token'

let token: string | null = sessionStorage.getItem(TOKEN_KEY)
let onUnauthorized: (() => void) | null = null

export function getToken(): string | null {
  return token
}

export function setToken(value: string | null): void {
  token = value
  if (value) sessionStorage.setItem(TOKEN_KEY, value)
  else sessionStorage.removeItem(TOKEN_KEY)
}

/** Called by the auth context so a 401 anywhere logs the user out. */
export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Pull a readable message out of a FastAPI error body. */
async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) {
      // Pydantic validation errors: [{loc: [...], msg: "..."}]
      return body.detail
        .map((d: { loc?: unknown[]; msg?: string }) => {
          const field = d.loc?.filter((p) => p !== 'body').join('.')
          return field ? `${field}: ${d.msg}` : d.msg
        })
        .join('; ')
    }
  } catch {
    // not JSON
  }
  return `Request failed (${response.status})`
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && typeof init.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(path, { ...init, headers })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Is the backend running?')
  }

  if (response.status === 401 && token) {
    setToken(null)
    onUnauthorized?.()
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  return response
}

/** GET/POST/... JSON. Returns the parsed body (or undefined for 204 No Content). */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await request(path, init)
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

/**
 * Download a file (e.g. CSV export). A plain <a href> link can't send the
 * Authorization header (and tokens must never go in URLs), so we fetch the
 * file ourselves and hand it to the browser as a temporary object URL.
 */
export async function apiDownload(path: string, fallbackName: string): Promise<void> {
  const response = await request(path)
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/** Build a query string, skipping empty values. */
export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value))
  }
  const s = search.toString()
  return s ? `?${s}` : ''
}
