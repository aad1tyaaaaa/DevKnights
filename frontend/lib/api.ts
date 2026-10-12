import { API_BASE_URL } from '@/lib/config'

export type ScanStatus = 'accepted' | 'analyzing' | 'complete' | 'failed'

export interface ScanDetail {
  scan_id: string
  status: ScanStatus
  created_at: string
  project_name: string | null
  summary: { packages: number; direct: number; transitive: number; findings: number } | null
  warnings: string[]
  error: string | null
}

export interface GraphNode {
  id: string
  name: string
  version: string
  direct: boolean
  lockfile_paths: string[]
  registry: { status: 'available' | 'unavailable'; license: string | null; deprecated: string | null }
}

export interface ScanGraph {
  scan_id: string
  status: ScanStatus
  nodes: GraphNode[]
  edges: Array<{ from: string; to: string; type: 'prod' | 'dev' | 'optional' | 'peer' }>
  warnings: string[]
}

export interface Finding {
  id: string
  rule_id: string
  package: string
  version: string
  severity: 'info' | 'low' | 'medium' | 'high'
  confidence: 'low' | 'medium' | 'high'
  priority_score: number
  title: string
  explanation: string
  evidence: Array<{ source: string; field: string; value: unknown; observed_at: string }>
  paths: string[][]
}

export type ApiResult<T> = { data: T; error: null } | { data: null; error: string }

export async function fetchApi<T>(path: string): Promise<ApiResult<T>> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { cache: 'no-store' })
    if (!response.ok) return { data: null, error: `API returned ${response.status}.` }
    return { data: (await response.json()) as T, error: null }
  } catch {
    return { data: null, error: `Cannot reach the Provenyx API at ${API_BASE_URL}.` }
  }
}