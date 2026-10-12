'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { ChevronRight } from 'lucide-react'
import { NAV } from '@/components/app-sidebar'
import { AccountMenu } from '@/components/github-auth'
import { ThemeToggle } from '@/components/theme-toggle'

export function AppNavbar() {
  const pathname = usePathname()
  const section = NAV.find(({ href }) => pathname === href || pathname.startsWith(`${href}/`))
  const nested = section && pathname !== section.href

  return (
    <header className="sticky top-0 z-20 border-b border-line bg-surface/80 backdrop-blur-md">
      <div className="px-4 sm:px-8 lg:px-12">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-4">
          <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-sm">
            <span className="text-ink-muted">Workspace</span>
            {section && (
              <>
                <ChevronRight className="size-3.5 shrink-0 text-ink-muted" aria-hidden />
                {nested ? (
                  <Link href={section.href} className="text-ink-muted transition-colors hover:text-ink">
                    {section.label}
                  </Link>
                ) : (
                  <span className="truncate font-medium text-ink" aria-current="page">
                    {section.label}
                  </span>
                )}
              </>
            )}
            {nested && (
              <>
                <ChevronRight className="size-3.5 shrink-0 text-ink-muted" aria-hidden />
                <span className="truncate font-medium text-ink" aria-current="page">
                  Details
                </span>
              </>
            )}
          </nav>
          <div className="flex shrink-0 items-center gap-4">
            <AccountMenu />
            <ThemeToggle />
          </div>
        </div>
      </div>
    </header>
  )
}
