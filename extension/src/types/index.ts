// Mirrors docs/api-contract.md and backend/app/models/schemas.py. Keep them in sync.

export interface HealthResponse {
  status: 'ok';
  service: string;
  version: string;
}

/** Only the fields Provenyx inspects; everything else in the lockfile is passed through untouched. */
export interface Lockfile {
  name?: string;
  version?: string;
  lockfileVersion: number;
  packages?: Record<string, unknown>;
  dependencies?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ScanRequest {
  lockfile: Lockfile;
  project_name?: string;
  client?: string;
}

export interface ScanAccepted {
  scan_id: string;
  status: 'accepted';
  message: string;
}

export type BackendState = 'unknown' | 'connected' | 'unreachable';

export type LastScan =
  | { kind: 'none' }
  | { kind: 'accepted'; scanId: string; message: string; at: Date }
  | { kind: 'failed'; message: string; at: Date };
