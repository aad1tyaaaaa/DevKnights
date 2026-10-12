from app.graph.comparison import compare_graphs
from app.models.schemas import GraphEdge, GraphNode, RegistryMetadataResponse, ScanGraph


UNKNOWN = RegistryMetadataResponse(status="unavailable", error="not fetched")


def node(name: str, version: str) -> GraphNode:
    return GraphNode(
        id=f"{name}@{version}",
        name=name,
        version=version,
        direct=False,
        lockfile_paths=[f"node_modules/{name}"],
        registry=UNKNOWN,
    )


def test_compare_graphs_reports_additions_removals_upgrades_and_new_edges():
    baseline = ScanGraph(
        scan_id="baseline",
        status="complete",
        nodes=[node("parent", "1.0.0"), node("old", "1.0.0"), node("shared", "1.0.0")],
        edges=[GraphEdge(source="parent@1.0.0", target="shared@1.0.0", type="prod")],
    )
    current = ScanGraph(
        scan_id="current",
        status="complete",
        nodes=[node("parent", "1.0.0"), node("new", "1.0.0"), node("shared", "2.0.0")],
        edges=[
            GraphEdge(source="parent@1.0.0", target="shared@2.0.0", type="prod"),
            GraphEdge(source="parent@1.0.0", target="new@1.0.0", type="optional"),
        ],
    )

    comparison = compare_graphs(baseline, current)

    assert comparison.added_packages == ("new@1.0.0", "shared@2.0.0")
    assert comparison.removed_packages == ("old@1.0.0", "shared@1.0.0")
    assert comparison.version_changes[0].name == "shared"
    assert comparison.version_changes[0].from_versions == ("1.0.0",)
    assert comparison.version_changes[0].to_versions == ("2.0.0",)
    assert {(edge.source, edge.target, edge.type) for edge in comparison.added_edges} == {
        ("parent@1.0.0", "shared@2.0.0", "prod"),
        ("parent@1.0.0", "new@1.0.0", "optional"),
    }


def test_compare_graphs_is_empty_for_identical_snapshots():
    graph = ScanGraph(scan_id="scan", status="complete", nodes=[node("pkg", "1.0.0")])

    comparison = compare_graphs(graph, graph)

    assert comparison.added_packages == ()
    assert comparison.removed_packages == ()
    assert comparison.version_changes == ()
    assert comparison.added_edges == ()