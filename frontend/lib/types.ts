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
  title: string
  explanation: string
  evidence: Evidence[]
  unknowns: string[]
  paths: string[][]
}

export interface GraphNode {
  id: string
  name: string
  version: string
  direct: boolean
  dev: boolean
  lockfile_paths: string[]
}

export interface GraphEdge {
  from: string
  to: string
  type: 'prod' | 'dev' | 'optional' | 'peer'
}

export interface DependencyGraphData {
  scan_id: string
  root: string
  nodes: GraphNode[]
  edges: GraphEdge[]
}

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
