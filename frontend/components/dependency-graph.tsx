'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import type { Core, ElementDefinition } from 'cytoscape'
import { Maximize, Minus, Plus } from 'lucide-react'
import type { DependencyGraphData, Severity } from '@/lib/types'

// ponytail: above this size only the root, direct dependencies and flagged/path packages are drawn;
// a dedicated "explore neighbours" mode can come later if users need the full graph.
const MAX_FULL_GRAPH = 400

const SEVERITY_COLOR: Record<Severity, string> = { high: '#b74232', medium: '#d08a10', low: '#3b6390', info: '#7a8c82' }

interface Props {
  graph: DependencyGraphData
  flagged: Map<string, Severity>
  /** Node ids that must stay visible in large graphs (e.g. nodes on finding paths). */
  keep: Set<string>
  selectedNode: string | null
  highlightPaths: string[][] | null
  onSelectNode: (id: string) => void
}

function buildElements(graph: DependencyGraphData, flagged: Map<string, Severity>, keep: Set<string>) {
  let nodes = graph.nodes
  if (nodes.length > MAX_FULL_GRAPH) {
    nodes = nodes.filter((n) => n.id === graph.root || n.direct || flagged.has(n.id) || keep.has(n.id))
  }
  const ids = new Set(nodes.map((n) => n.id))
  ids.add(graph.root)

  const elements: ElementDefinition[] = []
  if (!graph.nodes.some((n) => n.id === graph.root)) {
    elements.push({ data: { id: graph.root, label: graph.root, kind: 'root' } })
  }
  for (const n of nodes) {
    const sev = flagged.get(n.id)
    elements.push({
      data: {
        id: n.id,
        label: `${n.name}\n${n.version}`,
        kind: n.id === graph.root ? 'root' : sev ? 'flagged' : n.direct ? 'direct' : 'transitive',
        color: sev ? SEVERITY_COLOR[sev] : undefined,
      },
    })
  }
  const seen = new Set<string>()
  for (const e of graph.edges) {
    const id = `${e.from}->${e.to}`
    if (!ids.has(e.from) || !ids.has(e.to) || seen.has(id)) continue
    seen.add(id)
    elements.push({ data: { id, source: e.from, target: e.to, type: e.type } })
  }
  return { elements, shown: nodes.length, total: graph.nodes.length }
}

export function DependencyGraph({ graph, flagged, keep, selectedNode, highlightPaths, onSelectNode }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const onSelect = useRef(onSelectNode)
  onSelect.current = onSelectNode
  const [ready, setReady] = useState(0)

  const view = useMemo(() => buildElements(graph, flagged, keep), [graph, flagged, keep])

  useEffect(() => {
    let cy: Core | undefined
    let disposed = false
    void import('cytoscape').then(({ default: cytoscape }) => {
      if (disposed || !container.current) return
      cy = cytoscape({
        container: container.current,
        elements: view.elements,
        minZoom: 0.1,
        maxZoom: 3,
        layout: { name: 'breadthfirst', directed: true, roots: [graph.root], spacingFactor: 1.15, padding: 24 },
        style: [
          {
            selector: 'node',
            style: {
              label: 'data(label)', 'text-wrap': 'wrap', 'font-size': 9, color: '#365b48', 'text-valign': 'bottom', 'text-margin-y': 4,
              width: 18, height: 18, 'background-color': '#e1efe5', 'border-width': 2, 'border-color': '#a9c9b3',
            },
          },
          { selector: 'node[kind = "root"]', style: { 'background-color': '#173d30', 'border-color': '#0f2a20', width: 26, height: 26, 'font-weight': 'bold' } },
          { selector: 'node[kind = "direct"]', style: { 'background-color': '#5e9e6f', 'border-color': '#3f7a51' } },
          { selector: 'node[kind = "flagged"]', style: { 'background-color': 'data(color)', 'border-color': 'data(color)', width: 22, height: 22 } },
          { selector: 'edge', style: { width: 1.2, 'line-color': '#c6d9cc', 'target-arrow-color': '#c6d9cc', 'target-arrow-shape': 'triangle', 'arrow-scale': 0.7, 'curve-style': 'bezier' } },
          { selector: 'edge[type = "dev"]', style: { 'line-style': 'dashed' } },
          { selector: '.faded', style: { opacity: 0.15 } },
          { selector: 'edge.hl', style: { width: 2.5, 'line-color': '#173d30', 'target-arrow-color': '#173d30' } },
          { selector: 'node.hl', style: { 'border-color': '#173d30', 'border-width': 3 } },
          { selector: 'node.selected', style: { 'overlay-color': '#5e9e6f', 'overlay-opacity': 0.25, 'overlay-padding': 6 } },
        ],
      })
      cy.on('tap', 'node', (e) => onSelect.current(e.target.id()))
      cyRef.current = cy
      setReady((r) => r + 1)
    })
    return () => {
      disposed = true
      cy?.destroy()
      cyRef.current = null
    }
  }, [view, graph.root])

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

  const zoom = (factor: number) => {
    const cy = cyRef.current
    if (cy) cy.zoom({ level: cy.zoom() * factor, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } })
  }

  return (
    <div>
      <div className="relative h-[460px] overflow-hidden rounded-lg border border-line bg-[#fbfdfb]">
        <div
          ref={container}
          className="size-full"
          role="img"
          aria-label={`Dependency graph with ${view.shown} packages. Use the findings table for a text alternative.`}
        />
        <div className="absolute right-3 top-3 flex flex-col overflow-hidden rounded-lg border border-line bg-white shadow-sm">
          <button type="button" onClick={() => zoom(1.25)} className="p-2 text-ink-muted hover:bg-surface hover:text-ink" aria-label="Zoom in"><Plus className="size-4" aria-hidden /></button>
          <button type="button" onClick={() => zoom(0.8)} className="border-t border-line p-2 text-ink-muted hover:bg-surface hover:text-ink" aria-label="Zoom out"><Minus className="size-4" aria-hidden /></button>
          <button type="button" onClick={() => cyRef.current?.fit(undefined, 24)} className="border-t border-line p-2 text-ink-muted hover:bg-surface hover:text-ink" aria-label="Fit graph to view"><Maximize className="size-4" aria-hidden /></button>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-ink-muted">
        <Legend color="#173d30" label="Project" />
        <Legend color="#5e9e6f" label="Direct" />
        <Legend color="#e1efe5" border="#a9c9b3" label="Transitive" />
        <Legend color={SEVERITY_COLOR.high} label="Flagged (colour = severity)" />
        <span>Dashed edge = dev dependency · Scroll to zoom, drag to pan, click a package to trace its paths</span>
      </div>
      {view.shown < view.total && (
        <p className="mt-2 text-xs text-ink-muted">
          Showing {view.shown} of {view.total} packages: the project, direct dependencies, and packages involved in findings.
        </p>
      )}
    </div>
  )
}

function Legend({ color, border, label }: { color: string; border?: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="size-2.5 rounded-full border-2" style={{ backgroundColor: color, borderColor: border ?? color }} aria-hidden />
      {label}
    </span>
  )
}
