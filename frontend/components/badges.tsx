import type { Confidence, ScanStatus, Severity } from '@/lib/types'
import { cn } from '@/lib/utils'

const SEVERITY_STYLE: Record<Severity, string> = {
  high: 'bg-[#ff6b57]/15 text-danger',
  medium: 'bg-[#f5b942]/15 text-warn',
  low: 'bg-[#6ea8ff]/15 text-note',
  info: 'bg-ink/10 text-ink/70',
}

export const SEVERITY_ORDER: Severity[] = ['high', 'medium', 'low', 'info']

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize', SEVERITY_STYLE[severity] ?? SEVERITY_STYLE.info)}>
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {severity}
    </span>
  )
}

export function ConfidenceLabel({ confidence }: { confidence: Confidence }) {
  return <span className="text-xs text-ink-muted">{confidence[0].toUpperCase() + confidence.slice(1)} confidence</span>
}

const STATUS_STYLE: Record<ScanStatus, string> = {
  accepted: 'bg-ink/10 text-ink/70',
  analyzing: 'bg-[#6ea8ff]/15 text-note',
  complete: 'bg-mint-soft text-ok',
  failed: 'bg-[#ff6b57]/15 text-danger',
}

export function ScanStatusBadge({ status }: { status: ScanStatus }) {
  return <span className={cn('inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize', STATUS_STYLE[status])}>{status}</span>
}
