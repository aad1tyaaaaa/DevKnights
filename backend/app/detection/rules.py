from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import networkx as nx

from app.detection.osv import OsvAdvisory
from app.graph.comparison import compare_graphs
from app.models.schemas import Finding, FindingEvidence, GraphNode, ScanGraph


FINDING_NAMESPACE = uuid.UUID("84112ff9-ef11-4bee-9be8-592a1230eff8")


def detect_known_vulnerabilities(
    current: ScanGraph,
    *,
    advisories: dict[tuple[str, str], tuple[OsvAdvisory, ...] | None],
    observed_at: datetime,
) -> list[Finding]:
    findings: list[Finding] = []
    for node in current.nodes:
        matches = advisories.get((node.name, node.version))
        if not matches:
            continue
        severity, priority = _advisory_risk(matches)
        identifiers = sorted({identifier for advisory in matches for identifier in (advisory.id, *advisory.aliases)})
        findings.append(
            Finding(
                id=_finding_id(current.scan_id, "known-vulnerability", node.id),
                rule_id="known-vulnerability",
                package=node.name,
                version=node.version,
                severity=severity,
                confidence="high",
                priority_score=priority,
                title=f"Known vulnerability advisory ({len(matches)})",
                explanation=(
                    f"OSV reports {len(matches)} advisory match(es) for the exact installed release {node.id}. "
                    "Review the advisory details and upgrade guidance; presence in OSV does not prove exploitation."
                ),
                evidence=[
                    FindingEvidence(
                        source="osv",
                        field="advisories",
                        value={
                            "package": node.name,
                            "version": node.version,
                            "identifiers": identifiers,
                            "advisories": [
                                {
                                    "id": advisory.id,
                                    "aliases": list(advisory.aliases),
                                    "summary": advisory.summary,
                                    "severity": advisory.severity,
                                }
                                for advisory in matches
                            ],
                        },
                        observed_at=observed_at,
                    )
                ],
                paths=_dependency_paths(current, node.id),
            )
        )
    return sorted(findings, key=lambda finding: (-finding.priority_score, finding.package, finding.version))


def detect_graph_changes(
    baseline: ScanGraph,
    current: ScanGraph,
    *,
    observed_at: datetime,
) -> list[Finding]:
    """Return explainable change findings; absence of a baseline must be handled by the caller."""
    comparison = compare_graphs(baseline, current)
    baseline_names = {node.name for node in baseline.nodes}
    current_nodes = {node.id: node for node in current.nodes}
    findings: list[Finding] = []

    for node_id in comparison.added_packages:
        node = current_nodes[node_id]
        if node.name in baseline_names:
            continue
        findings.append(
            Finding(
                id=_finding_id(current.scan_id, "new-dependency", node.id),
                rule_id="new-dependency",
                package=node.name,
                version=node.version,
                severity="info",
                confidence="high",
                priority_score=30 if node.direct else 20,
                title=f"New {'direct' if node.direct else 'transitive'} dependency",
                explanation=(
                    f"{node.id} was not present in baseline scan {baseline.scan_id}. "
                    "A new dependency is not inherently malicious and should be reviewed in the context of the update."
                ),
                evidence=[
                    FindingEvidence(
                        source="lockfile",
                        field="dependency_added",
                        value={"baseline_scan_id": baseline.scan_id, "node_id": node.id, "direct": node.direct},
                        observed_at=observed_at,
                    )
                ],
                paths=_dependency_paths(current, node.id),
            )
        )

    # Compare relationships by package name: when express@4.18.2 becomes express@4.18.3 every edge has a
    # new node id, but only dependencies the package did not have before are an expansion.
    baseline_names_by_id = {node.id: node.name for node in baseline.nodes}
    current_names_by_id = {node.id: node.name for node in current.nodes}
    baseline_relationships = {
        (baseline_names_by_id.get(edge.source, edge.source), baseline_names_by_id.get(edge.target, edge.target), edge.type)
        for edge in baseline.edges
    }
    added_edges_by_source: dict[str, list[dict[str, str]]] = {}
    for edge in comparison.added_edges:
        relationship = (current_names_by_id.get(edge.source, edge.source), current_names_by_id.get(edge.target, edge.target), edge.type)
        if relationship in baseline_relationships:
            continue
        added_edges_by_source.setdefault(edge.source, []).append(
            {"from": edge.source, "to": edge.target, "type": edge.type}
        )
    for source_id, edges in sorted(added_edges_by_source.items()):
        source_node = current_nodes.get(source_id)
        if source_node is None:
            continue
        findings.append(
            Finding(
                id=_finding_id(current.scan_id, "dependency-expansion", source_id),
                rule_id="dependency-expansion",
                package=source_node.name,
                version=source_node.version,
                severity="low",
                confidence="high",
                priority_score=min(60, 35 + (5 * len(edges))),
                title="Dependency graph expanded",
                explanation=(
                    f"{source_id} introduces {len(edges)} dependency edge(s) not present in baseline scan "
                    f"{baseline.scan_id}. Expansion is an investigation signal, not proof of compromise."
                ),
                evidence=[
                    FindingEvidence(
                        source="lockfile",
                        field="added_edges",
                        value={"baseline_scan_id": baseline.scan_id, "edges": edges},
                        observed_at=observed_at,
                    )
                ],
                paths=_dependency_paths(current, source_id),
            )
        )

    return sorted(findings, key=lambda finding: (-finding.priority_score, finding.rule_id, finding.package))


