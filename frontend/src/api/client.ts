import { mockApi } from './mock'

export const API_BASE = import.meta.env.VITE_API_BASE || ''

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

const REAL_BACKEND_ONLY_PATHS = [
  '/admin/submissions',
  '/submissions',
  '/upload',
  '/analyze',
]

function requiresRealBackend(path: string) {
  const cleanPath = path.split('?')[0]
  return REAL_BACKEND_ONLY_PATHS.some(item => cleanPath === item || cleanPath.startsWith(`${item}/`))
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  headers.set('Accept', 'application/json')
  const requestPath = path.startsWith('/api/') ? path : `/api${path}`
  try {
    const response = await fetch(`${API_BASE}${requestPath}`, {
      ...options,
      headers,
      credentials: options.credentials || 'include',
    })
    if (!response.ok) {
      const detail = await response.text()
      if ((response.status === 404 || response.status === 405) && !requiresRealBackend(path)) {
        return mockApi<T>(path, options)
      }
      throw new Error(detail || `HTTP ${response.status}`)
    }
    const payload = (await response.json()) as ApiResponse<T> | T
    if (payload && typeof payload === 'object' && 'data' in payload) {
      return (payload as ApiResponse<T>).data
    }
    return payload as T
  } catch (error) {
    if (!requiresRealBackend(path) && (import.meta.env.PROD || import.meta.env.VITE_STATIC_DEMO === 'true')) {
      return mockApi<T>(path, options)
    }
    throw error
  }
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: 'POST', body: JSON.stringify(body) })
}

export function patchJson<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
}
