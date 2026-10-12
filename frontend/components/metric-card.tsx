import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

export function MetricCard({
  label,
  value,
  hint,
  icon: Icon,
  share,
  tone = 'default',
}: {
  label: string
  value: React.ReactNode
  hint?: string
  icon?: LucideIcon
  /** 0–1: renders a proportion bar, e.g. direct deps out of all packages. */
  share?: number
  tone?: 'default' | 'warn'
}) {
  const warn = tone === 'warn'
  return (
    <div
      className={cn(
        'relative flex h-full min-w-0 flex-col overflow-hidden rounded-xl border bg-gradient-to-br to-panel p-5 transition-colors sm:p-6',
        warn ? 'border-[#f5b942]/30 from-[#f5b942]/10 hover:border-[#f5b942]/50' : 'border-line from-brand/10 hover:border-[#6b1239] dark:from-brand/45',
      )}
    >
      <div aria-hidden className={cn('absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent to-transparent', warn ? 'via-[#f5b942]/70' : 'via-[#a8325f]')} />
      <div className="flex items-center justify-between gap-3">
        <p className="truncate text-[11px] font-medium uppercase tracking-wider text-ink-muted">{label}</p>
        {Icon && (
          <span className={cn('grid size-9 shrink-0 place-items-center rounded-lg', warn ? 'bg-[#f5b942]/15 text-warn' : 'bg-brand text-[#f1dbe5]')}>
            <Icon className="size-4" aria-hidden />
          </span>
        )}
      </div>
      <p className={cn('mt-5 text-3xl font-semibold leading-none tabular-nums tracking-tight sm:text-4xl', warn ? 'text-warn' : 'text-ink')}>{typeof value === 'number' ? value.toLocaleString() : value}</p>
      {(share !== undefined || hint) && (
        <div className="mt-auto flex flex-col gap-2 pt-5">
          {share !== undefined && (
            <div className="h-1 overflow-hidden rounded-full bg-ink/10" aria-hidden>
              <div className="h-full rounded-full bg-[#a8325f]" style={{ width: `${Math.round(Math.min(1, Math.max(0, share)) * 100)}%` }} />
            </div>
          )}
          {hint && <p className="truncate text-[11px] leading-4 text-ink-muted" title={hint}>{hint}</p>}
        </div>
      )}
    </div>
  )
}
