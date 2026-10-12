import type { Metadata } from 'next'
import Link from 'next/link'
import { ArrowRight, History } from 'lucide-react'
import { EmptyState, PageHeader } from '@/components/page-header'
import { fetchApi, type ScanDetail } from '@/lib/api'

export const metadata: Metadata = { title: 'Scans' }
export const dynamic = 'force-dynamic'

export default async function ScansPage() {
  const result = await fetchApi<ScanDetail[]>('/api/scans')
  const scans = result.data ?? []

  return (
    <div className="flex flex-col gap-8">
      <PageHeader eyebrow="History" title="Scans" description="Scans you start from VS Code will be listed here." />
      {result.error ? (
        <section className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-800">
          <h2 className="font-semibold">Scan history unavailable</h2>
          <p className="mt-1">{result.error}</p>
        </section>
      ) : scans.length === 0 ? (
        <EmptyState icon={<History className="size-5" aria-hidden />} title="No scans yet">
          Run Provenyx: Scan Dependencies from VS Code to create the first persisted scan.
        </EmptyState>
      ) : (
        <div className="overflow-hidden rounded-lg border border-line bg-white">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-surface text-xs uppercase text-ink-muted">
                <tr>
                  <th className="px-5 py-3 font-semibold">Project</th>
                  <th className="px-5 py-3 font-semibold">Status</th>
                  <th className="px-5 py-3 font-semibold">Packages</th>
                  <th className="px-5 py-3 font-semibold">Findings</th>
                  <th className="px-5 py-3 font-semibold">Created</th>
                  <th className="px-5 py-3"><span className="sr-only">Open</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {scans.map((scan) => (
                  <tr key={scan.scan_id}>
                    <td className="px-5 py-4 font-medium text-ink">{scan.project_name ?? 'Unnamed project'}</td>
                    <td className="px-5 py-4 capitalize text-ink-muted">{scan.status}</td>
                    <td className="px-5 py-4 tabular-nums text-ink-muted">{scan.summary?.packages ?? '—'}</td>
                    <td className="px-5 py-4 tabular-nums text-ink-muted">{scan.summary?.findings ?? '—'}</td>
                    <td className="px-5 py-4 whitespace-nowrap text-ink-muted">{new Date(scan.created_at).toLocaleString()}</td>
                    <td className="px-5 py-4 text-right">
                      <Link href={`/scans/${scan.scan_id}`} aria-label={`Open ${scan.project_name ?? 'scan'}`} className="inline-flex text-leaf hover:text-forest">
                        <ArrowRight className="size-4" aria-hidden />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
