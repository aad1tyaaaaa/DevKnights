import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

/**
 * Adds the API access key to proxied /api requests on the server, so the key never ships in the
 * browser bundle. Set PROVENYX_API_KEY on Vercel to the same value as on Render.
 */
export function proxy(request: NextRequest) {
  const key = process.env.PROVENYX_API_KEY
  if (!key) return NextResponse.next()
  const headers = new Headers(request.headers)
  headers.set('X-Provenyx-Key', key)
  return NextResponse.next({ request: { headers } })
}

export const config = {
  matcher: '/api/:path*',
}
