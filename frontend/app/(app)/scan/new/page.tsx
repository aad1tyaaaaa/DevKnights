import type { Metadata } from 'next'
import { PageHeader } from '@/components/page-header'
import { ScanDropzone } from '@/components/scan-dropzone'

export const metadata: Metadata = { title: 'New scan' }

export default function NewScanPage() {
  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="New scan"
        title="Scan a lockfile"
        description="Prefer scanning from VS Code. Uploading here is useful when you only have the lockfile."
      />
      <ScanDropzone />
    </div>
  )
}
