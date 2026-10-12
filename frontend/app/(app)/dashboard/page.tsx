import type { Metadata } from 'next'
import Link from 'next/link'
import { ArrowRight, Code2, FileSearch } from 'lucide-react'
import { BackendStatus } from '@/components/backend-status'
import { EmptyState, PageHeader } from '@/components/page-header'

export const metadata: Metadata = { title: 'Dashboard' }

const STEPS = [
  'Install the Provenyx Security extension in VS Code.',
  'Open a project that contains a package-lock.json.',
  'Run “Provenyx: Scan Dependencies” from the Command Palette.',
  'Confirm the prompt to send the lockfile to your Provenyx API.',
]

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Development workspace"
        title="Dashboard"
        description="Investigate dependency trust for your npm projects. Scans are started from VS Code."
      />

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <section className="rounded-xl border border-line bg-white p-6" aria-labelledby="onboarding-title">
          <div className="flex items-start gap-4">
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-forest text-mint">
              <Code2 className="size-5" aria-hidden />
            </span>
            <div>
              <h2 id="onboarding-title" className="font-semibold text-ink">Scan from VS Code</h2>
              <p className="mt-1 text-sm text-ink-muted">Provenyx reads your lockfile. It never installs or runs your packages.</p>
            </div>
          </div>
          <ol className="mt-6 flex flex-col gap-3">
            {STEPS.map((step, i) => (
              <li key={step} className="flex items-start gap-3 text-sm text-ink">
                <span className="grid size-6 shrink-0 place-items-center rounded-full bg-mint-soft text-xs font-semibold text-leaf">{i + 1}</span>
                <span className="pt-0.5">{step}</span>
              </li>
            ))}
          </ol>
          <Link
            href="/settings#extension"
            className="mt-6 inline-flex items-center gap-1.5 rounded-lg bg-forest px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#225b3c] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-leaf"
          >
            Extension setup instructions <ArrowRight className="size-4" aria-hidden />
          </Link>
        </section>

        <BackendStatus />
      </div>

      <EmptyState icon={<FileSearch className="size-5" aria-hidden />} title="No scans to show yet">
        Dependency analysis arrives in a later release. Lockfiles submitted today are validated and acknowledged, but no findings are
        produced or stored.
      </EmptyState>
    </div>
  )
}
