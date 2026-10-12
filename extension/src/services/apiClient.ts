import * as vscode from 'vscode';
import type { HealthResponse, ScanAccepted, ScanRequest } from '../types';

const HEALTH_TIMEOUT_MS = 5_000;
const SCAN_TIMEOUT_MS = 60_000;

export class ApiError extends Error {}

export function apiBaseUrl(): string {
  const raw = vscode.workspace.getConfiguration('provenyx').get<string>('apiBaseUrl', 'http://localhost:8000');
  return raw.replace(/\/+$/, '');
}

async function request<T>(path: string, init: RequestInit, timeoutMs: number): Promise<T> {
  const base = apiBaseUrl();
  let res: Response;
  try {
    res = await fetch(base + path, { ...init, signal: AbortSignal.timeout(timeoutMs) });
  } catch (err) {
    const timedOut = err instanceof Error && err.name === 'TimeoutError';
    throw new ApiError(
      timedOut
        ? `The Provenyx API at ${base} did not respond in time.`
        : `Cannot reach the Provenyx API at ${base}. Is the backend running?`,
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
    throw new ApiError(`Provenyx API returned ${res.status}${detail ? `: ${detail}` : ''}.`);
  }
  return (await res.json()) as T;
}

export function checkHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health', { method: 'GET' }, HEALTH_TIMEOUT_MS);
}

export function submitScan(body: ScanRequest): Promise<ScanAccepted> {
  return request<ScanAccepted>(
    '/api/scans',
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) },
    SCAN_TIMEOUT_MS,
  );
}
