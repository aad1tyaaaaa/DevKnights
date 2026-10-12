// Mirrors docs/api-contract.md. Keep in sync with backend/app/models/schemas.py and extension/src/types.

export type ScanStatus = 'accepted' | 'analyzing' | 'complete' | 'failed'
export type Severity = 'info' | 'low' | 'medium' | 'high'
export type Confidence = 'low' | 'medium' | 'high'

export interface ScanAccepted {
  scan_id: string
  status: 'accepted'
  message: string
}

export interface GitHubAuthStatus {
  configured: boolean
  connected: boolean
  login: string | null
  avatar_url: string | null
}

export interface GitHubRepository {
  id: number
  name: string
  full_name: string
  private: boolean
  description: string | null
  default_branch: string
  html_url: string
  updated_at: string
  owner_avatar_url: string | null
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

export interface ThreatExplanation {
  source: 'deterministic' | 'gemini'
  what_was_detected: string
  why_it_may_be_risky: string
  evidence_summary: string[]
  uncertainty: string
  investigation_steps: string[]
}

export interface RemediationRecommendation {
  action: string
  rationale: string
  confidence: Confidence
  limitation?: string | null
}

export interface BlastRadiusAnalysis {
  target_node_id: string
  direct: boolean
  reachable: boolean
  shortest_path: string[]
  paths: string[][]
  paths_truncated: boolean
  introducing_direct_dependencies: string[]
  upstream_dependents: string[]
  upstream_dependents_truncated: boolean
  affected_package_count: number
  affected_package_definition: string
  branch_path_counts: Record<string, number>
  reachability_note: string
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
  ranking_source?: 'deterministic' | 'gemini'
  ai_priority_score?: number | null
  ai_rationale?: string | null
  title: string
  explanation: string
  evidence: Evidence[]
  unknowns?: string[]
  /** Each path starts with the literal "root" (the scanned project), then node ids "name@version". */
  paths: string[][]
  threat_explanation?: ThreatExplanation | null
  remediation?: RemediationRecommendation[]
  blast_radius?: BlastRadiusAnalysis | null
}

export interface RegistryMetadata {
  status: 'available' | 'unavailable'
  publisher: string | null
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
