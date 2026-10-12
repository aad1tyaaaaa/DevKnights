// When the dashboard and API live on different sites (e.g. Vercel + Render), the browser treats the
// API's session cookie as third-party and blocks it, which breaks GitHub sign-in. Setting
// PROVENYX_API_PROXY_URL proxies /api/* and /health through this app instead, so the cookie is
// first-party; pair it with NEXT_PUBLIC_PROVENYX_API_URL=/ so the browser calls the same origin.
const apiProxy = process.env.PROVENYX_API_PROXY_URL?.replace(/\/+$/, '')

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true,
  },
  async rewrites() {
    if (!apiProxy) return []
    return [
      { source: '/api/:path*', destination: `${apiProxy}/api/:path*` },
      { source: '/health', destination: `${apiProxy}/health` },
    ]
  },
}

export default nextConfig
