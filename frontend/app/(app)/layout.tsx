import { AppSidebar } from '@/components/app-sidebar'

export default function AppLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="min-h-screen bg-surface md:flex">
      <AppSidebar />
      <main className="min-w-0 flex-1 px-4 py-8 sm:px-8 sm:py-10 lg:px-12">
        <div className="mx-auto max-w-5xl">{children}</div>
      </main>
    </div>
  )
}
