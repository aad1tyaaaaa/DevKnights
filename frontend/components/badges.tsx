import type { Confidence, ScanStatus, Severity } from '@/lib/types'
import { cn } from '@/lib/utils'

const SEVERITY_STYLE: Record<Severity, string> = {
  high: 'bg-[#fff0ed] text-[#b74232]',
  medium: 'bg-[#fff7df] text-[#a36b0c]',
  low: 'bg-[#eef4fb] text-[#3b6390]',
  info: 'bg-[#f1f4f2] text-[#5f7268]',
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
  accepted: 'bg-[#f1f4f2] text-[#5f7268]',
  analyzing: 'bg-[#eef4fb] text-[#3b6390]',
  complete: 'bg-mint-soft text-[#287246]',
  failed: 'bg-[#fff0ed] text-[#b74232]',
}

export function ScanStatusBadge({ status }: { status: ScanStatus }) {
  return <span className={cn('inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize', STATUS_STYLE[status])}>{status}</span>
}
