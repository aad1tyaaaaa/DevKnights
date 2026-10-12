'use client'

import Link from 'next/link'
import { ChevronRight, History } from 'lucide-react'
import { ScanStatusBadge } from '@/components/badges'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { useApi, type Result } from '@/lib/api'
import { formatDate } from '@/lib/format'
import type { Scan } from '@/lib/types'

export function useScans() {
  return useApi<{ scans: Scan[] }>('/api/scans')
}

export function ScanHistory({ limit }: { limit?: number }) {
  const [result] = useScans()
  return <ScanList result={result} limit={limit} />
}

/** Renders the shared loading / not-available / error states for the scan list, or the list itself. */
export function ScanList({ result, limit }: { result: Result<{ scans: Scan[] }>; limit?: number }) {
  if (result.state === 'loading') return <LoadingState label="Loading scans…" />
  if (result.state === 'error') return <ErrorState title="Could not load scans">{result.message}</ErrorState>
  if (result.state === 'unavailable')
    return (
      <EmptyState icon={<History className="size-5" aria-hidden />} title="Scan history is not available yet">
        The connected API does not provide scan history yet. Scans you submit are still accepted; history appears here once the backend stores them.
      </EmptyState>
    )

  const scans = limit ? result.data.scans.slice(0, limit) : result.data.scans
  if (scans.length === 0)
    return (
      <EmptyState icon={<History className="size-5" aria-hidden />} title="No scans yet">
        Start one from VS Code with “Provenyx: Scan Dependencies”, or upload a lockfile from <Link className="font-semibold text-leaf underline-offset-2 hover:underline" href="/scan/new">New scan</Link>.
      </EmptyState>
    )

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-white">
      <div className="relative overflow-x-auto">
        <table className="w-full min-w-[600px] text-left text-sm">
          <caption className="sr-only">Scans</caption>
          <thead className="bg-[#fbfdfb] text-[10px] uppercase tracking-wider text-ink-muted">
            <tr>
              <th scope="col" className="px-5 py-3 font-semibold">Project</th>
              <th scope="col" className="px-5 py-3 font-semibold">Status</th>
              <th scope="col" className="px-5 py-3 font-semibold">Packages</th>
              <th scope="col" className="px-5 py-3 font-semibold">Findings</th>
              <th scope="col" className="px-5 py-3 font-semibold">Started</th>
              <th scope="col" className="px-5 py-3"><span className="sr-only">Open</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {scans.map((s) => (
              <tr key={s.scan_id} className="transition-colors hover:bg-[#f8fbf8]">
                <td className="px-5 py-4">
                  <Link href={`/scans/${s.scan_id}`} className="font-semibold text-ink hover:underline focus-visible:outline-2 focus-visible:outline-leaf">
                    {s.project_name ?? 'Unnamed project'}
                  </Link>
                  <p className="mt-0.5 font-mono text-[11px] text-ink-muted">{s.scan_id.slice(0, 8)}</p>
                </td>
                <td className="px-5 py-4"><ScanStatusBadge status={s.status} /></td>
                <td className="px-5 py-4 tabular-nums text-ink-muted">{s.summary?.packages ?? '—'}</td>
                <td className="px-5 py-4 tabular-nums text-ink-muted">{s.summary?.findings ?? '—'}</td>
                <td className="px-5 py-4 text-xs text-ink-muted">{formatDate(s.created_at)}</td>
                <td className="px-5 py-4 text-ink-muted">
                  <Link href={`/scans/${s.scan_id}`} aria-label={`Open scan of ${s.project_name ?? 'unnamed project'}`}>
                    <ChevronRight className="size-4" aria-hidden />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
