export function PageHeader({ eyebrow, title, description }: { eyebrow: string; title: string; description?: string }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-[.18em] text-leaf">{eyebrow}</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink sm:text-3xl">{title}</h1>
      {description && <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">{description}</p>}
    </div>
  )
}

export function EmptyState({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed border-line bg-white px-6 py-14 text-center">
      <span className="grid size-11 place-items-center rounded-xl bg-mint-soft text-leaf">{icon}</span>
      <h2 className="mt-4 font-semibold text-ink">{title}</h2>
      <div className="mt-2 max-w-md text-sm leading-6 text-ink-muted">{children}</div>
    </div>
  )
}
