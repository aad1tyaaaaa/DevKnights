import { ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Logo({ light = false, className }: { light?: boolean; className?: string }) {
  return (
    <span className={cn('flex items-center gap-2.5 font-semibold tracking-tight', light ? 'text-white' : 'text-ink', className)}>
      <span className={cn('grid size-8 place-items-center rounded-lg', light ? 'bg-mint text-forest' : 'bg-forest text-mint')}>
        <ShieldCheck size={17} strokeWidth={2.4} aria-hidden />
      </span>
      <span>provenyx</span>
    </span>
  )
}
