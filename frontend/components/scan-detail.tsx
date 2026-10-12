'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { CircleAlert, GitBranch, Info, Network, Package, ShieldCheck } from 'lucide-react'
import { ScanStatusBadge } from '@/components/badges'
import { DependencyGraph } from '@/components/dependency-graph'
import { FindingsTable } from '@/components/findings-table'
import { MetricCard } from '@/components/metric-card'
import { PackageDetailDrawer } from '@/components/package-detail-drawer'
import { PageHeader, secondaryButton } from '@/components/page-header'
import { ScanProgress } from '@/components/scan-progress'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { SEVERITY_ORDER } from '@/components/badges'
import { useApi } from '@/lib/api'
import { formatDate } from '@/lib/format'
import { ROOT_ID, type DependencyGraphData, type Finding, type Scan, type Severity } from '@/lib/types'

const POLL_MS = 2000

const pct = (n: number, total: number) => `${Math.round((n / total) * 100)}%`

export function ScanDetail({ scanId }: { scanId: string }) {
  const enc = encodeURIComponent(scanId)
  const [scanR, reloadScan] = useApi<Scan>(`/api/scans/${enc}`)
  const scan = scanR.state === 'ok' ? scanR.data : null
  const complete = scan?.status === 'complete'

  useEffect(() => {
    if (scan && (scan.status === 'accepted' || scan.status === 'analyzing')) {
      const t = setTimeout(reloadScan, POLL_MS)
      return () => clearTimeout(t)
    }
  }, [scan, reloadScan])

  const header = (
    <PageHeader
      eyebrow="Scan"
      title={scan?.project_name ?? 'Scan details'}
      description={
        <span className="flex flex-wrap items-center gap-2">
          {scan && <ScanStatusBadge status={scan.status} />}
          <span className="break-all font-mono text-xs">{scanId}</span>
          {scan && <span className="text-xs">· {formatDate(scan.created_at)}</span>}
        </span>
      }
      action={<Link href="/scans" className={secondaryButton}>All scans</Link>}
    />
  )

  if (scanR.state === 'loading') return <div className="flex flex-col gap-8">{header}<LoadingState label="Loading scan…" /></div>
  if (scanR.state === 'error') return <div className="flex flex-col gap-8">{header}<ErrorState title="Could not load this scan" action={<button className={secondaryButton} onClick={reloadScan}>Try again</button>}>{scanR.message}</ErrorState></div>
  if (scanR.state === 'unavailable')
    return (
      <div className="flex flex-col gap-8">
        {header}
        <ErrorState title="This scan isn’t available from the API">
          The API has no scan with this ID. It may have been submitted to a different backend, or the backend’s scan database was reset.
        </ErrorState>
      </div>
    )

  return (
    <div className="flex flex-col gap-8">
      {header}
      {scan!.status === 'failed' && <ErrorState title="The scan failed">{scan!.error ?? 'No reason was given by the API.'}</ErrorState>}
      {(scan!.status === 'accepted' || scan!.status === 'analyzing') && <ScanProgress status={scan!.status} />}
      {complete && <CompleteScan scan={scan!} />}
    </div>
  )
}

