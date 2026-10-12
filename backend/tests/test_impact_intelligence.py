from datetime import datetime, timezone

from app.detection.intelligence import deterministic_explanation, enrich_findings, remediation_for
from app.graph.impact import analyze_blast_radius
from app.models.schemas import Finding, FindingEvidence, GraphEdge, GraphNode, RegistryMetadataResponse, ScanGraph


NOW = datetime(2026, 10, 13, tzinfo=timezone.utc)
UNKNOWN = RegistryMetadataResponse(status="unavailable", error="offline")


def node(node_id: str, *, direct: bool = False) -> GraphNode:
    name, version = node_id.rsplit("@", 1)
    return GraphNode(
        id=node_id,
        name=name,
        version=version,
        direct=direct,
        lockfile_paths=[f"node_modules/{name}"],
        registry=UNKNOWN,
    )


def graph(node_ids: list[tuple[str, bool]], edges: list[tuple[str, str]]) -> ScanGraph:
    return ScanGraph(
        scan_id="scan",
        status="complete",
        nodes=[node(node_id, direct=direct) for node_id, direct in node_ids],
        edges=[GraphEdge(source=source, target=target, type="prod") for source, target in edges],
    )


def finding(rule_id: str = "possible-typosquatting", *, package: str = "expres", version: str = "1.0.0") -> Finding:
    return Finding(
        id="finding",
        rule_id=rule_id,
        package=package,
        version=version,
        severity="medium",
        confidence="medium",
        priority_score=70,
        title="Synthetic finding",
        explanation="The deterministic rule found a review signal.",
        evidence=[FindingEvidence(source="lockfile", field="test", value=True, observed_at=NOW)],
    )


def test_blast_radius_reports_multiple_paths_introducers_and_shortest_path():
    current = graph(
        [("a@1.0.0", True), ("b@1.0.0", True), ("middle@1.0.0", False), ("risk@2.0.0", False)],
        [
            ("a@1.0.0", "middle@1.0.0"),
            ("middle@1.0.0", "risk@2.0.0"),
            ("b@1.0.0", "risk@2.0.0"),
        ],
    )
    impact = analyze_blast_radius(current, "risk@2.0.0")

    assert impact.direct is False
    assert impact.reachable is True
    assert impact.shortest_path == ["root", "b@1.0.0", "risk@2.0.0"]
    assert impact.introducing_direct_dependencies == ["a@1.0.0", "b@1.0.0"]
    assert impact.affected_package_count == 4
    assert impact.branch_path_counts == {"a@1.0.0": 1, "b@1.0.0": 1}
    assert "not runtime code execution" in impact.affected_package_definition


def test_cycles_do_not_repeat_nodes_or_prevent_reachability():
    current = graph(
        [("a@1.0.0", True), ("loop@1.0.0", False), ("risk@1.0.0", False)],
        [("a@1.0.0", "loop@1.0.0"), ("loop@1.0.0", "a@1.0.0"), ("loop@1.0.0", "risk@1.0.0")],
    )
    impact = analyze_blast_radius(current, "risk@1.0.0")
    assert impact.paths == [["root", "a@1.0.0", "loop@1.0.0", "risk@1.0.0"]]


def test_multiple_versions_use_exact_node_identity():
    current = graph(
        [("a@1.0.0", True), ("b@1.0.0", True), ("shared@1.0.0", False), ("shared@2.0.0", False)],
        [("a@1.0.0", "shared@1.0.0"), ("b@1.0.0", "shared@2.0.0")],
    )
    impact = analyze_blast_radius(current, "shared@2.0.0")
    assert impact.introducing_direct_dependencies == ["b@1.0.0"]
    assert impact.paths == [["root", "b@1.0.0", "shared@2.0.0"]]


def test_large_path_enumeration_is_bounded_and_marked_truncated():
    nodes = [("root-dep@1.0.0", True), ("risk@1.0.0", False)]
    edges: list[tuple[str, str]] = []
    for index in range(10):
        branch = f"branch-{index}@1.0.0"
        nodes.append((branch, False))
        edges.extend([("root-dep@1.0.0", branch), (branch, "risk@1.0.0")])
    impact = analyze_blast_radius(graph(nodes, edges), "risk@1.0.0", max_paths=3)
    assert len(impact.paths) == 3
    assert impact.paths_truncated is True
    assert impact.affected_package_count == 12


def test_depth_limit_reports_truncation_but_reachability_and_shortest_path_remain_available():
    current = graph(
        [("a@1.0.0", True), ("b@1.0.0", False), ("c@1.0.0", False), ("risk@1.0.0", False)],
        [("a@1.0.0", "b@1.0.0"), ("b@1.0.0", "c@1.0.0"), ("c@1.0.0", "risk@1.0.0")],
    )
    impact = analyze_blast_radius(current, "risk@1.0.0", max_depth=1)
    assert impact.reachable is True
    assert impact.paths == []
    assert impact.paths_truncated is True
    assert impact.shortest_path == ["root", "a@1.0.0", "b@1.0.0", "c@1.0.0", "risk@1.0.0"]


def test_enrichment_adds_deterministic_explanation_remediation_and_impact():
    current = graph([("expres@1.0.0", True)], [])
    enriched = enrich_findings([finding()], current)[0]
    assert enriched.threat_explanation is not None
    assert enriched.threat_explanation.source == "deterministic"
    assert enriched.remediation[0].action.startswith("Verify the intended package name")
    assert enriched.blast_radius is not None and enriched.blast_radius.direct is True
    assert enriched.paths == [["root", "expres@1.0.0"]]


def test_vulnerability_remediation_does_not_invent_a_fixed_version():
    vulnerable = finding("known-vulnerability", package="pkg")
    explanation = deterministic_explanation(vulnerable)
    recommendations = remediation_for(vulnerable)
    assert "not exploitation" in explanation.uncertainty
    assert recommendations[0].limitation is not None
    assert "No fixed version was verified" in recommendations[0].limitation
    assert "safe" in recommendations[0].limitation

    with_fix = vulnerable.model_copy(
        update={
            "evidence": [
                FindingEvidence(
                    source="osv",
                    field="advisories",
                    value={"fixed_versions": ["1.2.4"]},
                    observed_at=NOW,
                )
            ]
        }
    )
    fixed = remediation_for(with_fix)[0]
    assert "1.2.4" in fixed.action
    assert fixed.limitation is None


def test_remediation_mappings_are_specific_for_publisher_and_install_rules():
    publisher = remediation_for(finding("publisher-change"))
    install = remediation_for(finding("suspicious-install-time-behavior"))
    assert "publisher" in publisher[0].action.lower()
    assert "preinstall" in install[0].action.lower()
