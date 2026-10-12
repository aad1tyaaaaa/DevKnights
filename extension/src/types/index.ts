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

export type ScanStatus = 'accepted' | 'analyzing' | 'complete' | 'failed';

export interface Scan {
  scan_id: string;
  status: ScanStatus;
  created_at: string;
  project_name: string | null;
  error: string | null;
  summary: { packages: number; direct: number; transitive: number; findings: number } | null;
}

export type Severity = 'info' | 'low' | 'medium' | 'high';

export interface Finding {
  id: string;
  rule_id: string;
  package: string;
  version: string;
  severity: Severity;
  confidence: 'low' | 'medium' | 'high';
  title: string;
  explanation: string;
  evidence: { source: string; field: string; value: unknown; observed_at: string | null }[];
  unknowns: string[];
  paths: string[][];
}

export interface FindingsResponse {
  scan_id: string;
  findings: Finding[];
}

export type BackendState = 'unknown' | 'connected' | 'unreachable';

/** `findings` is undefined while not known, e.g. when the API does not provide findings yet. */
export type LastScan =
  | { kind: 'none' }
  | { kind: 'in-progress'; scanId: string; status: ScanStatus; message: string; at: Date }
  | { kind: 'complete'; scan: Scan; findings?: Finding[]; at: Date }
  | { kind: 'failed'; scanId?: string; message: string; at: Date };
