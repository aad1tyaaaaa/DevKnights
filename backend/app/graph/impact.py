"""Bounded dependency reachability analysis for security findings."""

from __future__ import annotations

from collections import deque

import networkx as nx

from app.models.schemas import BlastRadiusAnalysis, ScanGraph


AFFECTED_DEFINITION = (
    "Unique installed package-release nodes that are the target or can reach it through dependency edges; "
    "this measures dependency reachability, not runtime code execution."
)
REACHABILITY_NOTE = (
    "A dependency path shows that installation resolution can reach the package. It does not prove that application "
    "code imports or executes the package."
)


def analyze_blast_radius(
    graph: ScanGraph,
    target_node_id: str,
    *,
    max_paths: int = 25,
    max_depth: int = 20,
    max_upstream_dependents: int = 100,
) -> BlastRadiusAnalysis:
    """Describe bounded root-to-target reachability using stable graph node identities.

    Path enumeration stops after ``max_paths`` and never revisits a node in the same path, so
    cyclic or highly connected graphs cannot cause unbounded traversal.
    """
    node_by_id = {node.id: node for node in graph.nodes}
    if target_node_id not in node_by_id:
        return BlastRadiusAnalysis(
            target_node_id=target_node_id,
            direct=False,
            reachable=False,
            affected_package_count=0,
            affected_package_definition=AFFECTED_DEFINITION,
            reachability_note=REACHABILITY_NOTE,
        )

    dependency_graph = nx.DiGraph()
    dependency_graph.add_nodes_from(sorted(node_by_id))
    dependency_graph.add_edges_from(sorted((edge.source, edge.target) for edge in graph.edges))
    direct_nodes = sorted(node.id for node in graph.nodes if node.direct)
    direct = node_by_id[target_node_id].direct

    paths, truncated = _bounded_paths(
        dependency_graph,
        direct_nodes,
        target_node_id,
        max_paths=max(1, max_paths),
        max_depth=max(1, max_depth),
    )
    if direct and ["root", target_node_id] not in paths:
        paths.insert(0, ["root", target_node_id])
        if len(paths) > max(1, max_paths):
            paths.pop()
            truncated = True

    shortest = _shortest_root_path(dependency_graph, direct_nodes, target_node_id)
    root_reachable: set[str] = set()
    for direct_id in direct_nodes:
        root_reachable.add(direct_id)
        root_reachable.update(nx.descendants(dependency_graph, direct_id))
    reachable = target_node_id in root_reachable
    upstream = sorted(nx.ancestors(dependency_graph, target_node_id) & root_reachable)
    affected = sorted({target_node_id, *upstream}) if reachable else []
    introducers = sorted(
        direct_id
        for direct_id in direct_nodes
        if direct_id == target_node_id or nx.has_path(dependency_graph, direct_id, target_node_id)
    )
    branch_counts: dict[str, int] = {}
    for path in paths:
        if len(path) >= 2:
            branch_counts[path[1]] = branch_counts.get(path[1], 0) + 1
    capped_upstream = upstream[: max(0, max_upstream_dependents)]

    return BlastRadiusAnalysis(
        target_node_id=target_node_id,
        direct=direct,
        reachable=reachable,
        shortest_path=shortest,
        paths=paths,
        paths_truncated=truncated,
        introducing_direct_dependencies=introducers,
        upstream_dependents=capped_upstream,
        upstream_dependents_truncated=len(upstream) > len(capped_upstream),
        affected_package_count=len(affected),
        affected_package_definition=AFFECTED_DEFINITION,
        branch_path_counts=dict(sorted(branch_counts.items())),
        reachability_note=REACHABILITY_NOTE,
    )


def _bounded_paths(
    graph: nx.DiGraph,
    direct_nodes: list[str],
    target: str,
    *,
    max_paths: int,
    max_depth: int,
) -> tuple[list[list[str]], bool]:
    paths: list[list[str]] = []
    truncated = False
    for direct_id in direct_nodes:
        if direct_id == target:
            candidate_paths = [[direct_id]]
        else:
            depth_truncated = [False]
            candidate_paths = _simple_paths(
                graph,
                direct_id,
                target,
                max_depth=max_depth,
                depth_truncated=depth_truncated,
            )
        for path in candidate_paths:
            if len(paths) == max_paths:
                return paths, True
            paths.append(["root", *path])
        if direct_id != target and depth_truncated[0]:
            truncated = True
    return paths, truncated


def _simple_paths(
    graph: nx.DiGraph,
    source: str,
    target: str,
    *,
    max_depth: int,
    depth_truncated: list[bool],
):
    """Yield deterministic simple paths with an explicit depth bound."""
    if source not in graph or target not in graph:
        return
    stack: list[tuple[str, list[str], set[str]]] = [(source, [source], {source})]
    while stack:
        node, path, seen = stack.pop()
        if node == target:
            yield path
            continue
        if len(path) - 1 >= max_depth:
            if nx.has_path(graph, node, target):
                depth_truncated[0] = True
            continue
        for neighbor in reversed(sorted(graph.successors(node))):
            if neighbor not in seen:
                stack.append((neighbor, [*path, neighbor], {*seen, neighbor}))


def _shortest_root_path(
    graph: nx.DiGraph,
    direct_nodes: list[str],
    target: str,
) -> list[str]:
    candidates: list[list[str]] = []
    for direct_id in direct_nodes:
        path = _stable_shortest_path(graph, direct_id, target)
        if path:
            candidates.append(["root", *path])
    return min(candidates, key=lambda path: (len(path), path)) if candidates else []


def _stable_shortest_path(graph: nx.DiGraph, source: str, target: str) -> list[str]:
    if source not in graph or target not in graph:
        return []
    queue = deque([(source, [source])])
    visited_depth = {source: 0}
    while queue:
        node, path = queue.popleft()
        if node == target:
            return path
        for neighbor in sorted(graph.successors(node)):
            next_depth = len(path)
            if neighbor not in visited_depth:
                visited_depth[neighbor] = next_depth
                queue.append((neighbor, [*path, neighbor]))
    return []
