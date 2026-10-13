'use client'

import { useEffect, useRef, useState } from 'react'
import { Bot, Globe, Loader2, Sparkles, X } from 'lucide-react'
import { ConfidenceLabel, SeverityBadge } from '@/components/badges'
import { VerificationStatus } from '@/components/verification-status'
import { formatDate } from '@/lib/format'
import { apiFetch } from '@/lib/api'
import type { Finding, GraphNode, SimplifiedFindingResponse } from '@/lib/types'

interface Props {
  packageId: string
  node: GraphNode | undefined
  findings: Finding[]
  onClose: () => void
}

function splitId(id: string) {
  const at = id.lastIndexOf('@')
  return at > 0 ? { name: id.slice(0, at), version: id.slice(at + 1) } : { name: id, version: '' }
}

function FindingSimplificationCard({ finding }: { finding: Finding }) {
  const [data, setData] = useState<SimplifiedFindingResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const simplify = async () => {
    setLoading(true)
    setErr(null)
    try {
      const res = await apiFetch<SimplifiedFindingResponse>(
        `/api/scans/dummy/findings/${encodeURIComponent(finding.id)}/simplify`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ language: 'English' }),
        },
      )
      if (res.state === 'ok') {
        setData(res.data)
      } else if (res.state === 'error') {
        setErr(res.message)
      } else if (res.state === 'unavailable') {
        setErr('Simplification is not available on this API server.')
      }
    } catch (e) {
      setErr((e as Error).message || 'Failed to simplify finding')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mt-4 rounded-lg border border-line bg-surface/70 p-3.5 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2.5">
        <div className="flex items-center gap-1.5 font-medium text-ink">
          <Sparkles className="size-3.5 text-mint" />
          <span>Explain in Simple English</span>
          {data && (
            <span className="text-[10px] text-ink-muted">({data.provider === 'openrouter' ? `OpenRouter · ${data.model}` : 'Deterministic'})</span>
          )}
        </div>
        <button
          type="button"
          onClick={simplify}
          disabled={loading}
          className="flex items-center gap-1 rounded bg-ink px-2.5 py-1 text-[11px] font-medium text-panel hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-leaf disabled:opacity-50"
        >
          {loading ? <Loader2 className="size-3 animate-spin" /> : <Bot className="size-3" />}
          <span>{data ? 'Regenerate' : 'Simplify'}</span>
        </button>
      </div>

      {err && <p className="mt-2 text-rose-500">{err}</p>}

      {loading && !data && (
        <div className="flex items-center gap-2 py-3 text-ink-muted">
          <Loader2 className="size-3.5 animate-spin text-mint" />
          <span>Simplifying finding in plain English with OpenRouter…</span>
        </div>
      )}

      {!data && !loading && !err && (
        <p className="mt-2 text-ink-muted">
          Need a non-technical breakdown? Click Simplify to view this finding in clear, simple English.
        </p>
      )}

      {data && (
        <div className="mt-2.5 space-y-2">
          <div>
            <span className="font-semibold text-ink">What happened: </span>
            <span className="text-ink/80">{data.what_happened}</span>
          </div>
          <div>
            <span className="font-semibold text-ink">Why it matters: </span>
            <span className="text-ink/80">{data.why_it_matters}</span>
          </div>
          <div className="rounded bg-mint-soft/50 p-2">
            <span className="font-semibold text-ink">Recommendation: </span>
            <span className="text-ink/80">{data.recommendation}</span>
          </div>
        </div>
      )}
    </div>
  )
}

