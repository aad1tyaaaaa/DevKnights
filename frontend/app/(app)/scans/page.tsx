import type { Metadata } from 'next'
import { History } from 'lucide-react'
import { EmptyState, PageHeader } from '@/components/page-header'

export const metadata: Metadata = { title: 'Scans' }

export default function ScansPage() {
  return (
    <div className="flex flex-col gap-8">
      <PageHeader eyebrow="History" title="Scans" description="Scans you start from VS Code will be listed here." />
      <EmptyState icon={<History className="size-5" aria-hidden />} title="Scan history is not available yet">
        The API does not store scans in this release. Persistent scan history is planned for the next phase.
      </EmptyState>
    </div>
  )
}
