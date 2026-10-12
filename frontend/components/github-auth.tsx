'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { GitFork, LoaderCircle, LogOut, X } from 'lucide-react'
import { type Result, useApi } from '@/lib/api'
import { API_BASE_URL, API_KEY, REQUIRE_SIGN_IN } from '@/lib/config'
import type { GitHubAuthStatus } from '@/lib/types'
import { cn } from '@/lib/utils'

type AuthState = { result: Result<GitHubAuthStatus>; reload: () => void }
const AuthContext = createContext<AuthState | null>(null)

/** One session check shared by everything inside the app layout (guard, sidebar, navbar). */
export function GitHubAuthProvider({ children }: { children: React.ReactNode }) {
  const [result, reload] = useApi<GitHubAuthStatus>('/api/github/auth/status')
  return <AuthContext.Provider value={{ result, reload }}>{children}</AuthContext.Provider>
}

/** Current GitHub session. `configured` is false when the backend has no OAuth app set up. */
export function useGitHubAuth() {
  const shared = useContext(AuthContext)
  // Outside the provider (landing, sign-in page) fetch directly; inside, reuse the shared check.
  const [own, reloadOwn] = useApi<GitHubAuthStatus>(shared ? null : '/api/github/auth/status')
  const result = shared?.result ?? own
  return { result, status: result.state === 'ok' ? result.data : null, reload: shared?.reload ?? reloadOwn }
}

/** Only signed-in users see the app; everyone else is sent to /signin and returned here afterwards. */
export function RequireSignIn({ children }: { children: React.ReactNode }) {
  const { result } = useGitHubAuth()
  const router = useRouter()
  const pathname = usePathname()
  const signedIn = result.state === 'ok' && result.data.connected
  const mustSignIn = REQUIRE_SIGN_IN && result.state !== 'loading' && !signedIn

  useEffect(() => {
    if (mustSignIn) router.replace(`/signin?${new URLSearchParams({ next: pathname })}`)
  }, [mustSignIn, pathname, router])

  if (!REQUIRE_SIGN_IN || signedIn) return children
  return (
    <div className="grid min-h-screen place-items-center bg-surface" role="status">
      <span className="flex items-center gap-3 text-sm text-ink-muted">
        <LoaderCircle className="size-4 animate-spin" aria-hidden />
        {result.state === 'loading' ? 'Checking your session…' : 'Redirecting to sign in…'}
      </span>
    </div>
  )
}

/** Signed-in account and log out, for the bottom of the sidebar. */
export function SidebarAccount({ compact = false }: { compact?: boolean }) {
  const { status } = useGitHubAuth()
  const router = useRouter()
  if (!status?.connected) return null
  const logOut = async () => {
    await signOut()
    router.replace('/signin')
  }
  if (compact) {
    return (
      <button type="button" onClick={logOut} className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-white">
        <LogOut className="size-4" aria-hidden /> Log out
      </button>
    )
  }
  return (
    <div className="border-t border-sidebar-border pt-4">
      <div className="flex items-center gap-3 px-1">
        {status.avatar_url ? (
          <img src={status.avatar_url} alt="" className="size-9 rounded-full ring-2 ring-white/20" />
        ) : (
          <span className="grid size-9 place-items-center rounded-full bg-sidebar-accent"><GitHubMark className="size-5 text-white" /></span>
        )}
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">{status.login}</p>
          <p className="text-[11px] text-sidebar-foreground/60">Signed in with GitHub</p>
        </div>
      </div>
      <button
        type="button"
        onClick={logOut}
        className="mt-3 flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent/60 hover:text-white"
      >
        <LogOut className="size-4" aria-hidden /> Log out
      </button>
    </div>
  )
}

/** A full-page navigation (not fetch): the backend redirects to GitHub and back to `next`. */
export function signInHref(next: string) {
  return `${API_BASE_URL}/api/github/auth/login?${new URLSearchParams({ next })}`
}

