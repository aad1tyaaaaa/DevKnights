// Mirrors docs/api-contract.md. Keep in sync with backend/app/models/schemas.py and extension/src/types.

export type ScanStatus = 'accepted' | 'analyzing' | 'complete' | 'failed'
export type Severity = 'info' | 'low' | 'medium' | 'high'
export type Confidence = 'low' | 'medium' | 'high'

export interface ScanAccepted {
  scan_id: string
  status: 'accepted'
  message: string
}

export interface ScanSummary {
  packages: number
  direct: number
  transitive: number
  findings: number
}

export interface Scan {
  scan_id: string
  status: ScanStatus
  created_at: string
  project_name: string | null
  error: string | null
  summary: ScanSummary | null
  warnings?: string[]
}

export interface Evidence {
  source: string
  field: string
  value: unknown
  observed_at: string | null
}

export interface Finding {
  id: string
  rule_id: string
  package: string
  version: string
  severity: Severity
  confidence: Confidence
  /** 0-100, deterministic investigation priority (higher first). */
  priority_score: number
  title: string
  explanation: string
  evidence: Evidence[]
  unknowns?: string[]
  /** Each path starts with the literal "root" (the scanned project), then node ids "name@version". */
  paths: string[][]
}

export interface RegistryMetadata {
  status: 'available' | 'unavailable'
  description: string | null
  license: string | null
  deprecated: string | null
  published_at: string | null
  dist_integrity: string | null
  error: string | null
}

export interface GraphNode {
  id: string
  name: string
  version: string
  direct: boolean
  dev?: boolean
  lockfile_paths: string[]
  resolved_urls?: string[]
  lockfile_integrities?: string[]
  registry?: RegistryMetadata
}

export interface GraphEdge {
  from: string
  to: string
  type: 'prod' | 'dev' | 'optional' | 'peer'
}

/** The project itself is not a node; findings refer to it as "root" (see ROOT_ID). */
export interface DependencyGraphData {
  scan_id: string
  status?: ScanStatus
  nodes: GraphNode[]
  edges: GraphEdge[]
  warnings?: string[]
}

export const ROOT_ID = 'root'

export type VerificationStatusKind = 'match' | 'mismatch' | 'no_record' | 'unavailable'

export interface VerificationResult {
  package: string
  version: string
  release_id: string
  status: VerificationStatusKind
  manifest_hash: string | null
  anchored_hash: string | null
  anchored_at: string | null
  manifest: Record<string, unknown> | null
  registry: { network: string; chain_id: number; address: string } | null
  detail: string | null
}
