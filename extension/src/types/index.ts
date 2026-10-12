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

export interface ScanSummary {
  packages: number;
  direct: number;
  transitive: number;
  findings: number;
}

export interface ScanDetail {
  scan_id: string;
  status: ScanStatus;
  created_at: string;
  project_name: string | null;
  summary: ScanSummary | null;
  warnings: string[];
  error: string | null;
}

export interface RegistryMetadata {
  status: 'available' | 'unavailable';
  description: string | null;
  license: string | null;
  deprecated: string | null;
  published_at: string | null;
  dist_integrity: string | null;
  error: string | null;
}

export interface GraphNode {
  id: string;
  name: string;
  version: string;
  direct: boolean;
  lockfile_paths: string[];
  resolved_urls: string[];
  lockfile_integrities: string[];
  registry: RegistryMetadata;
}

export interface GraphEdge {
  from: string;
  to: string;
  type: 'prod' | 'dev' | 'optional' | 'peer';
}

export interface ScanGraph {
  scan_id: string;
  status: ScanStatus;
  nodes: GraphNode[];
  edges: GraphEdge[];
  warnings: string[];
}

export interface VersionChange {
  name: string;
  from_versions: string[];
  to_versions: string[];
}

export interface ScanComparison {
  baseline_scan_id: string;
  current_scan_id: string;
  added_packages: string[];
  removed_packages: string[];
  version_changes: VersionChange[];
  added_edges: GraphEdge[];
}

export interface FindingEvidence {
  source: 'npm-registry' | 'lockfile' | 'registry-contract';
  field: string;
  value: unknown;
  observed_at: string;
}

export interface Finding {
  id: string;
  rule_id: string;
  package: string;
  version: string;
  severity: 'info' | 'low' | 'medium' | 'high';
  confidence: 'low' | 'medium' | 'high';
  priority_score: number;
  title: string;
  explanation: string;
  evidence: FindingEvidence[];
  paths: string[][];
}

export type BackendState = 'unknown' | 'connected' | 'unreachable';

export type LastScan =
  | { kind: 'none' }
  | { kind: 'accepted'; scanId: string; message: string; at: Date }
  | { kind: 'complete'; scanId: string; findingCount: number; at: Date }
  | { kind: 'failed'; message: string; at: Date };
