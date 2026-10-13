'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import type { ForceGraph3DInstance, LinkObject, NodeObject } from '3d-force-graph'
import type { Object3D } from 'three'
import { Maximize, Minus, MousePointerClick, Plus } from 'lucide-react'
import { ROOT_ID, type DependencyGraphData, type Severity } from '@/lib/types'
import { cn } from '@/lib/utils'

// Above this size transitive packages start hidden (flagged/path packages always stay);
// the "Transitive" toggle draws them anyway. WebGL copes with thousands of nodes.
const MAX_FULL_GRAPH = 3000

// Tree and Radial pin nodes to their depth from the project; Force lets the simulation place them.
const LAYOUTS = {
  force: { label: 'Force', dag: null },
  radial: { label: 'Radial', dag: 'radialout' },
  tree: { label: 'Tree', dag: 'td' },
} as const
type LayoutKey = keyof typeof LAYOUTS

// Matches the severity badges; info is a distinct slate so a flagged node never looks like an ordinary package.
const SEVERITY_COLOR: Record<Severity, string> = { high: '#ff6b57', medium: '#f5b942', low: '#6ea8ff', info: '#9aa3b5' }
const SEVERITIES: Severity[] = ['high', 'medium', 'low', 'info']
const KIND_COLOR = { root: '#e0457f', direct: '#c4537f', transitive: '#8a6577' }
const KIND_SIZE = { root: 14, direct: 3, transitive: 1, flagged: 6 }
const LINK_COLOR = { prod: '#7a3a58', dev: '#4a5f8f', hl: '#ffffff' }
const FADED = '#2a1a22'

type Kind = 'root' | 'direct' | 'transitive' | 'flagged'
interface GNode extends NodeObject {
  id: string
  label: string
  kind: Kind
  sev?: Severity
}
interface GLink extends LinkObject<GNode> {
  id: string
  type: string
}

interface Props {
  graph: DependencyGraphData
  /** Label for the project node (the API refers to it as "root"). */
  rootLabel: string
  flagged: Map<string, Severity>
  /** Node ids that must stay visible in large graphs (e.g. nodes on finding paths). */
  keep: Set<string>
  selectedNode: string | null
  highlightPaths: string[][] | null
  onSelectNode: (id: string) => void
}

function buildData(
  graph: DependencyGraphData,
  rootLabel: string,
  flagged: Map<string, Severity>,
  keep: Set<string>,
  show: { transitive: boolean; dev: boolean },
) {
  // Flagged and finding-path packages are never filtered out.
  const pinned = (id: string) => flagged.has(id) || keep.has(id)
  const shown = graph.nodes.filter((n) => pinned(n.id) || ((show.transitive || n.direct) && (show.dev || !n.dev)))
  const ids = new Set(shown.map((n) => n.id))

  // The API does not return the project as a node; draw it and connect it to the direct dependencies.
  const nodes: GNode[] = [{ id: ROOT_ID, label: rootLabel, kind: 'root' }]
  for (const n of shown) {
    const sev = flagged.get(n.id)
    nodes.push({
      id: n.id,
      label: `${n.name}@${n.version}${sev ? `\n${sev} severity` : ''}${n.dev ? '\ndev dependency' : ''}`,
      kind: sev ? 'flagged' : n.direct ? 'direct' : 'transitive',
      sev,
    })
  }
  const edges = [...shown.filter((n) => n.direct).map((n) => ({ from: ROOT_ID, to: n.id, type: 'prod' })), ...graph.edges]
  const links: GLink[] = []
  // Who depends on each package, for tracing a selection back to the project.
  const parents = new Map<string, string[]>()
  const seen = new Set<string>()
  for (const e of edges) {
    const id = `${e.from}->${e.to}`
    const known = (x: string) => x === ROOT_ID || ids.has(x)
    if (!known(e.from) || !known(e.to) || seen.has(id) || (!show.dev && e.type === 'dev')) continue
    seen.add(id)
    links.push({ id, source: e.from, target: e.to, type: e.type })
    parents.set(e.to, [...(parents.get(e.to) ?? []), e.from])
  }
  return { nodes, links, parents, shown: shown.length, total: graph.nodes.length }
}

/** Plain-text tooltip: package names come from the lockfile, so never render them as HTML. */
function tooltip(n: GNode) {
  const el = document.createElement('div')
  el.textContent = n.label
  el.style.whiteSpace = 'pre'
  el.style.fontFamily = 'Fredoka, sans-serif'
  el.style.fontSize = '12px'
  return el
}

