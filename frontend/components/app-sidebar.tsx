'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { FilePlus2, History, LayoutDashboard, Settings } from 'lucide-react'
import { Logo } from '@/components/logo'
import { cn } from '@/lib/utils'

const NAV = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/scan/new', label: 'New scan', icon: FilePlus2 },
  { href: '/scans', label: 'Scans', icon: History },
  { href: '/settings', label: 'Settings', icon: Settings },
]

function NavLinks({ horizontal = false }: { horizontal?: boolean }) {
  const pathname = usePathname()
  return (
    <nav aria-label="Main" className={cn('flex gap-1', horizontal ? '-mx-1 flex-row overflow-x-auto px-1' : 'flex-col')}>
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`)
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? 'page' : undefined}
            className={cn(
              'flex shrink-0 items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-mint',
              active ? 'bg-sidebar-accent text-white' : 'text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-white',
            )}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </Link>
        )
      })}
    </nav>
  )
}

export function AppSidebar() {
  return (
    <>
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col bg-sidebar p-5 md:flex">
        <Link href="/" aria-label="Provenyx home">
          <Logo light />
        </Link>
        <p className="mt-10 px-3 text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/50">Workspace</p>
        <div className="mt-3">
          <NavLinks />
        </div>
        <p className="mt-auto border-t border-sidebar-border pt-4 text-[11px] leading-5 text-sidebar-foreground/55">
          Local development · v0.1.0
        </p>
      </aside>
      <header className="flex flex-col gap-3 bg-sidebar px-4 py-3 md:hidden">
        <Link href="/" aria-label="Provenyx home">
          <Logo light />
        </Link>
        <NavLinks horizontal />
      </header>
    </>
  )
}
