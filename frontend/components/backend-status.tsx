'use client'

import { useCallback, useEffect, useState } from 'react'
import { CircleCheck, CircleX, LoaderCircle, RefreshCw } from 'lucide-react'
import { API_BASE_URL } from '@/lib/config'
import { cn } from '@/lib/utils'

type State = { kind: 'loading' } | { kind: 'ok'; version: string } | { kind: 'down' }

export function BackendStatus({ className }: { className?: string }) {
  const [state, setState] = useState<State>({ kind: 'loading' })

  const check = useCallback(async () => {
    setState({ kind: 'loading' })
    try {
      const res = await fetch(`${API_BASE_URL}/health`, { cache: 'no-store', signal: AbortSignal.timeout(5000) })
      const body = await res.json()
      setState(res.ok && body.status === 'ok' ? { kind: 'ok', version: body.version } : { kind: 'down' })
    } catch {
      setState({ kind: 'down' })
    }
  }, [])

  useEffect(() => {
    void check()
  }, [check])

  return (
    <div className={cn('rounded-xl border border-line bg-white p-5', className)} aria-live="polite">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          {state.kind === 'loading' && <LoaderCircle className="mt-0.5 size-5 animate-spin text-ink-muted" aria-hidden />}
          {state.kind === 'ok' && <CircleCheck className="mt-0.5 size-5 text-leaf" aria-hidden />}
          {state.kind === 'down' && <CircleX className="mt-0.5 size-5 text-[#b74232]" aria-hidden />}
          <div>
            <p className="text-sm font-semibold text-ink">
              {state.kind === 'loading' && 'Checking backend…'}
              {state.kind === 'ok' && 'Backend connected'}
              {state.kind === 'down' && 'Backend unreachable'}
            </p>
            <p className="mt-1 text-xs text-ink-muted">
              {state.kind === 'ok' ? `provenyx-api ${state.version} at ${API_BASE_URL}` : API_BASE_URL}
            </p>
            {state.kind === 'down' && (
              <p className="mt-2 text-xs leading-5 text-ink-muted">
                Start it with <code className="rounded bg-surface px-1.5 py-0.5 text-ink">uvicorn app.main:app --port 8000</code> from <code className="rounded bg-surface px-1.5 py-0.5 text-ink">backend/</code>.
              </p>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={() => void check()}
          disabled={state.kind === 'loading'}
          className="rounded-md p-1.5 text-ink-muted transition hover:bg-surface hover:text-ink focus-visible:outline-2 focus-visible:outline-leaf disabled:opacity-40"
          aria-label="Check backend connection again"
        >
          <RefreshCw className="size-4" aria-hidden />
        </button>
      </div>
    </div>
  )
}
