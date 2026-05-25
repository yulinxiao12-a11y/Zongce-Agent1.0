import { mockApi } from './mock'

export const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api'

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    })
    if (!response.ok) {
      const detail = await response.text()
      throw new Error(detail || `HTTP ${response.status}`)
    }
    const payload = (await response.json()) as ApiResponse<T>
    return payload.data
  } catch (error) {
    if (import.meta.env.PROD || import.meta.env.VITE_STATIC_DEMO === 'true') {
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
