'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import type { Core, ElementDefinition, LayoutOptions } from 'cytoscape'
import { Maximize, Minus, MousePointerClick, Plus } from 'lucide-react'
import { ROOT_ID, type DependencyGraphData, type Severity } from '@/lib/types'
import { cn } from '@/lib/utils'

// Above this size transitive packages start hidden (flagged/path packages always stay);
// the "Transitive" toggle draws them anyway.
const MAX_FULL_GRAPH = 400
const PADDING = 56

const LAYOUTS = {
  radial: { label: 'Radial', options: { name: 'breadthfirst', directed: true, circle: true, roots: [ROOT_ID], spacingFactor: 1.6, padding: PADDING } },
  tree: { label: 'Tree', options: { name: 'breadthfirst', directed: true, roots: [ROOT_ID], spacingFactor: 1.2, padding: PADDING } },
  // ponytail: cose is O(n²) per iteration; fine for hundreds of nodes, sluggish with every transitive package of a big lockfile.
  force: { label: 'Force', options: { name: 'cose', animate: false, randomize: true, nodeRepulsion: () => 40000, idealEdgeLength: () => 110, padding: PADDING } },
  hubs: { label: 'Hubs', options: { name: 'concentric', concentric: (n: { degree: (b: boolean) => number }) => n.degree(false), levelWidth: () => 3, minNodeSpacing: 18, padding: PADDING } },
} satisfies Record<string, { label: string; options: LayoutOptions }>
type LayoutKey = keyof typeof LAYOUTS

// Matches the severity badges; info is a distinct slate so a flagged node never looks like an ordinary package.
const SEVERITY_COLOR: Record<Severity, string> = { high: '#ff6b57', medium: '#f5b942', low: '#6ea8ff', info: '#9aa3b5' }
const SEVERITIES: Severity[] = ['high', 'medium', 'low', 'info']

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

function buildElements(
  graph: DependencyGraphData,
  rootLabel: string,
  flagged: Map<string, Severity>,
  keep: Set<string>,
  show: { transitive: boolean; dev: boolean },
) {
  // Flagged and finding-path packages are never filtered out.
  const pinned = (id: string) => flagged.has(id) || keep.has(id)
  const nodes = graph.nodes.filter((n) => pinned(n.id) || ((show.transitive || n.direct) && (show.dev || !n.dev)))
  const ids = new Set(nodes.map((n) => n.id))

  // The API does not return the project as a node; draw it and connect it to the direct dependencies.
  const elements: ElementDefinition[] = [{ data: { id: ROOT_ID, label: rootLabel, kind: 'root' } }]
  for (const n of nodes) {
    const sev = flagged.get(n.id)
    elements.push({
      data: {
        id: n.id,
        label: `${n.name}
${n.version}`,
        kind: sev ? 'flagged' : n.direct ? 'direct' : 'transitive',
        color: sev ? SEVERITY_COLOR[sev] : undefined,
      },
    })
  }
  const edges = [...nodes.filter((n) => n.direct).map((n) => ({ from: ROOT_ID, to: n.id, type: 'prod' })), ...graph.edges]
  const seen = new Set<string>()
  for (const e of edges) {
    const id = `${e.from}->${e.to}`
    const known = (x: string) => x === ROOT_ID || ids.has(x)
    if (!known(e.from) || !known(e.to) || seen.has(id) || (!show.dev && e.type === 'dev')) continue
    seen.add(id)
    elements.push({ data: { id, source: e.from, target: e.to, type: e.type } })
  }
  return { elements, shown: nodes.length, total: graph.nodes.length }
}

