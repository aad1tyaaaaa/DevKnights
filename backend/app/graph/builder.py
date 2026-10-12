from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from app.parsers.lockfile import ParsedLockfile, ParsedPackage


@dataclass(frozen=True)
class DependencyNode:
    id: str
    name: str
    version: str
    direct: bool
    lockfile_paths: tuple[str, ...]


@dataclass(frozen=True)
class DependencyEdge:
    source: str
    target: str
    dependency_type: str


@dataclass(frozen=True)
class DependencyGraph:
    nodes: tuple[DependencyNode, ...]
    edges: tuple[DependencyEdge, ...]
    warnings: tuple[str, ...] = ()


EDGE_TYPE_ORDER = ["prod", "dev", "optional", "peer"]


def build_dependency_graph(parsed: ParsedLockfile) -> DependencyGraph:
    """Build a directed graph using npm's nearest-ancestor package resolution."""
    packages_by_path = {package.lockfile_path: package for package in parsed.packages}
    # Resolve each root declaration the way npm does, so aliases ("foo": "npm:bar@1") and unusual
    # layouts mark the package that is actually installed, not whatever happens to share the name.
    direct_ids = {
        _node_id(target)
        for dependencies in parsed.root_dependency_groups.values()
        for name in dependencies
        if (target := _resolve_dependency("", name, packages_by_path)) is not None
    }
    graph = nx.DiGraph()

    for package in parsed.packages:
        node_id = _node_id(package)
        existing_paths = graph.nodes[node_id].get("lockfile_paths", set()) if node_id in graph else set()
        graph.add_node(
            node_id,
            name=package.name,
            version=package.version,
            direct=node_id in direct_ids,
            lockfile_paths={*existing_paths, package.lockfile_path},
        )

    warnings = list(parsed.warnings)
    for package in parsed.packages:
        source_id = _node_id(package)
        for dependency_type, dependencies in package.dependency_groups.items():
            for dependency_name in dependencies:
                target = _resolve_dependency(package.lockfile_path, dependency_name, packages_by_path)
                if target is None:
                    warnings.append(
                        f"Could not resolve {dependency_name!r} declared by {package.name}@{package.version}"
                    )
                    continue
                target_id = _node_id(target)
                # One edge per (source, target), carrying every relationship type: a package can be
                # both a dependency and a peer of the same parent, or reached from several installs.
                if graph.has_edge(source_id, target_id):
                    graph.edges[source_id, target_id]["dependency_types"].add(dependency_type)
                else:
                    graph.add_edge(source_id, target_id, dependency_types={dependency_type})

    nodes = tuple(
        DependencyNode(
            id=node_id,
            name=attributes["name"],
            version=attributes["version"],
            direct=attributes["direct"],
            lockfile_paths=tuple(sorted(attributes["lockfile_paths"])),
        )
        for node_id, attributes in sorted(graph.nodes(data=True))
    )
    edges = tuple(
        DependencyEdge(source=source, target=target, dependency_type=dependency_type)
        for source, target, attributes in sorted(graph.edges(data=True))
        for dependency_type in sorted(attributes["dependency_types"], key=EDGE_TYPE_ORDER.index)
    )
    return DependencyGraph(nodes=nodes, edges=edges, warnings=tuple(warnings))


def _resolve_dependency(
    parent_path: str,
    dependency_name: str,
    packages_by_path: dict[str, ParsedPackage],
) -> ParsedPackage | None:
    current_path = parent_path
    while True:
        candidate = f"{current_path}/node_modules/{dependency_name}" if current_path else f"node_modules/{dependency_name}"
        package = packages_by_path.get(candidate)
        if package is not None:
            return package
        ancestor_marker = current_path.rfind("/node_modules/")
        if ancestor_marker < 0:
            if not current_path:
                return None
            current_path = ""
        else:
            current_path = current_path[:ancestor_marker]


def _node_id(package: ParsedPackage) -> str:
    return f"{package.name}@{package.version}"