def detect_unusual_release_timing(
    baseline: ScanGraph,
    current: ScanGraph,
    *,
    release_times: dict[str, dict[str, str] | None],
    observed_at: datetime,
    threshold: timedelta = timedelta(hours=1),
) -> list[Finding]:
    comparison = compare_graphs(baseline, current)
    current_nodes = {node.id: node for node in current.nodes}
    findings: list[Finding] = []
    for change in comparison.version_changes:
        history = release_times.get(change.name)
        if not history:
            continue
        parsed_history = sorted(
            (published_at, version)
            for version, timestamp in history.items()
            if (published_at := _parse_registry_datetime(timestamp)) is not None
        )
        for version in change.to_versions:
            node = current_nodes.get(f"{change.name}@{version}")
            current_time = _parse_registry_datetime(history.get(version, ""))
            if node is None or current_time is None:
                continue
            predecessors = [(time, prior_version) for time, prior_version in parsed_history if time < current_time]
            if not predecessors:
                continue
            previous_time, previous_version = predecessors[-1]
            interval = current_time - previous_time
            if interval > threshold:
                continue
            findings.append(
                Finding(
                    id=_finding_id(current.scan_id, "unusual-release-timing", node.id),
                    rule_id="unusual-release-timing",
                    package=node.name,
                    version=node.version,
                    severity="low",
                    confidence="medium",
                    priority_score=45,
                    title="Release followed its predecessor unusually quickly",
                    explanation=(
                        f"npm reports {node.id} was published {int(interval.total_seconds())} seconds after "
                        f"{node.name}@{previous_version}. The one-hour threshold is an investigation heuristic, "
                        "not evidence that the release is malicious."
                    ),
                    evidence=[
                        FindingEvidence(
                            source="npm-registry",
                            field="release_interval",
                            value={
                                "previous_version": previous_version,
                                "previous_published_at": previous_time.isoformat(),
                                "current_published_at": current_time.isoformat(),
                                "interval_seconds": int(interval.total_seconds()),
                                "threshold_seconds": int(threshold.total_seconds()),
                            },
                            observed_at=observed_at,
                        )
                    ],
                    paths=_dependency_paths(current, node.id),
                )
            )
    return findings


def detect_publisher_changes(
    baseline: ScanGraph,
    current: ScanGraph,
    *,
    observed_at: datetime,
) -> list[Finding]:
    comparison = compare_graphs(baseline, current)
    baseline_nodes = {(node.name, node.version): node for node in baseline.nodes}
    current_nodes = {(node.name, node.version): node for node in current.nodes}
    findings: list[Finding] = []

    for change in comparison.version_changes:
        previous_publishers = {
            node.registry.publisher
            for version in change.from_versions
            if (node := baseline_nodes.get((change.name, version))) is not None
            and node.registry.publisher is not None
        }
        if not previous_publishers:
            continue
        for version in change.to_versions:
            node = current_nodes.get((change.name, version))
            if node is None or node.registry.publisher is None or node.registry.publisher in previous_publishers:
                continue
            findings.append(
                Finding(
                    id=_finding_id(current.scan_id, "publisher-change", node.id),
                    rule_id="publisher-change",
                    package=node.name,
                    version=node.version,
                    severity="medium",
                    confidence="high",
                    priority_score=60,
                    title="Release publisher changed",
                    explanation=(
                        f"npm identifies {node.registry.publisher!r} as the publisher of {node.id}, while the "
                        f"baseline version was published by {', '.join(repr(value) for value in sorted(previous_publishers))}. "
                        "Publisher changes can be legitimate, but should be verified during an upgrade."
                    ),
                    evidence=[
                        FindingEvidence(
                            source="npm-registry",
                            field="publisher_change",
                            value={
                                "from_versions": list(change.from_versions),
                                "previous_publishers": sorted(previous_publishers),
                                "to_version": version,
                                "current_publisher": node.registry.publisher,
                            },
                            observed_at=observed_at,
                        )
                    ],
                    paths=_dependency_paths(current, node.id),
                )
            )
    return findings


