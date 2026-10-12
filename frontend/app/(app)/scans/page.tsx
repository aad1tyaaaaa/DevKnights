import type { Metadata } from 'next'
import Link from 'next/link'
import { Plus } from 'lucide-react'
import { PageHeader, primaryButton } from '@/components/page-header'
import { ScanHistory } from '@/components/scan-list'

export const metadata: Metadata = { title: 'Scans' }

export default function ScansPage() {
  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="History"
        title="Scans"
        description="Scans started from VS Code or uploaded here."
        action={<Link href="/scan/new" className={primaryButton}><Plus className="size-4" aria-hidden /> New scan</Link>}
      />
      <ScanHistory />
    </div>
  )
}
