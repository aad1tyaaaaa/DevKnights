from datetime import datetime, timezone

from app.detection.osv import OsvAdvisory
from app.detection.rules import (
    detect_deprecated_releases,
    detect_graph_changes,
    detect_known_vulnerabilities,
    detect_publisher_changes,
    detect_unusual_release_timing,
)
from app.models.schemas import GraphEdge, GraphNode, RegistryMetadataResponse, ScanGraph


OBSERVED_AT = datetime(2026, 10, 12, tzinfo=timezone.utc)
UNKNOWN = RegistryMetadataResponse(status="unavailable", error="not fetched")


def node(name: str, version: str, *, direct: bool = False, publisher: str | None = None) -> GraphNode:
    return GraphNode(
        id=f"{name}@{version}",
        name=name,
        version=version,
        direct=direct,
        lockfile_paths=[f"node_modules/{name}"],
        registry=(
            RegistryMetadataResponse(status="available", publisher=publisher)
            if publisher is not None
            else UNKNOWN
        ),
    )


def graph(scan_id: str, nodes: list[GraphNode], edges: list[GraphEdge] | None = None) -> ScanGraph:
    return ScanGraph(scan_id=scan_id, status="complete", nodes=nodes, edges=edges or [])


def test_new_transitive_dependency_has_evidence_and_blast_radius_path():
    baseline = graph("baseline", [node("app-dep", "1.0.0", direct=True)])
    current = graph(
        "current",
        [node("app-dep", "1.0.0", direct=True), node("new-child", "2.0.0")],
        [GraphEdge(source="app-dep@1.0.0", target="new-child@2.0.0", type="prod")],
    )

    findings = detect_graph_changes(baseline, current, observed_at=OBSERVED_AT)
    new_dependency = next(finding for finding in findings if finding.rule_id == "new-dependency")

    assert new_dependency.severity == "info"
    assert new_dependency.confidence == "high"
    assert new_dependency.evidence[0].value["baseline_scan_id"] == "baseline"
    assert new_dependency.paths == [["root", "app-dep@1.0.0", "new-child@2.0.0"]]


def test_added_edges_are_grouped_into_one_scored_expansion_finding():
    baseline = graph("baseline", [node("parent", "1.0.0", direct=True)])
    current = graph(
        "current",
        [node("parent", "1.0.0", direct=True), node("a", "1.0.0"), node("b", "1.0.0")],
        [
            GraphEdge(source="parent@1.0.0", target="a@1.0.0", type="prod"),
            GraphEdge(source="parent@1.0.0", target="b@1.0.0", type="optional"),
        ],
    )

    findings = detect_graph_changes(baseline, current, observed_at=OBSERVED_AT)
    expansion = next(finding for finding in findings if finding.rule_id == "dependency-expansion")

    assert expansion.package == "parent"
    assert expansion.priority_score == 45
    assert len(expansion.evidence[0].value["edges"]) == 2
    assert expansion.paths == [["root", "parent@1.0.0"]]


def test_normal_version_only_upgrade_does_not_create_a_risk_finding():
    baseline = graph("baseline", [node("pkg", "1.0.0", direct=True)])
    current = graph("current", [node("pkg", "2.0.0", direct=True)])

    assert detect_graph_changes(baseline, current, observed_at=OBSERVED_AT) == []


def test_known_vulnerability_is_detected_without_a_baseline():
    current = graph("current", [node("minimist", "1.2.5", direct=True)])

    findings = detect_known_vulnerabilities(
        current,
        advisories={
            ("minimist", "1.2.5"): (
                OsvAdvisory(
                    id="GHSA-test-1234",
                    aliases=("CVE-2026-0001",),
                    summary="Synthetic advisory",
                    severity="high",
                ),
            )
        },
        observed_at=OBSERVED_AT,
    )

    assert len(findings) == 1
    assert findings[0].rule_id == "known-vulnerability"
    assert findings[0].severity == "high"
    assert findings[0].confidence == "high"
    assert findings[0].priority_score == 90
    assert findings[0].paths == [["root", "minimist@1.2.5"]]
    assert findings[0].evidence[0].source == "osv"


def test_publisher_change_uses_release_specific_registry_evidence():
    baseline = graph("baseline", [node("pkg", "1.0.0", direct=True, publisher="original")])
    current = graph("current", [node("pkg", "2.0.0", direct=True, publisher="new-owner")])

    findings = detect_publisher_changes(baseline, current, observed_at=OBSERVED_AT)

    assert len(findings) == 1
    assert findings[0].rule_id == "publisher-change"
    assert findings[0].priority_score == 60
    assert findings[0].evidence[0].value == {
        "from_versions": ["1.0.0"],
        "previous_publishers": ["original"],
        "to_version": "2.0.0",
        "current_publisher": "new-owner",
    }
    assert findings[0].paths == [["root", "pkg@2.0.0"]]


