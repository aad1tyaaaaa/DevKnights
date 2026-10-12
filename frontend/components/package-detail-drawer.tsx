'use client'

import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { ConfidenceLabel, SeverityBadge } from '@/components/badges'
import { VerificationStatus } from '@/components/verification-status'
import { formatDate } from '@/lib/format'
import type { Finding, GraphNode } from '@/lib/types'

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
    <div className="fixed inset-0 z-30 flex justify-end bg-[#173b2e]/20" onClick={onClose}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        className="h-full w-full max-w-lg overflow-y-auto bg-white p-6 shadow-2xl sm:p-7"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <p className="text-[11px] font-semibold uppercase tracking-[.16em] text-ink-muted">Package investigation</p>
          <button ref={closeRef} type="button" onClick={onClose} className="rounded-md p-1.5 text-ink-muted hover:bg-surface hover:text-ink" aria-label="Close">
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
                <span className="text-xs tabular-nums text-ink-muted">Priority {f.priority_score}/100</span>
                <span className="font-mono text-[11px] text-ink-muted">{f.rule_id}</span>
              </div>
              <h3 className="mt-3 font-semibold text-ink">{f.title}</h3>
              <p className="mt-2 text-sm leading-6 text-[#4f6e5d]">{f.explanation}</p>

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
                      <li key={i} className="break-words rounded-lg bg-mint-soft/60 px-3 py-2 text-xs text-[#365b48]">{p.join('  →  ')}</li>
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
                <dt className="text-ink-muted">License</dt><dd className="text-ink">{node.registry.license ?? 'Unknown'}</dd>
                <dt className="text-ink-muted">Published</dt><dd className="text-ink">{formatDate(node.registry.published_at)}</dd>
                {node.registry.deprecated && (<><dt className="text-ink-muted">Deprecated</dt><dd className="text-[#a36b0c]">{node.registry.deprecated}</dd></>)}
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
