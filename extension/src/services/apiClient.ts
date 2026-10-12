import * as vscode from 'vscode';
import type { Finding, HealthResponse, Scan, ScanAccepted, ScanRequest } from '../types';

const HEALTH_TIMEOUT_MS = 5_000;
const READ_TIMEOUT_MS = 15_000;
const SCAN_TIMEOUT_MS = 60_000;
export const DEFAULT_API_BASE_URL = 'https://devknights.onrender.com';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    /** True when the API could not be reached at all (not running, wrong URL, or timed out). */
    readonly unreachable = false,
  ) {
    super(message);
  }

  /** The API does not offer this resource (yet): unknown route, unknown scan, or not implemented. */
  get notAvailable(): boolean {
    return this.status === 404 || this.status === 405 || this.status === 501;
  }
}

export function apiBaseUrl(): string {
  const raw = vscode.workspace.getConfiguration('provenyx').get<string>('apiBaseUrl', DEFAULT_API_BASE_URL);
  return raw.replace(/\/+$/, '');
}

async function request<T>(path: string, init: RequestInit, timeoutMs: number): Promise<T> {
  const base = apiBaseUrl();
  const headers = new Headers(init.headers);
  const apiKey = vscode.workspace.getConfiguration('provenyx').get<string>('apiKey', '');
  if (apiKey) headers.set('X-Provenyx-Key', apiKey);
  let res: Response;
  try {
    res = await fetch(base + path, { ...init, headers, signal: AbortSignal.timeout(timeoutMs) });
  } catch (err) {
    const timedOut = err instanceof Error && err.name === 'TimeoutError';
    throw new ApiError(
      timedOut
        ? `The Provenyx API at ${base} did not respond in time.`
        : `Cannot reach the Provenyx API at ${base}. Is the backend running?`,
      undefined,
      true,
    );
  }
  if (!res.ok) {
    // Only surface the server's message, never echo request content.
    let detail = '';
    try {
      const body = (await res.json()) as { detail?: unknown };
      detail = typeof body.detail === 'string' ? body.detail : res.status === 422 ? 'the lockfile failed validation' : '';
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(`Provenyx API returned ${res.status}${detail ? `: ${detail}` : ''}.`, res.status);
  }
  return (await res.json()) as T;
}

/** Returns undefined when the API does not provide the resource yet. */
async function optional<T>(promise: Promise<T>): Promise<T | undefined> {
  try {
    return await promise;
  } catch (err) {
    if (err instanceof ApiError && err.notAvailable) return undefined;
    throw err;
  }
}

export function checkHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health', { method: 'GET' }, HEALTH_TIMEOUT_MS);
}

export function createGitHubBrowserHandoff(accessToken: string, path: string): Promise<{ url: string }> {
  return request<{ url: string }>(
    '/api/github/auth/extension',
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ next: path }),
    },
    READ_TIMEOUT_MS,
  );
}

export function submitScan(body: ScanRequest, accessToken: string): Promise<ScanAccepted> {
  return request<ScanAccepted>(
    '/api/scans',
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    SCAN_TIMEOUT_MS,
  );
}

export function getScan(scanId: string, accessToken: string): Promise<Scan | undefined> {
  return optional(
    request<Scan>(
      `/api/scans/${encodeURIComponent(scanId)}`,
      { method: 'GET', headers: { Authorization: `Bearer ${accessToken}` } },
      READ_TIMEOUT_MS,
    ),
  );
}

export function getFindings(scanId: string, accessToken: string): Promise<Finding[] | undefined> {
  return optional(
    request<Finding[]>(
      `/api/scans/${encodeURIComponent(scanId)}/findings`,
      { method: 'GET', headers: { Authorization: `Bearer ${accessToken}` } },
      READ_TIMEOUT_MS,
    ),
  );
}