def test_publisher_change_does_not_guess_when_evidence_is_missing_or_unchanged():
    baseline = graph("baseline", [node("pkg", "1.0.0", direct=True, publisher="owner")])
    missing = graph("missing", [node("pkg", "2.0.0", direct=True)])
    unchanged = graph("unchanged", [node("pkg", "2.0.0", direct=True, publisher="owner")])

    assert detect_publisher_changes(baseline, missing, observed_at=OBSERVED_AT) == []
    assert detect_publisher_changes(baseline, unchanged, observed_at=OBSERVED_AT) == []


def test_finding_ids_and_order_are_deterministic():
    baseline = graph("baseline", [])
    current = graph("current", [node("z-package", "1.0.0"), node("a-package", "1.0.0", direct=True)])

    first = detect_graph_changes(baseline, current, observed_at=OBSERVED_AT)
    second = detect_graph_changes(baseline, current, observed_at=OBSERVED_AT)

    assert [finding.id for finding in first] == [finding.id for finding in second]
    assert [finding.package for finding in first] == ["a-package", "z-package"]


def test_unusual_release_timing_uses_registry_history_for_changed_versions():
    baseline = graph("baseline", [node("pkg", "1.0.0", direct=True)])
    current = graph("current", [node("pkg", "2.0.0", direct=True)])

    findings = detect_unusual_release_timing(
        baseline,
        current,
        release_times={
            "pkg": {
                "1.0.0": "2026-10-12T10:00:00.000Z",
                "2.0.0": "2026-10-12T10:15:00.000Z",
            }
        },
        observed_at=OBSERVED_AT,
    )

    assert len(findings) == 1
    assert findings[0].rule_id == "unusual-release-timing"
    assert findings[0].confidence == "medium"
    assert findings[0].evidence[0].value["interval_seconds"] == 900


def test_release_timing_does_not_guess_when_history_is_missing_or_normal():
    baseline = graph("baseline", [node("pkg", "1.0.0", direct=True)])
    current = graph("current", [node("pkg", "2.0.0", direct=True)])

    assert detect_unusual_release_timing(
        baseline, current, release_times={"pkg": None}, observed_at=OBSERVED_AT
    ) == []
    assert detect_unusual_release_timing(
        baseline,
        current,
        release_times={
            "pkg": {"1.0.0": "2026-10-10T10:00:00Z", "2.0.0": "2026-10-12T10:00:00Z"}
        },
        observed_at=OBSERVED_AT,
    ) == []

def test_version_update_only_counts_genuinely_new_dependencies_as_expansion():
    baseline = graph(
        "baseline",
        [node("express", "4.18.2", direct=True), node("body-parser", "1.0.0")],
        [GraphEdge(source="express@4.18.2", target="body-parser@1.0.0", type="prod")],
    )
    current = graph(
        "current",
        [node("express", "4.18.3", direct=True), node("body-parser", "1.0.0"), node("helper", "1.0.0")],
        [
            GraphEdge(source="express@4.18.3", target="body-parser@1.0.0", type="prod"),
            GraphEdge(source="express@4.18.3", target="helper@1.0.0", type="prod"),
        ],
    )

    expansion = next(f for f in detect_graph_changes(baseline, current, observed_at=OBSERVED_AT) if f.rule_id == "dependency-expansion")

    assert expansion.evidence[0].value["edges"] == [{"from": "express@4.18.3", "to": "helper@1.0.0", "type": "prod"}]


def test_deprecated_rule_only_reports_the_requested_releases():
    deprecated = RegistryMetadataResponse(status="available", deprecated="Use v2")
    current = graph(
        "current",
        [
            GraphNode(id="old@1.0.0", name="old", version="1.0.0", direct=True, lockfile_paths=[], registry=deprecated),
            GraphNode(id="legacy@1.0.0", name="legacy", version="1.0.0", direct=True, lockfile_paths=[], registry=deprecated),
        ],
    )

    findings = detect_deprecated_releases(current, {"old@1.0.0"}, observed_at=OBSERVED_AT)

    assert [(f.package, f.rule_id, f.severity) for f in findings] == [("old", "deprecated-package", "low")]
