import Link from 'next/link'
import { ArrowRight, CircleAlert, Code2, Fingerprint, GitBranch, LockKeyhole } from 'lucide-react'
import { Logo } from '@/components/logo'

const PILLARS = [
  {
    icon: GitBranch,
    tone: 'bg-mint-soft text-leaf',
    title: 'Map your dependency tree.',
    body: 'Follow direct and transitive relationships from package-lock.json to see exactly how a package reaches your project.',
  },
  {
    icon: CircleAlert,
    tone: 'bg-[#fff3d8] text-[#a36b0c]',
    title: 'Spot unusual releases.',
    body: 'Explainable rules over public npm metadata highlight release behavior worth a closer look — with the reasoning shown.',
  },
  {
    icon: Fingerprint,
    tone: 'bg-mint-soft text-leaf',
    title: 'Verify release records.',
    body: 'Compare release metadata with blockchain-anchored manifest hashes, while being clear about what a match does and does not prove.',
  },
]

const cta =
  'inline-flex items-center justify-center gap-1.5 rounded-lg px-5 py-3 text-sm font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-leaf'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#f8fbf8] text-ink">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-8">
        <Logo />
        <nav aria-label="Primary" className="flex items-center gap-6 text-sm font-medium text-ink-muted">
          <a href="#how" className="hidden hover:text-ink sm:inline">How it works</a>
          <a href="#safety" className="hidden hover:text-ink sm:inline">Safety</a>
          <Link href="/dashboard" className={`${cta} bg-forest px-4 py-2.5 text-white hover:bg-[#225b3c]`}>
            Open dashboard
          </Link>
        </nav>
      </header>

      <main>
        <section className="relative overflow-hidden px-5 pb-20 pt-20 sm:px-8 sm:pt-28">
          <div className="pointer-events-none absolute left-1/2 top-0 h-[520px] w-[900px] -translate-x-1/2 rounded-full bg-mint/50 blur-3xl" aria-hidden />
          <div className="relative mx-auto max-w-4xl text-center">
            <p className="mx-auto flex w-fit items-center gap-2 rounded-full border border-[#cfe4d3] bg-white/70 px-3 py-1.5 text-[11px] font-semibold text-leaf">
              <Code2 size={13} aria-hidden /> VS Code extension · npm · Early preview
            </p>
            <h1 className="mx-auto mt-7 max-w-3xl text-5xl font-semibold leading-[1.04] tracking-[-.05em] sm:text-7xl">
              Trust every dependency. <span className="text-leaf">Verify every release.</span>
            </h1>
            <p className="mx-auto mt-7 max-w-2xl text-base leading-7 text-ink-muted sm:text-lg">
              Provenyx brings software supply-chain investigation into your editor — analyzing your npm lockfile without installing or
              executing a single package.
            </p>
            <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row">
              <Link href="/dashboard" className={`${cta} bg-forest text-white shadow-lg shadow-forest/10 hover:bg-[#225b3c]`}>
                Get started <ArrowRight size={15} aria-hidden />
              </Link>
              <Link href="/settings#extension" className={`${cta} border border-[#cfe0d3] bg-white text-[#365b48] hover:bg-surface`}>
                Set up the extension
              </Link>
            </div>
          </div>
        </section>

        <section id="how" className="mx-auto grid max-w-6xl gap-10 px-5 py-20 sm:grid-cols-3 sm:px-8">
          {PILLARS.map(({ icon: Icon, tone, title, body }) => (
            <div key={title}>
              <div className={`mb-5 grid size-10 place-items-center rounded-xl ${tone}`}>
                <Icon size={19} aria-hidden />
              </div>
              <h2 className="text-lg font-semibold">{title}</h2>
              <p className="mt-3 text-sm leading-6 text-ink-muted">{body}</p>
            </div>
          ))}
        </section>

        <section id="safety" className="border-y border-[#dfebe2] bg-[#edf7ef] px-5 py-20 sm:px-8">
          <div className="mx-auto max-w-4xl">
            <p className="flex items-center gap-2 text-sm font-semibold text-[#287246]">
              <LockKeyhole size={16} aria-hidden /> Safe by design
            </p>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight">Understand risk without running untrusted code.</h2>
            <ul className="mt-5 grid gap-3 text-sm leading-6 text-[#4f6e5d] sm:grid-cols-2">
              <li>Never runs <code>npm install</code> or lifecycle scripts in your project.</li>
              <li>Sends your lockfile only after you confirm each scan.</li>
              <li>A missing on-chain record is an evidence gap, not proof of compromise.</li>
              <li>A matching hash confirms integrity of a record, not that a package is safe.</li>
            </ul>
          </div>
        </section>
      </main>

      <footer className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-8 text-xs text-[#8da394] sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <Logo />
        <span>Provenyx Security · v0.1.0 preview</span>
      </footer>
    </div>
  )
}