export async function signOut() {
  await fetch(`${API_BASE_URL}/api/github/auth/logout`, {
    method: 'POST',
    credentials: 'include',
    headers: API_KEY ? { 'X-Provenyx-Key': API_KEY } : undefined,
  })
}

/** Shows the reason when GitHub sent the user back with an error (e.g. they cancelled). */
export function useSignInError() {
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const reason = params.get('github_error')
    if (!reason && !params.has('connected')) return
    if (reason) setError(reason === 'access_denied' ? 'GitHub sign-in was cancelled.' : `GitHub sign-in failed: ${reason}`)
    // Drop the one-time callback parameters so a reload doesn't repeat the message.
    params.delete('github_error')
    params.delete('connected')
    const query = params.toString()
    window.history.replaceState(null, '', `${window.location.pathname}${query ? `?${query}` : ''}`)
  }, [])
  return [error, () => setError(null)] as const
}

export function GitHubMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden className={className}>
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  )
}

/** Navbar control for the app: the signed-in account with sign out, or a sign-in button. */
export function AccountMenu() {
  const { status, reload } = useGitHubAuth()
  const [error, dismiss] = useSignInError()
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open) return
    const close = (event: KeyboardEvent) => event.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [open])

  return (
    <div className="relative flex items-center gap-3">
      {error && (
        <p role="alert" className="flex max-w-[45vw] items-center gap-2 rounded-md border border-[#ff6b57]/30 bg-[#ff6b57]/15 px-2.5 py-1 text-xs text-danger">
          {error}
          <button type="button" onClick={dismiss} aria-label="Dismiss" className="text-danger/70 hover:text-danger">
            <X className="size-3.5" aria-hidden />
          </button>
        </p>
      )}
      {status?.connected ? (
        <>
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            aria-haspopup="menu"
            className="flex items-center gap-2 rounded-full border border-line py-1 pl-1 pr-3 text-sm font-medium text-ink transition-colors hover:bg-ink/5"
          >
            {status.avatar_url ? (
              <img src={status.avatar_url} alt="" className="size-7 rounded-full" />
            ) : (
              <GitHubMark className="size-5" />
            )}
            <span className="hidden max-w-32 truncate sm:inline">{status.login}</span>
          </button>
          {open && <button type="button" tabIndex={-1} aria-hidden className="fixed inset-0 z-20 cursor-default" onClick={() => setOpen(false)} />}
          {open && (
            <div role="menu" className="absolute right-0 top-full z-30 mt-2 w-56 overflow-hidden rounded-xl border border-line bg-panel shadow-xl">
              <p className="border-b border-line px-4 py-3 text-xs text-ink-muted">
                Signed in with GitHub as <span className="font-semibold text-ink">{status.login}</span>
              </p>
              <Link role="menuitem" href="/github" onClick={() => setOpen(false)} className="flex items-center gap-2 px-4 py-2.5 text-sm text-ink hover:bg-ink/5">
                <GitFork className="size-4" aria-hidden /> GitHub projects
              </Link>
              <button
                role="menuitem"
                type="button"
                onClick={async () => {
                  setOpen(false)
                  await signOut()
                  reload()
                }}
                className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-sm text-ink hover:bg-ink/5"
              >
                <LogOut className="size-4" aria-hidden /> Sign out
              </button>
            </div>
          )}
        </>
      ) : (
        <SignInButton next="/dashboard" configured={status?.configured === true} />
      )}
    </div>
  )
}

/** Without a configured OAuth app, the button opens the sign-in page, which explains the setup. */
export function SignInButton({ next, configured, className }: { next: string; configured: boolean; className?: string }) {
  return (
    <a
      href={configured ? signInHref(next) : `/signin?${new URLSearchParams({ next })}`}
      className={cn(
        'inline-flex items-center gap-2 rounded-lg bg-brand px-3.5 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-hover',
        className,
      )}
    >
      <GitHubMark className="size-4" /> Sign in with GitHub
    </a>
  )
}
