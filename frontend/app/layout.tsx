import type { Metadata, Viewport } from 'next'
import './globals.css'
import './theme-switch.css'
import { ThemeToggleFilters, themeInitScript } from '@/components/theme-toggle'

export const metadata: Metadata = {
  title: { default: 'Provenyx Security', template: '%s · Provenyx' },
  description: 'Trust Every Dependency. Verify Every Release. Software supply-chain security for npm projects.',
  icons: {
    icon: [
      { url: '/icon.svg', type: 'image/svg+xml' },
      { url: '/icon-32x32.png', sizes: '32x32', type: 'image/png' },
    ],
    apple: '/apple-icon.png',
  },
}

export const viewport: Viewport = {
  colorScheme: 'dark light',
  themeColor: '#000000',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Fredoka:wght@300..700&family=JetBrains+Mono:ital,wght@0,100..800;1,100..800&display=swap"
        />
      </head>
      <body className="antialiased">
        <ThemeToggleFilters />
        {children}
      </body>
    </html>
  )
}