def detect_install_script_changes(
    baseline: ScanGraph,
    current: ScanGraph,
    *,
    observed_at: datetime,
) -> list[Finding]:
    """Flag releases that run lifecycle scripts on install when their predecessor did not.

    Install scripts execute arbitrary code on every `npm install`, so gaining one in a patch or
    minor update is one of the strongest supply-chain signals available without running the package.
    Unknown metadata (None) never produces a finding.
    """
    comparison = compare_graphs(baseline, current)
    baseline_nodes = {node.id: node for node in baseline.nodes}
    baseline_names = {node.name for node in baseline.nodes}
    current_nodes = {node.id: node for node in current.nodes}
    findings: list[Finding] = []

    for change in comparison.version_changes:
        previous = [baseline_nodes.get(f"{change.name}@{version}") for version in change.from_versions]
        previous_scripts = [install_scripts(node) for node in previous if node is not None]
        if not previous_scripts or any(scripts is None or scripts for scripts in previous_scripts):
            continue
        for version in change.to_versions:
            node = current_nodes.get(f"{change.name}@{version}")
            if node is None or not (scripts := install_scripts(node)):
                continue
            findings.append(
                _install_script_finding(
                    current,
                    node,
                    rule_id="install-script-added",
                    severity="high",
                    priority=85,
                    title="Install script introduced in update",
                    explanation=(
                        f"{node.id} runs install lifecycle script(s) ({', '.join(scripts)}), while "
                        f"{', '.join(f'{change.name}@{v}' for v in change.from_versions)} ran no install scripts. "
                        "Install scripts execute code on every machine that installs the package; review the script "
                        "source before merging."
                    ),
                    scripts=scripts,
                    extra={"from_versions": list(change.from_versions)},
                    observed_at=observed_at,
                )
            )

    for node_id in comparison.added_packages:
        node = current_nodes[node_id]
        if node.name in baseline_names or not (scripts := install_scripts(node)):
            continue
        findings.append(
            _install_script_finding(
                current,
                node,
                rule_id="install-script-present",
                severity="medium",
                priority=65,
                title="New dependency runs an install script",
                explanation=(
                    f"{node.id} is new to this lockfile and runs install lifecycle script(s) ({', '.join(scripts)}). "
                    "Many legitimate packages do (e.g. native builds), but the script should be reviewed."
                ),
                scripts=scripts,
                extra={},
                observed_at=observed_at,
            )
        )
    return findings


LOCKFILE_INSTALL_SCRIPT = "declared in lockfile"


def install_scripts(node: GraphNode) -> list[str] | None:
    """Install lifecycle scripts a release runs: npm registry data when available, else the lockfile's
    `hasInstallScript` flag (which names no script). None means unknown."""
    if node.registry.install_scripts is not None:
        return list(node.registry.install_scripts)
    return [LOCKFILE_INSTALL_SCRIPT] if node.lockfile_install_script else None


def _install_script_finding(
    current: ScanGraph,
    node: GraphNode,
    *,
    rule_id: str,
    severity: str,
    priority: int,
    title: str,
    explanation: str,
    scripts: list[str],
    extra: dict,
    observed_at: datetime,
) -> Finding:
    return Finding(
        id=_finding_id(current.scan_id, rule_id, node.id),
        rule_id=rule_id,
        package=node.name,
        version=node.version,
        severity=severity,
        confidence="high",
        priority_score=priority,
        title=title,
        explanation=explanation,
        evidence=[
            FindingEvidence(
                source="npm-registry",
                field="scripts",
                value={"install_scripts": scripts, **extra},
                observed_at=observed_at,
            )
        ],
        paths=_dependency_paths(current, node.id),
    )


