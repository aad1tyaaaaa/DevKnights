from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import GraphEdge, ScanGraph


@dataclass(frozen=True)
class VersionChange:
    name: str
    from_versions: tuple[str, ...]
    to_versions: tuple[str, ...]


@dataclass(frozen=True)
class GraphComparison:
    added_packages: tuple[str, ...]
    removed_packages: tuple[str, ...]
    version_changes: tuple[VersionChange, ...]
    added_edges: tuple[GraphEdge, ...]


def compare_graphs(baseline: ScanGraph, current: ScanGraph) -> GraphComparison:
    baseline_nodes = {node.id: node for node in baseline.nodes}
    current_nodes = {node.id: node for node in current.nodes}
    baseline_versions = _versions_by_name(baseline)
    current_versions = _versions_by_name(current)

    version_changes = tuple(
        VersionChange(
            name=name,
            from_versions=tuple(sorted(baseline_versions[name])),
            to_versions=tuple(sorted(current_versions[name])),
        )
        for name in sorted(baseline_versions.keys() & current_versions.keys())
        if baseline_versions[name] != current_versions[name]
    )
    baseline_edges = {(edge.source, edge.target, edge.type) for edge in baseline.edges}
    added_edges = tuple(
        edge
        for edge in current.edges
        if (edge.source, edge.target, edge.type) not in baseline_edges
    )
    return GraphComparison(
        added_packages=tuple(sorted(current_nodes.keys() - baseline_nodes.keys())),
        removed_packages=tuple(sorted(baseline_nodes.keys() - current_nodes.keys())),
        version_changes=version_changes,
        added_edges=added_edges,
    )


def _versions_by_name(graph: ScanGraph) -> dict[str, set[str]]:
    versions: dict[str, set[str]] = {}
    for node in graph.nodes:
        versions.setdefault(node.name, set()).add(node.version)
    return versions