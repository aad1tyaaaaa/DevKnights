"""Evidence-grounded explanations and deterministic remediation advice."""

from __future__ import annotations

from typing import Iterable

from app.graph.impact import analyze_blast_radius
from app.models.schemas import Finding, RemediationRecommendation, ScanGraph, ThreatExplanation


def enrich_findings(
    findings: Iterable[Finding],
    graph: ScanGraph,
    *,
    max_paths: int = 25,
    max_depth: int = 20,
    max_upstream_dependents: int = 100,
) -> list[Finding]:
    enriched: list[Finding] = []
    for finding in findings:
        node_id = f"{finding.package}@{finding.version}"
        impact = analyze_blast_radius(
            graph,
            node_id,
            max_paths=max_paths,
            max_depth=max_depth,
            max_upstream_dependents=max_upstream_dependents,
        )
        enriched.append(
            finding.model_copy(
                update={
                    "threat_explanation": deterministic_explanation(finding),
                    "remediation": remediation_for(finding),
                    "blast_radius": impact,
                    # Preserve the long-standing paths field for dashboard/extension compatibility.
                    "paths": impact.paths,
                }
            )
        )
    return enriched


def deterministic_explanation(finding: Finding) -> ThreatExplanation:
    return ThreatExplanation(
        source="deterministic",
        what_was_detected=finding.title,
        why_it_may_be_risky=finding.explanation,
        evidence_summary=_evidence_summary(finding),
        uncertainty=_uncertainty(finding.rule_id),
        investigation_steps=[recommendation.action for recommendation in remediation_for(finding)],
    )


def remediation_for(finding: Finding) -> list[RemediationRecommendation]:
    rule = finding.rule_id
    if rule == "possible-typosquatting":
        return [
            _recommend("Verify the intended package name against the project manifest and upstream documentation.", "A near-match can result from a typing error or intentional impersonation."),
            _recommend("Review npm ownership, release history, and repository links before installation.", "Name similarity alone cannot establish package identity.", "medium"),
            _recommend("Remove or replace the dependency if the package name was unintended.", "An unintended dependency should not remain in the lockfile."),
        ]
    if rule in {"install-script-added", "install-script-present", "install-time-process-execution", "suspicious-install-time-behavior"}:
        return [
            _recommend("Inspect the declared preinstall, install, and postinstall commands and every referenced file.", "Lifecycle scripts execute during dependency installation."),
            _recommend("Compare the artifact with the previously approved release and investigate unexpected process or network activity.", "A newly introduced execution path deserves release-specific review.", "medium"),
            _recommend("Test in an isolated environment with lifecycle scripts disabled before approval.", "Isolation reduces exposure while the behavior is investigated.", "medium"),
        ]
    if rule == "known-vulnerability":
        fixed_versions = _known_fixed_versions(finding)
        action = (
            f"Upgrade to a version explicitly listed as fixed by the advisory: {', '.join(fixed_versions)}."
            if fixed_versions
            else "Review the referenced OSV advisories and identify a version they explicitly mark as fixed."
        )
        return [
            _recommend(action, "The finding matches an advisory for the exact installed release.", limitation=None if fixed_versions else "No fixed version was verified in the collected evidence; do not assume another version is safe."),
            _recommend("Assess whether the vulnerable package is reachable in the application's runtime or build path.", "Dependency reachability does not prove exploitability.", "medium"),
        ]
    if rule in {"publisher-change", "maintainer-change"}:
        return [
            _recommend("Verify the publisher or maintainer change through the package's official project channels.", "Ownership changes can be legitimate but should be independently confirmed."),
            _recommend("Compare this artifact and changelog with the previously approved release.", "Release-specific differences can clarify whether the change is expected.", "medium"),
        ]
    if rule == "provenance-removed":
        return [_recommend("Confirm that the release came from the project's expected build and publishing workflow.", "The prior release had provenance but the current release does not.", "medium")]
    if rule in {"possible-credential-exfiltration", "potential-credential-access", "dynamic-code-execution", "obfuscated-dynamic-code", "obfuscation-indicator"}:
        return [
            _recommend("Review the reported file and surrounding control/data flow without executing the package.", "Static indicators need contextual source review."),
            _recommend("Determine whether sensitive data can reach an outbound request or dynamic execution sink.", "Correlation is more informative than either indicator alone.", "medium"),
        ]
    if rule in {"release-anchor-mismatch", "blockchain-mismatch"}:
        return [_recommend("Stop approval and investigate why the release metadata differs from the anchored record.", "A mismatch means the observed release is not identical to the approved record.")]
    if rule == "unusual-release-timing":
        return [_recommend("Review the release history and confirm the rapid publication was expected by maintainers.", "Rapid releases are a heuristic and can be legitimate.", "medium")]
    if rule in {"new-dependency", "dependency-expansion"}:
        return [_recommend("Review why the new package or dependency edge is required and confirm its source and ownership.", "New dependency reachability expands the project's supply-chain surface.", "medium")]
    if rule == "deprecated-package":
        return [_recommend("Follow the package's deprecation guidance and plan a supported replacement.", "Deprecated packages may stop receiving fixes.", "high")]
    return [_recommend("Review the finding evidence and dependency path before approving the release.", "The rule identified a supply-chain investigation signal.", finding.confidence)]


