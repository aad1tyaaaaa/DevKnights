import type { Metadata } from 'next'
import Link from 'next/link'
import { AlertTriangle, ArrowLeft, Box, GitBranch, ShieldCheck } from 'lucide-react'
import { PageHeader } from '@/components/page-header'
import { fetchApi, type Finding, type ScanDetail, type ScanGraph } from '@/lib/api'

export const metadata: Metadata = { title: 'Scan investigation' }
export const dynamic = 'force-dynamic'

export default async function ScanPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const encodedId = encodeURIComponent(id)
  const [scanResult, graphResult, findingsResult] = await Promise.all([
    fetchApi<ScanDetail>(`/api/scans/${encodedId}`),
    fetchApi<ScanGraph>(`/api/scans/${encodedId}/graph`),
    fetchApi<Finding[]>(`/api/scans/${encodedId}/findings`),
  ])

  if (scanResult.error || !scanResult.data) {
    return (
      <div className="flex flex-col gap-6">
        <Link href="/scans" className="inline-flex items-center gap-2 text-sm font-semibold text-leaf"><ArrowLeft className="size-4" /> Scans</Link>
        <section className="rounded-lg border border-red-200 bg-red-50 p-6 text-red-800">
          <h1 className="font-semibold">Scan unavailable</h1>
          <p className="mt-2 text-sm">{scanResult.error ?? 'The API returned no scan data.'}</p>
        </section>
      </div>
    )
  }

  const scan = scanResult.data
  const graph = graphResult.data
  const findings = findingsResult.data ?? []
  const metrics = [
    { label: 'Packages', value: scan.summary?.packages ?? 0, icon: Box },
    { label: 'Direct', value: scan.summary?.direct ?? 0, icon: ShieldCheck },
    { label: 'Edges', value: graph?.edges.length ?? 0, icon: GitBranch },
    { label: 'Findings', value: scan.summary?.findings ?? findings.length, icon: AlertTriangle },
  ]

  return (
    <div className="flex flex-col gap-8">
      <Link href="/scans" className="inline-flex w-fit items-center gap-2 text-sm font-semibold text-leaf hover:text-forest"><ArrowLeft className="size-4" /> Scans</Link>
      <PageHeader eyebrow={`Scan ${scan.status}`} title={scan.project_name ?? 'Unnamed project'} description={`Created ${new Date(scan.created_at).toLocaleString()} · ${scan.scan_id}`} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {metrics.map(({ label, value, icon: Icon }) => (
          <div key={label} className="rounded-lg border border-line bg-white p-4">
            <Icon className="size-4 text-leaf" aria-hidden />
            <p className="mt-4 text-2xl font-semibold tabular-nums text-ink">{value}</p>
            <p className="mt-1 text-xs font-medium uppercase text-ink-muted">{label}</p>
          </div>
        ))}
      </div>

      <section aria-labelledby="findings-title">
        <div className="mb-4 flex items-end justify-between gap-4">
          <div><p className="text-xs font-semibold uppercase text-leaf">Investigation queue</p><h2 id="findings-title" className="mt-1 text-xl font-semibold text-ink">Findings</h2></div>
          <p className="text-xs text-ink-muted">Signals are not proof of compromise.</p>
        </div>
        {findingsResult.error ? <ErrorBand message={findingsResult.error} /> : findings.length === 0 ? (
          <div className="rounded-lg border border-line bg-white p-6 text-sm text-ink-muted">No evidence-backed findings were produced for this scan.</div>
        ) : (
          <div className="flex flex-col divide-y divide-line overflow-hidden rounded-lg border border-line bg-white">
            {findings.map((finding) => (
              <article key={finding.id} className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div><h3 className="font-semibold text-ink">{finding.title}</h3><p className="mt-1 font-mono text-xs text-ink-muted">{finding.package}@{finding.version}</p></div>
                  <div className="flex gap-2 text-xs"><span className="rounded-md bg-mint-soft px-2 py-1 font-semibold uppercase text-leaf">{finding.severity}</span><span className="rounded-md bg-surface px-2 py-1 text-ink-muted">{finding.priority_score}/100</span></div>
                </div>
                <p className="mt-3 text-sm leading-6 text-ink-muted">{finding.explanation}</p>
                {finding.paths.map((path) => <p key={path.join('>')} className="mt-3 overflow-x-auto font-mono text-xs text-forest">{path.join(' → ')}</p>)}
                <details className="mt-4 text-xs text-ink-muted"><summary className="cursor-pointer font-semibold text-ink">Evidence</summary><pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-md bg-surface p-3">{JSON.stringify(finding.evidence, null, 2)}</pre></details>
              </article>
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="packages-title">
        <div className="mb-4"><p className="text-xs font-semibold uppercase text-leaf">Installed snapshot</p><h2 id="packages-title" className="mt-1 text-xl font-semibold text-ink">Packages</h2></div>
        {graphResult.error ? <ErrorBand message={graphResult.error} /> : (
          <div className="overflow-hidden rounded-lg border border-line bg-white"><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-line bg-surface text-xs uppercase text-ink-muted"><tr><th className="px-5 py-3">Package</th><th className="px-5 py-3">Relationship</th><th className="px-5 py-3">Registry</th><th className="px-5 py-3">License</th></tr></thead><tbody className="divide-y divide-line">{graph?.nodes.map((node) => <tr key={node.id}><td className="px-5 py-3 font-mono text-xs text-ink">{node.id}</td><td className="px-5 py-3 text-ink-muted">{node.direct ? 'Direct' : 'Transitive'}</td><td className="px-5 py-3 capitalize text-ink-muted">{node.registry.status}</td><td className="px-5 py-3 text-ink-muted">{node.registry.license ?? 'Unknown'}</td></tr>)}</tbody></table></div></div>
        )}
      </section>
    </div>
  )
}

function ErrorBand({ message }: { message: string }) {
  return <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-800">{message}</div>
}