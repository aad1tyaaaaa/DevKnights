import { Check, LoaderCircle } from 'lucide-react'
import type { ScanStatus } from '@/lib/types'
import { cn } from '@/lib/utils'

const STEPS: { key: ScanStatus; label: string }[] = [
  { key: 'accepted', label: 'Lockfile accepted' },
  { key: 'analyzing', label: 'Analyzing dependencies' },
  { key: 'complete', label: 'Results ready' },
]

export function ScanProgress({ status }: { status: ScanStatus }) {
  const current = STEPS.findIndex((s) => s.key === status)
  return (
    <div className="rounded-xl border border-line bg-panel p-6" role="status" aria-live="polite">
      <ol className="flex flex-col gap-4 sm:flex-row sm:gap-8">
        {STEPS.map((s, i) => {
          const done = i < current
          const active = i === current
          return (
            <li key={s.key} className="flex items-center gap-3 text-sm">
              <span
                className={cn(
                  'grid size-7 place-items-center rounded-full border text-xs font-semibold',
                  done && 'border-brand bg-brand text-white',
                  active && 'border-leaf text-leaf',
                  !done && !active && 'border-line text-ink-muted',
                )}
              >
                {done ? <Check className="size-3.5" aria-hidden /> : active ? <LoaderCircle className="size-3.5 animate-spin" aria-hidden /> : i + 1}
              </span>
              <span className={cn(active ? 'font-semibold text-ink' : 'text-ink-muted')}>{s.label}</span>
            </li>
          )
        })}
      </ol>
      <p className="mt-4 text-xs text-ink-muted">This page refreshes automatically while the scan runs.</p>
    </div>
  )
}
