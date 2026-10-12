export const API_BASE_URL = (process.env.NEXT_PUBLIC_PROVENYX_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '')
/** Shared demo access key (sent as X-Provenyx-Key). It ships in the browser bundle, so it gates an exposed backend, not individual users. */
export const API_KEY = process.env.NEXT_PUBLIC_PROVENYX_API_KEY
