import type { Metadata } from 'next'
import { Suspense } from 'react'
import { ScanDetail } from '@/components/scan-detail'
import { LoadingState } from '@/components/states'

export const metadata: Metadata = { title: 'Scan' }

export default async function ScanPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return (
    <Suspense fallback={<LoadingState label="Loading scan…" />}>
      <ScanDetail scanId={decodeURIComponent(id)} />
    </Suspense>
  )
}