def detect_provenance_regressions(
    baseline: ScanGraph,
    current: ScanGraph,
    *,
    observed_at: datetime,
) -> list[Finding]:
    """Flag updates that drop npm build provenance their predecessor had.

    A package that publishes from CI with provenance and then ships a release without it may have
    been published from somewhere else, e.g. a stolen token on a laptop.
    """
    comparison = compare_graphs(baseline, current)
    baseline_nodes = {node.id: node for node in baseline.nodes}
    current_nodes = {node.id: node for node in current.nodes}
    findings: list[Finding] = []
    for change in comparison.version_changes:
        attested = [
            version
            for version in change.from_versions
            if (node := baseline_nodes.get(f"{change.name}@{version}")) is not None and node.registry.has_provenance
        ]
        if not attested:
            continue
        for version in change.to_versions:
            node = current_nodes.get(f"{change.name}@{version}")
            if node is None or node.registry.has_provenance is not False:
                continue
            findings.append(
                Finding(
                    id=_finding_id(current.scan_id, "provenance-removed", node.id),
                    rule_id="provenance-removed",
                    package=node.name,
                    version=node.version,
                    severity="medium",
                    confidence="medium",
                    priority_score=70,
                    title="Release no longer has build provenance",
                    explanation=(
                        f"{', '.join(f'{change.name}@{v}' for v in attested)} was published with an npm provenance "
                        f"attestation, but {node.id} was not. Confirm the release was published by the project's usual pipeline."
                    ),
                    evidence=[
                        FindingEvidence(
                            source="npm-registry",
                            field="dist.attestations",
                            value={"attested_versions": attested, "to_version": version, "has_provenance": False},
                            observed_at=observed_at,
                        )
                    ],
                    paths=_dependency_paths(current, node.id),
                )
            )
    return findings


def detect_deprecated_releases(
    current: ScanGraph,
    node_ids: set[str],
    *,
    observed_at: datetime,
) -> list[Finding]:
    """Flag the given releases that npm marks as deprecated (scoped by the caller, e.g. to a PR's changes)."""
    findings: list[Finding] = []
    for node in current.nodes:
        if node.id not in node_ids or not node.registry.deprecated:
            continue
        findings.append(
            Finding(
                id=_finding_id(current.scan_id, "deprecated-package", node.id),
                rule_id="deprecated-package",
                package=node.name,
                version=node.version,
                severity="low",
                confidence="high",
                priority_score=40,
                title="Release is deprecated",
                explanation=f"npm marks {node.id} as deprecated: {node.registry.deprecated}",
                evidence=[
                    FindingEvidence(
                        source="npm-registry",
                        field="deprecated",
                        value={"message": node.registry.deprecated},
                        observed_at=observed_at,
                    )
                ],
                paths=_dependency_paths(current, node.id),
            )
        )
    return findings


def _dependency_paths(graph: ScanGraph, target_id: str) -> list[list[str]]:
    if target_id not in {node.id for node in graph.nodes}:
        return []
    dependency_graph = nx.DiGraph((edge.source, edge.target) for edge in graph.edges)
    dependency_graph.add_nodes_from(node.id for node in graph.nodes)
    direct_nodes = sorted(node.id for node in graph.nodes if node.direct)
    paths: list[list[str]] = []
    for direct_id in direct_nodes:
        try:
            path = nx.shortest_path(dependency_graph, direct_id, target_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
        paths.append(["root", *path])
    return paths


def _advisory_risk(advisories: tuple[OsvAdvisory, ...]) -> tuple[str, int]:
    severities = {advisory.severity for advisory in advisories}
    if "critical" in severities:
        return "high", 95
    if "high" in severities:
        return "high", 90
    if severities & {"medium", "moderate"}:
        return "medium", 75
    if "low" in severities:
        return "low", 55
    return "medium", 65


def _finding_id(scan_id: str, rule_id: str, node_id: str) -> str:
    return str(uuid.uuid5(FINDING_NAMESPACE, f"{scan_id}:{rule_id}:{node_id}"))


def _parse_registry_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None