function CompleteScan({ scan }: { scan: Scan }) {
  const enc = encodeURIComponent(scan.scan_id)
  const [findingsR] = useApi<Finding[]>(`/api/scans/${enc}/findings`)
  const [graphR] = useApi<DependencyGraphData>(`/api/scans/${enc}/graph`)
  const findings = findingsR.state === 'ok' ? findingsR.data : null
  const graph = graphR.state === 'ok' ? graphR.data : null

  const searchParams = useSearchParams()
  const [selectedFinding, setSelectedFinding] = useState<string | null>(searchParams.get('finding'))
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // Open the finding requested in the URL (e.g. from VS Code) once findings load.
  useEffect(() => {
    const f = findings?.find((x) => x.id === searchParams.get('finding'))
    if (f) {
      setSelectedFinding(f.id)
      setSelectedNode(`${f.package}@${f.version}`)
      setDrawerOpen(true)
    }
  }, [findings, searchParams])

  const flagged = useMemo(() => {
    const m = new Map<string, Severity>()
    for (const f of findings ?? []) {
      const id = `${f.package}@${f.version}`
      const prev = m.get(id)
      if (!prev || SEVERITY_ORDER.indexOf(f.severity) < SEVERITY_ORDER.indexOf(prev)) m.set(id, f.severity)
    }
    return m
  }, [findings])
  const keep = useMemo(() => new Set((findings ?? []).flatMap((f) => f.paths.flat())), [findings])

  const activeFinding = findings?.find((f) => f.id === selectedFinding) ?? null
  const highlightPaths = activeFinding?.paths ?? null
  const nodeFindings = useMemo(() => (findings ?? []).filter((f) => `${f.package}@${f.version}` === selectedNode), [findings, selectedNode])
  const closeDrawer = useCallback(() => setDrawerOpen(false), [])

  const warnings = [...new Set([...(scan.warnings ?? []), ...(graph?.warnings ?? [])])]
  const s = scan.summary
  return (
    <>
      <div className="grid grid-cols-2 gap-4 sm:gap-5 lg:grid-cols-4">
        <MetricCard label="Packages" value={s?.packages ?? '—'} icon={Package} hint="Resolved from the lockfile" />
        <MetricCard label="Direct" value={s?.direct ?? '—'} icon={GitBranch} share={s?.packages ? s.direct / s.packages : undefined} hint={s?.packages ? `${pct(s.direct, s.packages)} of packages` : undefined} />
        <MetricCard label="Transitive" value={s?.transitive ?? '—'} icon={Network} share={s?.packages ? s.transitive / s.packages : undefined} hint={s?.packages ? `${pct(s.transitive, s.packages)} of packages` : undefined} />
        <MetricCard label="Findings" value={s?.findings ?? '—'} icon={CircleAlert} tone={s?.findings ? 'warn' : 'default'} hint="Leads to investigate, not verdicts" />
      </div>

      {warnings.length > 0 && (
        <details className="rounded-xl border border-line bg-panel p-5 text-sm">
          <summary className="flex cursor-pointer items-center gap-2 font-semibold text-ink">
            <Info className="size-4 text-leaf" aria-hidden /> Analysis notes ({warnings.length})
          </summary>
          <p className="mt-2 text-xs text-ink-muted">Things the analysis could not determine. Unknown is reported as unknown, never guessed.</p>
          <ul className="mt-3 list-disc pl-5 text-xs leading-5 text-ink-muted">
            {warnings.slice(0, 50).map((w, i) => <li key={i}>{w}</li>)}
          </ul>
          {warnings.length > 50 && <p className="mt-2 text-xs text-ink-muted">and {warnings.length - 50} more</p>}
        </details>
      )}

      {findingsR.state === 'loading' && <LoadingState label="Loading findings…" />}
      {findingsR.state === 'error' && <ErrorState title="Could not load findings">{findingsR.message}</ErrorState>}
      {findingsR.state === 'unavailable' && <EmptyState icon={<ShieldCheck className="size-5" aria-hidden />} title="Findings are not available yet">The connected API does not provide findings for this scan yet.</EmptyState>}
      {findings && findings.length === 0 && (
        <EmptyState icon={<ShieldCheck className="size-5" aria-hidden />} title="No findings reported">
          No detection rule matched this lockfile. That is not a guarantee that every dependency is safe.
        </EmptyState>
      )}
      {findings && findings.length > 0 && (
        <FindingsTable
          findings={findings}
          selectedId={selectedFinding}
          onSelect={(f) => {
            setSelectedFinding(f.id)
            setSelectedNode(`${f.package}@${f.version}`)
            setDrawerOpen(true)
          }}
        />
      )}

      <section className="rounded-xl border border-line bg-panel p-5" aria-labelledby="graph-title">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 id="graph-title" className="font-semibold text-ink">Dependency graph</h2>
            <p className="mt-1 text-xs text-ink-muted">
              {activeFinding ? `Highlighting paths to ${activeFinding.package}@${activeFinding.version}` : selectedNode ? `Highlighting everything that depends on ${selectedNode}` : 'Select a finding or a package to trace how it reaches your project.'}
            </p>
          </div>
          {(selectedNode || selectedFinding) && (
            <button type="button" className={secondaryButton} onClick={() => { setSelectedNode(null); setSelectedFinding(null) }}>Clear selection</button>
          )}
        </div>
        {graphR.state === 'loading' && <LoadingState label="Loading graph…" />}
        {graphR.state === 'error' && <ErrorState title="Could not load the graph">{graphR.message}</ErrorState>}
        {graphR.state === 'unavailable' && <p className="text-sm text-ink-muted">The dependency graph is not available from the connected API yet.</p>}
        {graph && (
          <DependencyGraph
            graph={graph}
            rootLabel={scan.project_name ?? 'project'}
            flagged={flagged}
            keep={keep}
            selectedNode={selectedNode}
            highlightPaths={highlightPaths}
            onSelectNode={(id) => {
              setSelectedFinding(null)
              setSelectedNode(id)
              setDrawerOpen(id !== ROOT_ID)
            }}
          />
        )}
      </section>

      {drawerOpen && selectedNode && (
        <PackageDetailDrawer
          packageId={selectedNode}
          node={graph?.nodes.find((n) => n.id === selectedNode)}
          findings={nodeFindings}
          onClose={closeDrawer}
        />
      )}
    </>
  )
}
