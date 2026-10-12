export const API_BASE_URL = (process.env.NEXT_PUBLIC_PROVENYX_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')
/** Shared demo access key (sent as X-Provenyx-Key). It ships in the browser bundle, so it gates an exposed backend, not individual users. */
export const API_KEY = process.env.NEXT_PUBLIC_PROVENYX_API_KEY

/** App pages require a GitHub sign-in. Set NEXT_PUBLIC_PROVENYX_REQUIRE_SIGN_IN=false only for local development without an OAuth app. */
export const REQUIRE_SIGN_IN = process.env.NEXT_PUBLIC_PROVENYX_REQUIRE_SIGN_IN !== 'false'
