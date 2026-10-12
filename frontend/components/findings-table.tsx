'use client'

import { useMemo, useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { ConfidenceLabel, SEVERITY_ORDER, SeverityBadge } from '@/components/badges'
import type { Finding, Severity } from '@/lib/types'
import { cn } from '@/lib/utils'

export function FindingsTable({ findings, selectedId, onSelect }: { findings: Finding[]; selectedId: string | null; onSelect: (f: Finding) => void }) {
  const [filter, setFilter] = useState<Severity | 'all'>('all')
  const rows = useMemo(
    () =>
      findings
        .filter((f) => filter === 'all' || f.severity === filter)
        .sort((a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)),
    [findings, filter],
  )

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-5">
        <div>
          <h2 className="font-semibold text-ink">Findings</h2>
          <p className="mt-1 text-xs text-ink-muted">Each finding lists the evidence and rule behind it. Signals are leads to investigate, not proof of compromise.</p>
        </div>
        <label className="text-xs text-ink-muted">
          <span className="sr-only">Filter by severity</span>
          <select value={filter} onChange={(e) => setFilter(e.target.value as Severity | 'all')} className="rounded-md border border-line bg-white px-3 py-2 text-xs text-ink">
            <option value="all">All severities</option>
            {SEVERITY_ORDER.map((s) => (
              <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="relative overflow-x-auto">
        <table className="w-full min-w-[680px] text-left text-sm">
          <caption className="sr-only">Findings</caption>
          <thead className="bg-[#fbfdfb] text-[10px] uppercase tracking-wider text-ink-muted">
            <tr>
              <th scope="col" className="px-5 py-3 font-semibold">Package</th>
              <th scope="col" className="px-5 py-3 font-semibold">Severity</th>
              <th scope="col" className="px-5 py-3 font-semibold">Finding</th>
              <th scope="col" className="px-5 py-3 font-semibold">Paths</th>
              <th scope="col" className="px-5 py-3"><span className="sr-only">Details</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((f) => (
              <tr key={f.id} className={cn('cursor-pointer transition-colors hover:bg-[#f8fbf8]', selectedId === f.id && 'bg-mint-soft/60')} onClick={() => onSelect(f)}>
                <td className="px-5 py-4">
                  <p className="font-semibold text-ink">{f.package}</p>
                  <p className="mt-0.5 text-xs text-ink-muted">v{f.version}</p>
                </td>
                <td className="px-5 py-4">
                  <SeverityBadge severity={f.severity} />
                  <div className="mt-1"><ConfidenceLabel confidence={f.confidence} /></div>
                </td>
                <td className="px-5 py-4">
                  <p className="text-ink">{f.title}</p>
                  <p className="mt-0.5 font-mono text-[11px] text-ink-muted">{f.rule_id}</p>
                </td>
                <td className="px-5 py-4 tabular-nums text-ink-muted">{f.paths.length}</td>
                <td className="px-5 py-4">
                  <button type="button" onClick={(e) => { e.stopPropagation(); onSelect(f) }} className="rounded-md p-1 text-ink-muted hover:bg-surface hover:text-ink" aria-label={`Investigate ${f.package}@${f.version}: ${f.title}`}>
                    <ChevronRight className="size-4" aria-hidden />
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={5} className="px-5 py-8 text-center text-sm text-ink-muted">No findings match this filter.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