export function DependencyGraph({ graph, rootLabel, flagged, keep, selectedNode, highlightPaths, onSelectNode }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const onSelect = useRef(onSelectNode)
  onSelect.current = onSelectNode
  const [ready, setReady] = useState(0)
  const [layout, setLayout] = useState<LayoutKey>('radial')
  const layoutRef = useRef(layout)
  layoutRef.current = layout
  const laidOut = useRef<LayoutKey>(layout)
  const [showTransitive, setShowTransitive] = useState(graph.nodes.length <= MAX_FULL_GRAPH)
  const [showDev, setShowDev] = useState(true)
  const [showLabels, setShowLabels] = useState(true)

  const view = useMemo(
    () => buildElements(graph, rootLabel, flagged, keep, { transitive: showTransitive, dev: showDev }),
    [graph, rootLabel, flagged, keep, showTransitive, showDev],
  )

  useEffect(() => {
    let cy: Core | undefined
    let disposed = false
    void import('cytoscape').then(({ default: cytoscape }) => {
      if (disposed || !container.current) return
      laidOut.current = layoutRef.current
      cy = cytoscape({
        container: container.current,
        elements: view.elements,
        minZoom: 0.1,
        maxZoom: 3,
        layout: LAYOUTS[layoutRef.current].options,
        style: [
          {
            selector: 'node',
            style: {
              label: 'data(label)', 'font-family': 'Fredoka, sans-serif', 'text-wrap': 'wrap', 'font-size': 9, color: '#e8d5dd',
              'text-valign': 'bottom', 'text-margin-y': 5, 'min-zoomed-font-size': 7,
              'text-background-color': '#0d0307', 'text-background-opacity': 0.85, 'text-background-padding': '2px', 'text-background-shape': 'roundrectangle',
              width: 16, height: 16, 'background-color': '#2a1520', 'border-width': 1.5, 'border-color': '#6b4a5a',
            },
          },
          {
            selector: 'node[kind = "root"]',
            style: {
              'background-color': '#a8325f', 'border-color': '#f1dbe5', 'border-width': 2, width: 34, height: 34, 'font-size': 11, 'font-weight': 'bold', color: '#ffffff',
              'underlay-color': '#a8325f', 'underlay-opacity': 0.3, 'underlay-padding': 10, 'underlay-shape': 'ellipse',
            },
          },
          { selector: 'node[kind = "direct"]', style: { 'background-color': '#6b1239', 'border-color': '#c4537f', width: 20, height: 20 } },
          // Flagged packages are diamonds, so the state is visible without relying on colour alone.
          { selector: 'node[kind = "flagged"]', style: { shape: 'diamond', 'background-color': 'data(color)', 'border-color': '#000000', 'border-width': 2, width: 26, height: 26, 'font-weight': 'bold', color: 'data(color)' } },
          { selector: 'edge', style: { width: 1, 'line-color': '#5c2a40', 'line-opacity': 0.6, 'target-arrow-color': '#5c2a40', 'target-arrow-shape': 'triangle', 'arrow-scale': 0.6, 'curve-style': 'bezier' } },
          { selector: 'edge[type = "dev"]', style: { 'line-style': 'dashed' } },
          { selector: '.faded', style: { opacity: 0.12 } },
          { selector: 'node.hover', style: { 'border-color': '#ffffff', 'border-width': 2.5, color: '#ffffff', 'z-index': 10 } },
          { selector: 'edge.hover', style: { 'line-color': '#c4537f', 'target-arrow-color': '#c4537f', 'line-opacity': 1, width: 1.8 } },
          { selector: 'edge.hl', style: { width: 2.5, 'line-color': '#ffffff', 'target-arrow-color': '#ffffff', 'line-opacity': 1 } },
          { selector: 'node.hl', style: { 'border-color': '#ffffff', 'border-width': 3 } },
          { selector: 'node.selected', style: { 'underlay-color': '#ffffff', 'underlay-opacity': 0.25, 'underlay-padding': 8, 'underlay-shape': 'ellipse' } },
          { selector: 'node:active', style: { 'overlay-opacity': 0 } },
          { selector: 'node.nolabel', style: { label: '' } },
        ],
      })
      cy.on('tap', 'node', (e) => onSelect.current(e.target.id()))
      cy.on('mouseover', 'node', (e) => {
        e.target.addClass('hover').connectedEdges().addClass('hover')
        if (container.current) container.current.style.cursor = 'pointer'
      })
      cy.on('mouseout', 'node', (e) => {
        e.target.removeClass('hover').connectedEdges().removeClass('hover')
        if (container.current) container.current.style.cursor = ''
      })
      cyRef.current = cy
      setReady((r) => r + 1)
    })
    return () => {
      disposed = true
      cy?.destroy()
      cyRef.current = null
    }
  }, [view])

  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.batch(() => {
      cy.elements().removeClass('hl faded selected')
      let set = cy.collection()
      if (highlightPaths?.length) {
        for (const path of highlightPaths) {
          path.forEach((id, i) => {
            set = set.union(cy.getElementById(id))
            if (i > 0) set = set.union(cy.getElementById(`${path[i - 1]}->${id}`))
          })
        }
      } else if (selectedNode) {
        const n = cy.getElementById(selectedNode)
        set = n.union(n.predecessors())
      }
      if (set.nonempty()) {
        cy.elements().not(set).addClass('faded')
        set.addClass('hl')
      }
      if (selectedNode) cy.getElementById(selectedNode).addClass('selected')
    })
  }, [ready, highlightPaths, selectedNode])

  // Re-run only the layout on an existing graph; rebuilding cytoscape would lose zoom and selection.
  useEffect(() => {
    const cy = cyRef.current
    if (!cy || laidOut.current === layout) return
    laidOut.current = layout
    cy.layout(LAYOUTS[layout].options).run()
  }, [layout, ready])

  useEffect(() => {
    cyRef.current?.nodes().not(`#${ROOT_ID}`).toggleClass('nolabel', !showLabels)
  }, [ready, showLabels])

  const zoom = (factor: number) => {
    const cy = cyRef.current
    if (cy) cy.zoom({ level: cy.zoom() * factor, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } })
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
          <Toggle on={showLabels} onChange={setShowLabels} label="Labels" />
        </div>
      </div>
      <div
        className="dark relative h-[520px] overflow-hidden rounded-xl border border-line bg-[#070205] sm:h-[600px]"
        style={{
          backgroundImage: 'radial-gradient(circle at 50% 50%, rgba(70,10,38,0.45), transparent 65%), radial-gradient(rgba(255,255,255,0.06) 1px, transparent 1px)',
          backgroundSize: '100% 100%, 22px 22px',
        }}
      >
        <div
          ref={container}
          className="size-full"
          role="img"
          aria-label={`Dependency graph with ${view.shown} packages. Use the findings table for a text alternative.`}
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
          <button type="button" onClick={() => zoom(1.25)} className={ctrl} aria-label="Zoom in" title="Zoom in"><Plus className="size-4" aria-hidden /></button>
          <button type="button" onClick={() => zoom(0.8)} className={`${ctrl} border-t border-line`} aria-label="Zoom out" title="Zoom out"><Minus className="size-4" aria-hidden /></button>
          <button type="button" onClick={() => cyRef.current?.fit(undefined, 56)} className={`${ctrl} border-t border-line`} aria-label="Fit graph to view" title="Fit to view"><Maximize className="size-4" aria-hidden /></button>
        </div>
        <p className={`${chip} pointer-events-none absolute bottom-3 left-3 hidden items-center gap-1.5 border-transparent text-[11px] text-ink-muted sm:flex`}>
          <MousePointerClick className="size-3.5" aria-hidden /> Scroll to zoom · drag to pan · click a package to trace its paths
        </p>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-ink-muted">
        <Legend color="#a8325f" border="#f1dbe5" label="Project" />
        <Legend color="#6b1239" border="#c4537f" label="Direct" />
        <Legend color="#2a1520" border="#6b4a5a" label="Transitive" />
        <span className="flex items-center gap-1.5 rounded-full border border-line px-3 py-1">
          <svg width="18" height="6" aria-hidden><line x1="0" y1="3" x2="18" y2="3" stroke="#c4537f" strokeWidth="1.5" strokeDasharray="3 2" /></svg>
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

function Legend({ color, border, label }: { color: string; border?: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 rounded-full border border-line px-3 py-1">
      <span className="size-2.5 rounded-full border-2" style={{ backgroundColor: color, borderColor: border ?? color }} aria-hidden />
      {label}
    </span>
  )
}
