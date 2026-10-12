from datetime import datetime, timezone

from app.detection.typosquatting import damerau_levenshtein, detect_typosquatting, normalize_package_name
from app.models.schemas import GraphNode, RegistryMetadataResponse, ScanGraph


NOW = datetime(2026, 10, 13, tzinfo=timezone.utc)


def graph(name: str) -> ScanGraph:
    return ScanGraph(
        scan_id="scan",
        status="complete",
        nodes=[
            GraphNode(
                id=f"{name}@1.0.0",
                name=name,
                version="1.0.0",
                direct=True,
                lockfile_paths=[f"node_modules/{name}"],
                registry=RegistryMetadataResponse(status="available", publisher="publisher"),
            )
        ],
    )


def findings(name: str, trusted: tuple[str, ...] = ("express",)):
    current = graph(name)
    return detect_typosquatting(
        current,
        candidate_ids={current.nodes[0].id},
        observed_at=NOW,
        trusted_packages=trusted,
    )


def test_exact_trusted_name_is_not_flagged():
    assert findings("express") == []


def test_deletion_and_transposition_are_detected():
    deletion = findings("expres")[0]
    transposition = findings("exrpess")[0]
    assert deletion.evidence[0].value["edit_distance"] == 1
    assert transposition.evidence[0].value["transformation"] == "an adjacent-character transposition"


def test_similar_but_legitimate_name_outside_threshold_is_not_flagged():
    assert findings("express-session") == []


def test_scoped_packages_only_compare_inside_the_same_scope():
    assert findings("@angular/croe", ("@angular/core",))[0].evidence[0].value["similar_to"] == "@angular/core"
    assert findings("@other/croe", ("@angular/core",)) == []


def test_malformed_empty_and_case_normalization():
    assert normalize_package_name("") == (None, None)
    assert normalize_package_name("not valid") == (None, None)
    assert normalize_package_name("EXPRESS") == ("", "express")
    assert findings("EXPRESS") == []


def test_hyphen_and_damerau_distance_support():
    assert damerau_levenshtein("raect", "react") == 1
    hit = findings("ex-press")
    assert hit and hit[0].evidence[0].value["transformation"] == "a hyphen insertion or removal"
    assert hit[0].evidence[0].value["edit_distance"] == 1


def test_detector_requires_candidate_context():
    current = graph("expres")
    assert detect_typosquatting(current, candidate_ids=set(), observed_at=NOW) == []
