import { AppNavbar } from '@/components/app-navbar'
import { AppSidebar } from '@/components/app-sidebar'
import { GitHubAuthProvider, RequireSignIn } from '@/components/github-auth'

export default function AppLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <GitHubAuthProvider>
      <RequireSignIn>
        <div className="min-h-screen bg-surface md:flex">
          <AppSidebar />
          <div className="min-w-0 flex-1">
            <AppNavbar />
            <main className="px-4 py-8 sm:px-8 sm:py-10 lg:px-12">
              <div className="mx-auto max-w-5xl">{children}</div>
            </main>
          </div>
        </div>
      </RequireSignIn>
    </GitHubAuthProvider>
  )
}
