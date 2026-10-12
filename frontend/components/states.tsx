import { CircleAlert, LoaderCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

export function EmptyState({ icon, title, children, className }: { icon: React.ReactNode; title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('flex flex-col items-center rounded-xl border border-dashed border-line bg-panel px-6 py-14 text-center', className)}>
      <span className="grid size-11 place-items-center rounded-xl bg-mint-soft text-leaf">{icon}</span>
      <h2 className="mt-4 font-semibold text-ink">{title}</h2>
      <div className="mt-2 max-w-md text-sm leading-6 text-ink-muted">{children}</div>
    </div>
  )
}

export function ErrorState({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-[#ff6b57]/30 bg-[#ff6b57]/15 p-5">
      <CircleAlert className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden />
      <div className="min-w-0">
        <h2 className="text-sm font-semibold text-danger">{title}</h2>
        <div className="mt-1 text-sm leading-6 text-danger-soft">{children}</div>
        {action && <div className="mt-3">{action}</div>}
      </div>
    </div>
  )
}

export function LoadingState({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-line bg-panel p-5 text-sm text-ink-muted" role="status">
      <LoaderCircle className="size-4 animate-spin" aria-hidden />
      {label}
    </div>
  )
}
