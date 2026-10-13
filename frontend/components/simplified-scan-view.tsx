'use client'

import { useState } from 'react'
import { AlertCircle, Bot, CheckCircle2, ChevronDown, ChevronUp, Loader2, Sparkles } from 'lucide-react'
import type { SimplifiedScanResponse } from '@/lib/types'
import { apiFetch } from '@/lib/api'
import { cn } from '@/lib/utils'

interface Props {
  scanId: string
  initialSimplified?: SimplifiedScanResponse | null
}

export function SimplifiedScanView({ scanId, initialSimplified }: Props) {
  const [data, setData] = useState<SimplifiedScanResponse | null>(initialSimplified ?? null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isExpanded, setIsExpanded] = useState(true)

  const handleSimplify = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch<SimplifiedScanResponse>(
        `/api/scans/${encodeURIComponent(scanId)}/simplify`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ language: 'English' }),
        },
      )
      if (res.state === 'ok') {
        setData(res.data)
      } else if (res.state === 'error') {
        setError(res.message)
      } else if (res.state === 'unavailable') {
        setError('Simplification service is not available on this API server.')
      }
    } catch (err) {
      setError((err as Error).message || 'Failed to simplify scan')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-panel shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface/50 p-4 sm:px-6">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 items-center justify-center rounded-lg bg-mint-soft text-mint">
            <Sparkles className="size-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-ink">Plain-English Summary (OpenRouter LLM)</h2>
              {data && (
                <span className="rounded-full bg-ink/5 px-2 py-0.5 text-[10px] font-medium text-ink-muted">
                  {data.provider === 'openrouter' ? `OpenRouter · ${data.model}` : 'Deterministic Explanation'}
                </span>
              )}
            </div>
            <p className="text-xs text-ink-muted">
              Technical findings and dependency changes translated into simple, everyday English for developers.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleSimplify}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg bg-ink px-3 py-1.5 text-xs font-medium text-paper transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {loading ? <Loader2 className="size-3.5 animate-spin" /> : <Bot className="size-3.5" />}
            <span>{data ? 'Regenerate' : 'Simplify Now'}</span>
          </button>

          {data && (
            <button
              type="button"
              onClick={() => setIsExpanded(!isExpanded)}
              className="rounded-lg p-1.5 text-ink-muted hover:bg-ink/5 hover:text-ink"
              aria-label={isExpanded ? 'Collapse' : 'Expand'}
            >
              {isExpanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 border-b border-rose-500/20 bg-rose-500/10 p-4 text-xs text-rose-600 dark:text-rose-400">
          <AlertCircle className="size-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading && !data && (
        <div className="flex items-center justify-center gap-2 p-8 text-xs text-ink-muted">
          <Loader2 className="size-4 animate-spin text-mint" />
          <span>Explaining changes in simple English with OpenRouter LLM…</span>
        </div>
      )}

      {!data && !loading && !error && (
        <div className="flex flex-col items-center justify-center p-8 text-center">
          <p className="text-sm font-medium text-ink">Need a simple breakdown of this change?</p>
          <p className="mt-1 max-w-md text-xs text-ink-muted">
            Click <strong>Simplify Now</strong> to have the LLM explain what changed, why it matters, and recommended actions in clear, jargon-free English.
          </p>
        </div>
      )}

      {data && isExpanded && (
        <div className="space-y-4 p-5 sm:p-6">
          <div
            className={cn(
              'rounded-lg border p-4',
              data.risk_level === 'high'
                ? 'border-rose-500/30 bg-rose-500/5'
                : data.risk_level === 'medium'
                  ? 'border-amber-500/30 bg-amber-500/5'
                  : 'border-mint/30 bg-mint-soft/30',
            )}
          >
            <div className="flex items-start gap-2.5">
              <span className="mt-0.5 shrink-0">
                {data.risk_level === 'high' || data.risk_level === 'medium' ? (
                  <AlertCircle
                    className={cn(
                      'size-4',
                      data.risk_level === 'high' ? 'text-rose-500' : 'text-amber-500',
                    )}
                  />
                ) : (
                  <CheckCircle2 className="size-4 text-mint" />
                )}
              </span>
              <div>
                <h3 className="text-sm font-semibold text-ink">{data.headline}</h3>
                <p className="mt-1 text-xs leading-relaxed text-ink/80">{data.summary}</p>
              </div>
            </div>
          </div>

          {data.key_points.length > 0 && (
            <div>
              <h4 className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">Key Points</h4>
              <ul className="mt-2 space-y-1.5 pl-4 text-xs text-ink/80 list-disc">
                {data.key_points.map((point, idx) => (
                  <li key={idx} className="leading-relaxed">{point}</li>
                ))}
              </ul>
            </div>
          )}

          {data.action_items.length > 0 && (
            <div className="rounded-lg bg-surface p-3.5">
              <h4 className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">Recommended Actions</h4>
              <ul className="mt-2 space-y-1 text-xs font-medium text-ink">
                {data.action_items.map((action, idx) => (
                  <li key={idx} className="flex items-center gap-2">
                    <span className="size-1.5 rounded-full bg-mint" />
                    <span>{action}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
