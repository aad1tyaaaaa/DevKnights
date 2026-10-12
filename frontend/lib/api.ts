'use client'

import { useCallback, useEffect, useState } from 'react'
import { API_BASE_URL } from '@/lib/config'

/**
 * `unavailable` means the API does not offer this resource (unknown route, unknown id, or not implemented yet).
 * It is shown as "not available", never as an empty or clean result.
 */
export type Result<T> =
  | { state: 'loading' }
  | { state: 'ok'; data: T }
  | { state: 'unavailable' }
  | { state: 'error'; message: string }

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<Result<T>> {
  let res: Response
  try {
    res = await fetch(API_BASE_URL + path, { ...init, cache: 'no-store', signal: AbortSignal.timeout(15_000) })
  } catch (err) {
    const timedOut = err instanceof Error && err.name === 'TimeoutError'
    return {
      state: 'error',
      message: timedOut ? `The Provenyx API at ${API_BASE_URL} did not respond in time.` : `Cannot reach the Provenyx API at ${API_BASE_URL}.`,
    }
  }
  if (res.status === 404 || res.status === 405 || res.status === 501) return { state: 'unavailable' }
  if (!res.ok) {
    let detail = ''
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : res.status === 422 ? 'the request failed validation' : ''
    } catch {
      /* non-JSON error body */
    }
    return { state: 'error', message: `The API returned ${res.status}${detail ? `: ${detail}` : ''}.` }
  }
  return { state: 'ok', data: (await res.json()) as T }
}

export function apiPost<T>(path: string, body: unknown): Promise<Result<T>> {
  return apiFetch<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}

/** GETs `path` (skipped when null). `reload()` refetches without resetting to loading, which suits polling. */
export function useApi<T>(path: string | null) {
  const [result, setResult] = useState<Result<T>>({ state: 'loading' })
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!path) return
    let cancelled = false
    void apiFetch<T>(path).then((r) => {
      if (!cancelled) setResult(r)
    })
    return () => {
      cancelled = true
    }
  }, [path, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return [result, reload] as const
}
