import { cn } from '@/lib/utils'

export function Logo({ light = false, stacked = false, className }: { light?: boolean; stacked?: boolean; className?: string }) {
  return (
    <span
      className={cn(
        'flex items-center font-semibold tracking-tight',
        stacked ? 'flex-col gap-2 text-lg' : 'gap-2.5',
        light ? 'text-white' : 'text-ink',
        className,
      )}
    >
      <img
        src="/logo.png"
        alt=""
        aria-hidden
        className={cn(stacked ? 'size-20 rounded-2xl p-1.5' : 'size-9 rounded-lg p-0.5', light && 'bg-white')}
      />
      <span>provenyx</span>
    </span>
  )
}
