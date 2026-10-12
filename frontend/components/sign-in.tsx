'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowLeft, Eye, LoaderCircle, Lock, ShieldCheck } from 'lucide-react'
import { GitHubMark, signInHref, useGitHubAuth, useSignInError } from '@/components/github-auth'
import { ErrorState } from '@/components/states'

const POINTS = [
  { icon: Eye, text: 'Read-only: Provenyx only reads the lockfiles you choose.' },
  { icon: ShieldCheck, text: 'No package or repository code is ever installed or run.' },
  { icon: Lock, text: 'Your GitHub token stays in an encrypted, HTTP-only cookie for 8 hours.' },
]

/** Where to go after sign-in: a same-site path only, so the page cannot be used to redirect elsewhere. */
function safeNext(value: string | null) {
  return value && value.startsWith('/') && !value.startsWith('//') && !value.includes('\\') ? value : '/dashboard'
}

export function SignIn() {
  const router = useRouter()
  const next = safeNext(useSearchParams().get('next'))
  const { result, reload } = useGitHubAuth()
  const [error, dismiss] = useSignInError()
  const signedIn = result.state === 'ok' && result.data.connected

  useEffect(() => {
    if (signedIn) router.replace(next)
  }, [signedIn, next, router])

  return (
    <div className="grid min-h-screen bg-surface lg:grid-cols-2">
      <aside
        className="dark relative hidden flex-col justify-between overflow-hidden p-12 text-white lg:flex"
        style={{ background: 'radial-gradient(ellipse at 30% 20%, #6b1239 0%, #460a26 45%, #12030a 100%)' }}
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-10"
          style={{ backgroundImage: 'radial-gradient(#ffffff 1px, transparent 1px)', backgroundSize: '22px 22px' }}
        />
        <Link href="/" className="relative flex w-fit items-center gap-3" aria-label="Provenyx home">
          <img src="/logo.png" alt="" className="size-12 rounded-xl bg-white p-1" />
          <span className="text-xl font-semibold tracking-tight">provenyx</span>
        </Link>
        <div className="relative max-w-md">
          <h2 className="text-4xl font-light leading-tight tracking-tight">
            Trust every dependency.
            <br />
            Verify every release.
          </h2>
          <p className="mt-5 text-[15px] leading-relaxed text-white/70">
            Map your npm dependency graph, spot unusual releases, and stop risky updates before they merge.
          </p>
        </div>
        <p className="relative text-xs text-white/50">Explainable supply-chain security for npm projects.</p>
      </aside>

      <main className="flex flex-col px-6 py-8 sm:px-12">
        <Link href="/" className="flex w-fit items-center gap-1.5 text-sm text-ink-muted transition-colors hover:text-ink">
          <ArrowLeft className="size-4" aria-hidden /> Back to home
        </Link>
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-10">
          <img src="/logo.png" alt="" className="mb-6 size-14 rounded-2xl bg-white p-1.5 shadow-sm lg:hidden" />
          <h1 className="text-3xl font-semibold tracking-tight text-ink">Sign in to Provenyx</h1>
          <p className="mt-2 text-sm leading-6 text-ink-muted">Use your GitHub account to open the dashboard and scan your repositories.</p>

          <div className="mt-8 space-y-4">
            {error && (
              <ErrorState title="Sign-in didn't complete" action={<button type="button" onClick={dismiss} className="text-xs font-semibold underline">Dismiss</button>}>
                {error}
              </ErrorState>
            )}

            {result.state === 'loading' || signedIn ? (
              <p className="flex items-center gap-3 rounded-xl border border-line bg-panel p-4 text-sm text-ink-muted" role="status">
                <LoaderCircle className="size-4 animate-spin" aria-hidden />
                {signedIn ? 'Signed in. Opening the dashboard…' : 'Checking your session…'}
              </p>
            ) : result.state === 'error' ? (
              <ErrorState
                title="Cannot reach the Provenyx API"
                action={<button type="button" onClick={reload} className="text-xs font-semibold underline">Try again</button>}
              >
                {result.message}
              </ErrorState>
            ) : result.state === 'unavailable' || !result.data.configured ? (
              <div className="rounded-xl border border-dashed border-line bg-panel p-5 text-sm leading-6 text-ink-muted">
                <p className="font-semibold text-ink">GitHub sign-in isn&apos;t set up on this server</p>
                <p className="mt-1">Create a GitHub OAuth App, then add these to <code className="font-mono text-ink">backend/.env</code> and restart the API:</p>
                <pre className="mt-3 overflow-x-auto rounded-lg bg-ink/5 p-3 font-mono text-xs text-ink">
                  {'PROVENYX_GITHUB_CLIENT_ID=…\nPROVENYX_GITHUB_CLIENT_SECRET=…\nPROVENYX_GITHUB_SESSION_SECRET=…'}
                </pre>
                <p className="mt-3">Step-by-step instructions are in <code className="font-mono text-ink">deploy.md</code> (step 4).</p>
              </div>
            ) : (
              <a
                href={signInHref(next)}
                className="flex h-12 w-full items-center justify-center gap-3 rounded-xl bg-[#24292f] text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#32383f] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#a8325f] dark:bg-white dark:text-[#24292f] dark:hover:bg-[#e8e8ea]"
              >
                <GitHubMark className="size-5" /> Continue with GitHub
              </a>
            )}
          </div>

          <ul className="mt-10 space-y-3 border-t border-line pt-6">
            {POINTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex gap-3 text-xs leading-5 text-ink-muted">
                <Icon className="mt-0.5 size-4 shrink-0 text-leaf" aria-hidden />
                {text}
              </li>
            ))}
          </ul>
        </div>
      </main>
    </div>
  )
}