def ai_evidence_projection(finding: Finding) -> dict:
    """Minimal provider payload: controlled labels only, never raw metadata or source contents."""
    return {
        "id": finding.id,
        "rule_id": finding.rule_id,
        "severity": finding.severity,
        "confidence": finding.confidence,
        "priority_score": finding.priority_score,
        "evidence": [
            {"index": index, "source": evidence.source, "field": evidence.field}
            for index, evidence in enumerate(finding.evidence[:20])
        ],
        "direct_dependency": bool(finding.blast_radius and finding.blast_radius.direct),
    }


def _recommend(
    action: str,
    rationale: str,
    confidence: str = "high",
    limitation: str | None = None,
) -> RemediationRecommendation:
    return RemediationRecommendation(
        action=action,
        rationale=rationale,
        confidence=confidence,
        limitation=limitation,
    )


def _evidence_summary(finding: Finding) -> list[str]:
    summaries: list[str] = []
    for evidence in finding.evidence:
        summary = f"{evidence.source}: {evidence.field}"
        value = evidence.value if isinstance(evidence.value, dict) else {}
        if finding.rule_id == "possible-typosquatting":
            similar_to = value.get("similar_to")
            distance = value.get("edit_distance")
            if isinstance(similar_to, str) and isinstance(distance, int):
                summary += f" (similar to {similar_to!r}, edit distance {distance})"
        elif evidence.source == "static-analysis":
            path = value.get("file_path")
            indicators = value.get("indicators")
            labels = [item.get("label") for item in indicators or [] if isinstance(item, dict) and isinstance(item.get("label"), str)]
            if isinstance(path, str):
                summary += f" in {path}"
            if labels:
                summary += f" ({', '.join(labels[:5])})"
        elif evidence.source == "osv":
            identifiers = value.get("identifiers")
            if isinstance(identifiers, list):
                summary += f" ({', '.join(str(identifier) for identifier in identifiers[:5])})"
        summaries.append(summary[:500])
    return summaries[:20]


def _uncertainty(rule_id: str) -> str:
    if rule_id == "known-vulnerability":
        return "An advisory match confirms reported vulnerability data for this release, not exploitation in this project."
    if rule_id.startswith("possible-") or rule_id in {"obfuscation-indicator", "unusual-release-timing"}:
        return "This is a heuristic indicator and can have legitimate explanations; it does not prove malicious intent."
    if rule_id in {"publisher-change", "maintainer-change"}:
        return "Observed registry snapshots can show a change but are not an authoritative historical ownership ledger."
    if "install" in rule_id or "dynamic" in rule_id:
        return "The detected API or lifecycle behavior can be legitimate; source context and reachability require review."
    return "The evidence establishes the reported condition, but dependency reachability does not prove runtime execution or compromise."


def _known_fixed_versions(finding: Finding) -> list[str]:
    versions: set[str] = set()
    for evidence in finding.evidence:
        if evidence.source != "osv" or not isinstance(evidence.value, dict):
            continue
        value = evidence.value.get("fixed_versions")
        if isinstance(value, list):
            versions.update(version for version in value if isinstance(version, str) and version)
    return sorted(versions)
