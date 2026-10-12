'use client'

import { MetricCard } from '@/components/metric-card'
import { ScanList, useScans } from '@/components/scan-list'

/** Metrics are computed only from scans the API returns; nothing is shown when there is no data. */
export function DashboardOverview() {
  const [result] = useScans()
  const scans = result.state === 'ok' ? result.data.scans : []
  const latest = scans.find((s) => s.status === 'complete' && s.summary)

  return (
    <section aria-labelledby="recent-title" className="flex flex-col gap-4">
      {latest?.summary && (
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          <MetricCard label="Scans listed" value={scans.length} />
          <MetricCard label="Packages in latest scan" value={latest.summary.packages} hint={latest.project_name ?? undefined} />
          <MetricCard label="Direct dependencies" value={latest.summary.direct} hint="Latest completed scan" />
          <MetricCard label="Findings in latest scan" value={latest.summary.findings} tone={latest.summary.findings ? 'warn' : 'default'} hint="Leads to investigate, not verdicts" />
        </div>
      )}
      <h2 id="recent-title" className="font-semibold text-ink">Recent scans</h2>
      <ScanList result={result} limit={5} />
    </section>
  )
}
