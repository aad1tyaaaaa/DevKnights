// Production (Vercel): the dashboard and API live on different sites, so the browser would treat the
// API's session cookie as third-party and block it, breaking GitHub sign-in. Instead this app proxies
// /api/* and /health to the API, and the browser only ever talks to this origin.
//
// PROVENYX_API_PROXY_URL defaults to the Render Blueprint's service URL when building on Vercel;
// set it if your Render service got a different URL. Locally it is unset and the browser calls
// http://localhost:8000 directly.
const apiProxy = (
  process.env.PROVENYX_API_PROXY_URL ?? (process.env.VERCEL ? 'https://provenyx-api.onrender.com' : '')
).replace(/\/+$/, '')

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true,
  },
  // Behind the proxy the browser calls this same origin.
  env: apiProxy ? { NEXT_PUBLIC_PROVENYX_API_URL: '/' } : {},
  async rewrites() {
    if (!apiProxy) return []
    return [
      { source: '/api/:path*', destination: `${apiProxy}/api/:path*` },
      { source: '/health', destination: `${apiProxy}/health` },
    ]
  },
}

export default nextConfig