export function DependencyGraph({ graph, rootLabel, flagged, keep, selectedNode, highlightPaths, onSelectNode }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const graphRef = useRef<ForceGraph3DInstance<GNode, GLink> | null>(null)
  const onSelect = useRef(onSelectNode)
  onSelect.current = onSelectNode
  // Read by the colour accessors; empty sets mean nothing is highlighted.
  const hl = useRef({ nodes: new Set<string>(), links: new Set<string>() })
  const fitPending = useRef(true)
  const [ready, setReady] = useState(false)
  const [layout, setLayout] = useState<LayoutKey>('force')
  const [showTransitive, setShowTransitive] = useState(graph.nodes.length <= MAX_FULL_GRAPH)
  const [showDev, setShowDev] = useState(true)

  const view = useMemo(
    () => buildData(graph, rootLabel, flagged, keep, { transitive: showTransitive, dev: showDev }),
    [graph, rootLabel, flagged, keep, showTransitive, showDev],
  )

  useEffect(() => {
    let disposed = false
    let resize: ResizeObserver | undefined
    // three.js needs the browser, so load it on the client only.
    void Promise.all([import('3d-force-graph'), import('three')]).then(([{ default: ForceGraph3D }, THREE]) => {
      const el = container.current
      if (disposed || !el) return
      const active = () => hl.current.nodes.size > 0
      const nodeColor = (n: GNode) =>
        active() && !hl.current.nodes.has(n.id) ? FADED : n.sev ? SEVERITY_COLOR[n.sev] : KIND_COLOR[n.kind as keyof typeof KIND_COLOR]
      const g = (new ForceGraph3D(el) as unknown as ForceGraph3DInstance<GNode, GLink>)
        .width(el.clientWidth)
        .height(el.clientHeight)
        .backgroundColor('#070205')
        .showNavInfo(false)
        .nodeLabel(tooltip)
        .nodeVal((n) => KIND_SIZE[n.kind])
        .nodeColor(nodeColor)
        .nodeOpacity(0.95)
        // Flagged packages are octahedrons, so the state is visible without relying on colour alone.
        .nodeThreeObject((n) =>
          n.kind === 'flagged'
            ? new THREE.Mesh(new THREE.OctahedronGeometry(7), new THREE.MeshLambertMaterial({ color: nodeColor(n), transparent: true, opacity: 0.95 }))
            // Nothing returned: the default sphere.
            : (null as unknown as Object3D),
        )
        .linkColor((l) => (hl.current.links.has(l.id) ? LINK_COLOR.hl : active() ? FADED : l.type === 'dev' ? LINK_COLOR.dev : LINK_COLOR.prod))
        .linkOpacity(0.4)
        .linkWidth((l) => (hl.current.links.has(l.id) ? 1.2 : 0))
        // Particles flow from dependent to dependency along highlighted paths, showing direction.
        .linkDirectionalParticles((l) => (hl.current.links.has(l.id) ? 3 : 0))
        .linkDirectionalParticleWidth(1.6)
        .dagLevelDistance(45)
        // npm graphs can contain cycles; depth layouts just ignore the loop.
        .onDagError(() => undefined)
        .onNodeClick((n) => onSelect.current(n.id))
        .onEngineStop(() => {
          if (!fitPending.current) return
          fitPending.current = false
          g.zoomToFit(600, 40)
        })
      resize = new ResizeObserver(() => g.width(el.clientWidth).height(el.clientHeight))
      resize.observe(el)
      graphRef.current = g
      setReady(true)
    })
    return () => {
      disposed = true
      resize?.disconnect()
      graphRef.current?._destructor()
      graphRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!ready) return
    fitPending.current = true
    graphRef.current?.graphData({ nodes: view.nodes, links: view.links })
  }, [ready, view])

  useEffect(() => {
    const g = graphRef.current
    if (!g) return
    fitPending.current = true
    // null turns depth layout off (the typings omit it) and releases the pinned positions.
    g.dagMode(LAYOUTS[layout].dag as Parameters<typeof g.dagMode>[0]).d3ReheatSimulation()
  }, [ready, layout])

  useEffect(() => {
    const g = graphRef.current
    if (!g) return
    const nodes = new Set<string>()
    const links = new Set<string>()
    if (highlightPaths?.length) {
      for (const path of highlightPaths) {
        path.forEach((id, i) => {
          nodes.add(id)
          if (i > 0) links.add(`${path[i - 1]}->${id}`)
        })
      }
    } else if (selectedNode) {
      // The selection and every package that (transitively) depends on it, up to the project.
      const queue = [selectedNode]
      nodes.add(selectedNode)
      while (queue.length) {
        const id = queue.pop()!
        for (const parent of view.parents.get(id) ?? []) {
          links.add(`${parent}->${id}`)
          if (!nodes.has(parent)) {
            nodes.add(parent)
            queue.push(parent)
          }
        }
      }
    }
    hl.current = { nodes, links }
    // Re-assigning an accessor makes the graph re-evaluate it for every node/link.
    g.nodeColor(g.nodeColor())
      .nodeThreeObject(g.nodeThreeObject())
      .linkColor(g.linkColor())
      .linkWidth(g.linkWidth())
      .linkDirectionalParticles(g.linkDirectionalParticles())
  }, [ready, view, highlightPaths, selectedNode])

  const zoom = (factor: number) => {
    const g = graphRef.current
    if (!g) return
    const { x, y, z } = g.cameraPosition()
    g.cameraPosition({ x: x * factor, y: y * factor, z: z * factor }, undefined, 300)
  }

  const ctrl = 'grid size-9 place-items-center text-ink-muted transition-colors hover:bg-brand hover:text-white'
  const chip = 'rounded-md border bg-black/70 px-2.5 py-1 backdrop-blur'
  const large = graph.nodes.length > MAX_FULL_GRAPH
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div role="radiogroup" aria-label="Graph layout" className="flex rounded-lg border border-line bg-surface/40 p-1">
          {(Object.keys(LAYOUTS) as LayoutKey[]).map((key) => (
            <button
              key={key}
              type="button"
              role="radio"
              aria-checked={layout === key}
              onClick={() => setLayout(key)}
              className={cn(
                'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                layout === key ? 'bg-brand text-white shadow-sm' : 'text-ink-muted hover:bg-ink/5 hover:text-ink',
              )}
            >
              {LAYOUTS[key].label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2" aria-label="Show in graph" role="group">
          <Toggle on={showTransitive} onChange={setShowTransitive} label="Transitive" hint={large ? `Draws all ${graph.nodes.length.toLocaleString()} packages; may be slow` : undefined} />
          <Toggle on={showDev} onChange={setShowDev} label="Dev deps" />
        </div>
      </div>
      <div className="dark relative h-[520px] overflow-hidden rounded-xl border border-line bg-[#070205] sm:h-[600px]">
        <div
          ref={container}
          className="size-full"
          role="img"
          aria-label={`3D dependency graph with ${view.shown} packages. Use the findings table for a text alternative.`}
        />
        <div className="pointer-events-none absolute left-3 top-3 flex flex-wrap gap-2 text-[11px]">
          <span className={`${chip} border-line text-ink-muted`}>
            <span className="font-semibold tabular-nums text-ink">{view.shown.toLocaleString()}</span>
            {view.shown < view.total && ` of ${view.total.toLocaleString()}`} packages shown
          </span>
          {flagged.size > 0 && (
            <span className={`${chip} border-[#f5b942]/30 text-warn`}>
              <span className="font-semibold tabular-nums">{flagged.size}</span> flagged
            </span>
          )}
        </div>
        <div className="absolute right-3 top-3 flex flex-col overflow-hidden rounded-lg border border-line bg-black/70 backdrop-blur">
          <button type="button" onClick={() => zoom(0.8)} className={ctrl} aria-label="Zoom in" title="Zoom in"><Plus className="size-4" aria-hidden /></button>
          <button type="button" onClick={() => zoom(1.25)} className={`${ctrl} border-t border-line`} aria-label="Zoom out" title="Zoom out"><Minus className="size-4" aria-hidden /></button>
          <button type="button" onClick={() => graphRef.current?.zoomToFit(600, 40)} className={`${ctrl} border-t border-line`} aria-label="Fit graph to view" title="Fit to view"><Maximize className="size-4" aria-hidden /></button>
        </div>
        <p className={`${chip} pointer-events-none absolute bottom-3 left-3 hidden items-center gap-1.5 border-transparent text-[11px] text-ink-muted sm:flex`}>
          <MousePointerClick className="size-3.5" aria-hidden /> Drag to rotate · right-drag to pan · scroll to zoom · click a package to trace its paths
        </p>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-ink-muted">
        <Legend color={KIND_COLOR.root} label="Project" />
        <Legend color={KIND_COLOR.direct} label="Direct" />
        <Legend color={KIND_COLOR.transitive} label="Transitive" />
        <span className="flex items-center gap-1.5 rounded-full border border-line px-3 py-1">
          <svg width="18" height="6" aria-hidden><line x1="0" y1="3" x2="18" y2="3" stroke={LINK_COLOR.dev} strokeWidth="2" /></svg>
          Dev dependency
        </span>
        <span className="flex items-center gap-2.5 rounded-full border border-line px-3 py-1">
          Flagged
          {SEVERITIES.map((sev) => (
            <span key={sev} className="flex items-center gap-1 capitalize">
              <span className="size-2 rotate-45" style={{ backgroundColor: SEVERITY_COLOR[sev] }} aria-hidden />
              {sev}
            </span>
          ))}
        </span>
      </div>
      {view.shown < view.total && (
        <p className="mt-3 text-xs text-ink-muted">Some packages are hidden by the options above. Flagged packages and finding paths always stay visible.</p>
      )}
    </div>
  )
}

function Toggle({ on, onChange, label, hint }: { on: boolean; onChange: (v: boolean) => void; label: string; hint?: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      title={hint}
      className={cn(
        'flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors',
        on ? 'border-brand bg-brand text-white' : 'border-line text-ink-muted hover:text-ink',
      )}
    >
      <span className={cn('relative h-3.5 w-6 rounded-full transition-colors', on ? 'bg-[#c4537f]' : 'bg-ink/15')} aria-hidden>
        <span className={cn('absolute top-0.5 size-2.5 rounded-full bg-white transition-all', on ? 'left-3' : 'left-0.5')} />
      </span>
      {label}
    </button>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 rounded-full border border-line px-3 py-1">
      <span className="size-2.5 rounded-full" style={{ backgroundColor: color }} aria-hidden />
      {label}
    </span>
  )
}
