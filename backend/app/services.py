from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any

from app.graph.builder import build_dependency_graph
from app.graph.comparison import compare_graphs
from app.detection.rules import detect_graph_changes, detect_unusual_release_timing
from app.models.database import ScanRepository
from app.models.schemas import (
    GraphEdge,
    GraphNode,
    RegistryMetadataResponse,
    ScanComparisonResponse,
    ScanGraph,
    ScanSummary,
    VersionChangeResponse,
)
from app.parsers.lockfile import ParsedPackage, parse_lockfile
from app.parsers.npm_registry import NpmRegistryClient


class ScanService:
    def __init__(self, repository: ScanRepository, registry: NpmRegistryClient) -> None:
        self.repository = repository
        self.registry = registry

    def create_scan(self, lockfile: dict[str, Any], project_name: str | None) -> str:
        scan_id = str(uuid.uuid4())
        self.repository.create(scan_id, project_name, lockfile)
        return scan_id

    async def analyze_scan(self, scan_id: str) -> None:
        row = self.repository.get(scan_id)
        if row is None:
            return
        self.repository.set_analyzing(scan_id)
        try:
            parsed = parse_lockfile(row.lockfile)
            graph = build_dependency_graph(parsed)
            metadata = await self.registry.fetch_many((package.name, package.version) for package in parsed.packages)
            package_evidence = _package_evidence(parsed.packages)
            nodes = []
            for node in graph.nodes:
                registry_metadata = metadata[(node.name, node.version)]
                evidence = package_evidence[node.id]
                nodes.append(
                    GraphNode(
                        id=node.id,
                        name=node.name,
                        version=node.version,
                        direct=node.direct,
                        lockfile_paths=list(node.lockfile_paths),
                        resolved_urls=sorted(evidence["resolved_urls"]),
                        lockfile_integrities=sorted(evidence["lockfile_integrities"]),
                        registry=RegistryMetadataResponse.model_validate(asdict(registry_metadata)),
                    )
                )
            edges = [
                GraphEdge(source=edge.source, target=edge.target, type=edge.dependency_type)
                for edge in graph.edges
            ]
            scan_graph = ScanGraph(
                scan_id=scan_id,
                status="complete",
                nodes=nodes,
                edges=edges,
                warnings=list(graph.warnings),
            )
            project_name = row.project_name or parsed.name
            findings = []
            if project_name:
                baseline_row = self.repository.find_latest_complete(project_name, exclude_scan_id=scan_id)
                if baseline_row is not None and baseline_row.graph is not None:
                    baseline_graph = ScanGraph.model_validate(baseline_row.graph)
                    findings = detect_graph_changes(
                        baseline_graph,
                        scan_graph,
                        observed_at=row.created_at,
                    )
                    comparison = compare_graphs(baseline_graph, scan_graph)
                    release_times = await self.registry.fetch_release_times_many(
                        change.name for change in comparison.version_changes
                    )
                    findings.extend(
                        detect_unusual_release_timing(
                            baseline_graph,
                            scan_graph,
                            release_times=release_times,
                            observed_at=row.created_at,
                        )
                    )
                    findings.sort(key=lambda finding: (-finding.priority_score, finding.rule_id, finding.package))
            direct_count = sum(node.direct for node in nodes)
            summary = ScanSummary(
                packages=len(nodes),
                direct=direct_count,
                transitive=len(nodes) - direct_count,
                findings=len(findings),
            )
            self.repository.set_complete(
                scan_id,
                project_name=project_name,
                summary=summary.model_dump(mode="json"),
                graph=scan_graph.model_dump(mode="json", by_alias=True),
                findings=[finding.model_dump(mode="json") for finding in findings],
                warnings=list(graph.warnings),
            )
        except Exception as exc:
            self.repository.set_failed(scan_id, f"Dependency analysis failed: {type(exc).__name__}")

    def compare_scans(self, baseline_scan_id: str, current_scan_id: str) -> ScanComparisonResponse:
        baseline_row = self.repository.get(baseline_scan_id)
        current_row = self.repository.get(current_scan_id)
        if baseline_row is None or current_row is None:
            raise KeyError("Scan not found")
        if baseline_row.graph is None or current_row.graph is None:
            raise ValueError("Both scans must be complete before comparison")
        comparison = compare_graphs(
            ScanGraph.model_validate(baseline_row.graph),
            ScanGraph.model_validate(current_row.graph),
        )
        return ScanComparisonResponse(
            baseline_scan_id=baseline_scan_id,
            current_scan_id=current_scan_id,
            added_packages=list(comparison.added_packages),
            removed_packages=list(comparison.removed_packages),
            version_changes=[
                VersionChangeResponse(
                    name=change.name,
                    from_versions=list(change.from_versions),
                    to_versions=list(change.to_versions),
                )
                for change in comparison.version_changes
            ],
            added_edges=list(comparison.added_edges),
        )


def _package_evidence(packages: tuple[ParsedPackage, ...]) -> dict[str, dict[str, set[str]]]:
    evidence: dict[str, dict[str, set[str]]] = {}
    for package in packages:
        node_id = f"{package.name}@{package.version}"
        node_evidence = evidence.setdefault(node_id, {"resolved_urls": set(), "lockfile_integrities": set()})
        if package.resolved:
            node_evidence["resolved_urls"].add(package.resolved)
        if package.integrity:
            node_evidence["lockfile_integrities"].add(package.integrity)
    return evidence