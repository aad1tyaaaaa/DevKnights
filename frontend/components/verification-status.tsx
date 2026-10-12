'use client'

import { useState } from 'react'
import { CircleCheck, CircleHelp, CircleSlash, Fingerprint, LoaderCircle, TriangleAlert } from 'lucide-react'
import { secondaryButton } from '@/components/page-header'
import { apiPost, type Result } from '@/lib/api'
import { formatDate, shortHash } from '@/lib/format'
import type { VerificationResult, VerificationStatusKind } from '@/lib/types'
import { cn } from '@/lib/utils'

const COPY: Record<VerificationStatusKind, { title: string; body: string; icon: typeof CircleCheck; tone: string }> = {
  match: {
    title: 'Matches the approved record',
    body: 'This release’s metadata equals the manifest that was approved and anchored. This confirms integrity of the record. It is not a verdict that the package is safe.',
    icon: CircleCheck,
    tone: 'border-[#cfe4d3] bg-mint-soft/60 text-[#287246]',
  },
  mismatch: {
    title: 'Differs from the approved record',
    body: 'The current metadata does not match the anchored manifest. Compare the details below and investigate before trusting this release.',
    icon: TriangleAlert,
    tone: 'border-[#f0e4c9] bg-[#fffbf0] text-[#a36b0c]',
  },
  no_record: {
    title: 'No approved record',
    body: 'Nobody has anchored a manifest for this release. This is an evidence gap, not a risk signal. Most packages have no record.',
    icon: CircleSlash,
    tone: 'border-line bg-surface text-[#5f7268]',
  },
  unavailable: {
    title: 'Verification unavailable',
    body: 'The release registry or package metadata could not be reached, so nothing can be concluded.',
    icon: CircleHelp,
    tone: 'border-line bg-surface text-[#5f7268]',
  },
}

export function VerificationStatus({ pkg, version }: { pkg: string; version: string }) {
  const [result, setResult] = useState<Result<VerificationResult> | null>(null)

  async function verify() {
    setResult({ state: 'loading' })
    setResult(await apiPost<VerificationResult>('/api/releases/verify', { package: pkg, version }))
  }

  return (
    <section aria-labelledby="verify-title">
      <div className="flex items-center justify-between gap-3">
        <h3 id="verify-title" className="flex items-center gap-2 font-semibold text-ink">
          <Fingerprint className="size-4 text-leaf" aria-hidden /> Release record
        </h3>
        <button type="button" onClick={() => void verify()} disabled={result?.state === 'loading'} className={secondaryButton}>
          {result?.state === 'loading' && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
          {result ? 'Verify again' : 'Verify release'}
        </button>
      </div>

      <div className="mt-3" aria-live="polite">
        {!result && <p className="text-sm text-ink-muted">Compare this release’s metadata with the blockchain-anchored manifest, if one exists.</p>}
        {result?.state === 'unavailable' && <p className="text-sm text-ink-muted">Release verification is not available from the connected API yet.</p>}
        {result?.state === 'error' && <p className="text-sm text-[#8a4b41]">{result.message}</p>}
        {result?.state === 'ok' && <VerificationDetails v={result.data} />}
      </div>
    </section>
  )
}

export function VerificationDetails({ v }: { v: VerificationResult }) {
  const copy = COPY[v.status] ?? COPY.unavailable
  const Icon = copy.icon
  return (
    <div className="flex flex-col gap-3">
      <div className={cn('flex items-start gap-3 rounded-lg border p-4', copy.tone)}>
        <Icon className="mt-0.5 size-5 shrink-0" aria-hidden />
        <div>
          <p className="text-sm font-semibold">{copy.title}</p>
          <p className="mt-1 text-sm leading-6 text-ink-muted">{v.status === 'unavailable' && v.detail ? v.detail : copy.body}</p>
        </div>
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-xs">
        <Row label="Release ID" value={v.release_id} mono />
        <Row label="Current manifest hash" value={v.manifest_hash ?? 'Could not be computed'} mono={!!v.manifest_hash} />
        <Row label="Anchored hash" value={v.anchored_hash ?? 'No record'} mono={!!v.anchored_hash} />
        <Row label="Anchored at" value={formatDate(v.anchored_at)} />
        <Row
          label="Registry"
          value={v.registry ? `${v.registry.network === 'hardhat-local' ? 'Local Hardhat demo chain' : v.registry.network} (chain ${v.registry.chain_id}) · ${shortHash(v.registry.address)}` : 'Not configured'}
        />
      </dl>
      {v.registry?.network === 'hardhat-local' && (
        <p className="rounded-md bg-[#fff7df] px-3 py-2 text-[11px] text-[#7a5a14]">
          Local development chain: records exist only on this machine and were anchored by the local registry owner.
        </p>
      )}
      {v.manifest && (
        <details className="text-xs">
          <summary className="cursor-pointer font-semibold text-ink">Canonical manifest fields</summary>
          <pre className="mt-2 overflow-x-auto rounded-md bg-surface p-3 text-[11px] text-ink">{JSON.stringify(v.manifest, null, 2)}</pre>
        </details>
      )}
    </div>
  )
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <>
      <dt className="text-ink-muted">{label}</dt>
      <dd className={cn('min-w-0 break-all text-ink', mono && 'font-mono text-[11px]')} title={value}>{value}</dd>
    </>
  )
}