export function PackageDetailDrawer({ packageId, node, findings, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const { name, version } = node ?? splitId(packageId)

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-30 flex justify-end bg-black/60" onClick={onClose}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        className="h-full w-full max-w-lg overflow-y-auto bg-panel p-6 shadow-2xl sm:p-7"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <p className="text-[11px] font-semibold uppercase tracking-[.16em] text-ink-muted">Package investigation</p>
          <button ref={closeRef} type="button" onClick={onClose} className="rounded-md p-1.5 text-ink-muted hover:bg-ink/10 hover:text-ink" aria-label="Close">
            <X className="size-5" aria-hidden />
          </button>
        </div>

        <h2 id="drawer-title" className="mt-6 break-all text-2xl font-semibold text-ink">{name}</h2>
        <p className="mt-1 text-sm text-ink-muted">
          {version && `Version ${version}`}
          {node && ` · ${node.direct ? 'Direct' : 'Transitive'}${node.dev ? ' · dev' : ''}`}
        </p>

        {findings.length === 0 ? (
          <p className="mt-6 rounded-lg bg-surface px-4 py-3 text-sm text-ink-muted">No findings were reported for this package in this scan.</p>
        ) : (
          findings.map((f) => (
            <section key={f.id} className="mt-7 border-t border-line pt-6" aria-label={f.title}>
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge severity={f.severity} />
                <ConfidenceLabel confidence={f.confidence} />
                <span className="text-xs tabular-nums text-ink-muted">
                  {f.ranking_source === 'gemini' && f.ai_priority_score != null ? `Gemini ${f.ai_priority_score}/100` : `Priority ${f.priority_score}/100`}
                </span>
                <span className="font-mono text-[11px] text-ink-muted">{f.rule_id}</span>
              </div>
              <h3 className="mt-3 font-semibold text-ink">{f.title}</h3>
              <p className="mt-2 text-sm leading-6 text-ink/70">{f.explanation}</p>

              <FindingSimplificationCard finding={f} />

              {f.ranking_source === 'gemini' && f.ai_priority_score != null && (
                <div className="mt-4 rounded-lg border border-line bg-mint-soft/50 p-3 text-xs text-ink/70">
                  <p className="font-semibold text-ink">Gemini ranking · {f.ai_priority_score}/100</p>
                  <p className="mt-1">Deterministic rule score: {f.priority_score}/100</p>
                  {f.ai_rationale && <p className="mt-2 leading-5">{f.ai_rationale}</p>}
                </div>
              )}

              <h4 className="mt-5 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">Evidence</h4>
              <ul className="mt-2 flex flex-col gap-2">
                {f.evidence.map((e, i) => (
                  <li key={i} className="rounded-lg bg-surface p-3 text-xs">
                    <p className="font-semibold text-ink">{e.source}</p>
                    <p className="mt-1 break-all font-mono text-[11px] text-ink-muted">{e.field}</p>
                    <p className="mt-1 break-all text-ink">{typeof e.value === 'string' ? e.value : JSON.stringify(e.value)}</p>
                    {e.observed_at && <p className="mt-1 text-ink-muted">Observed {formatDate(e.observed_at)}</p>}
                  </li>
                ))}
              </ul>

              {(f.unknowns?.length ?? 0) > 0 && (
                <>
                  <h4 className="mt-5 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">Unknowns</h4>
                  <ul className="mt-2 list-disc pl-5 text-sm text-ink-muted">
                    {f.unknowns!.map((u) => <li key={u}>{u}</li>)}
                  </ul>
                </>
              )}

              {f.paths.length > 0 && (
                <>
                  <h4 className="mt-5 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">Dependency paths ({f.paths.length})</h4>
                  <ul className="mt-2 flex flex-col gap-2">
                    {f.paths.slice(0, 10).map((p, i) => (
                      <li key={i} className="break-words rounded-lg bg-mint-soft/60 px-3 py-2 text-xs text-ink/70">{p.join('  →  ')}</li>
                    ))}
                  </ul>
                  {f.paths.length > 10 && <p className="mt-1 text-xs text-ink-muted">and {f.paths.length - 10} more</p>}
                </>
              )}
            </section>
          ))
        )}

        {node?.registry && (
          <section className="mt-7 border-t border-line pt-6">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">npm registry</h3>
            {node.registry.status === 'unavailable' ? (
              <p className="mt-2 text-sm text-ink-muted">Metadata unavailable{node.registry.error ? `: ${node.registry.error}` : ''}. Treated as unknown.</p>
            ) : (
              <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-xs">
                {node.registry.description && (<><dt className="text-ink-muted">Description</dt><dd className="text-ink">{node.registry.description}</dd></>)}
                <dt className="text-ink-muted">Publisher</dt><dd className="text-ink">{node.registry.publisher ?? 'Unknown'}</dd>
                <dt className="text-ink-muted">License</dt><dd className="text-ink">{node.registry.license ?? 'Unknown'}</dd>
                {node.registry.published_at && (<><dt className="text-ink-muted">Published</dt><dd className="text-ink">{formatDate(node.registry.published_at)}</dd></>)}
                {node.registry.deprecated && (<><dt className="text-ink-muted">Deprecated</dt><dd className="text-warn">{node.registry.deprecated}</dd></>)}
                {node.registry.dist_integrity && (<><dt className="text-ink-muted">Integrity</dt><dd className="break-all font-mono text-[11px] text-ink">{node.registry.dist_integrity}</dd></>)}
              </dl>
            )}
          </section>
        )}

        {node && node.lockfile_paths.length > 0 && (
          <section className="mt-7 border-t border-line pt-6">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ink-muted">Installed at</h3>
            <ul className="mt-2 flex flex-col gap-1 font-mono text-[11px] text-ink">
              {node.lockfile_paths.map((p) => <li key={p} className="break-all">{p}</li>)}
            </ul>
          </section>
        )}

        {version && (
          <div className="mt-7 border-t border-line pt-6">
            <VerificationStatus key={packageId} pkg={name} version={version} />
          </div>
        )}
      </aside>
    </div>
  )
}
