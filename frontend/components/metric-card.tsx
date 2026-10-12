import { cn } from '@/lib/utils'

export function MetricCard({ label, value, hint, tone = 'default' }: { label: string; value: React.ReactNode; hint?: string; tone?: 'default' | 'warn' }) {
  return (
    <div className={cn('min-w-0 rounded-xl border bg-white p-4 sm:p-5', tone === 'warn' ? 'border-[#f0e4c9]' : 'border-line')}>
      <p className="text-xs text-ink-muted">{label}</p>
      <p className={cn('mt-2 text-2xl font-semibold tabular-nums sm:text-3xl', tone === 'warn' ? 'text-[#a36b0c]' : 'text-ink')}>{value}</p>
      {hint && <p className="mt-1 text-[11px] text-ink-muted">{hint}</p>}
    </div>
  )
}
