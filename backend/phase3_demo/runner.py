"""Reusable before/after runner for the safe Phase 3 scenarios."""

from __future__ import annotations

from typing import Any, Iterable, Literal

import httpx
from pydantic import BaseModel, Field

from app.detection.osv import OsvAdvisory
from app.detection.static_analysis import StaticArtifactInspector
from app.gate import TrustGate
from app.models.database import ScanRepository
from app.models.schemas import (
    BlastRadiusAnalysis,
    Finding,
    FindingEvidence,
    GateReport,
    RemediationRecommendation,
    ThreatExplanation,
    VersionChangeResponse,
)
from app.parsers.npm_registry import RegistryMetadata
from app.services import ScanService
from phase3_demo.scenarios import SCENARIOS, ScenarioDefinition


class ScenarioState(BaseModel):
    status: Literal["complete"]
    dependencies: list[str]
    finding_count: int
    warnings: list[str] = Field(default_factory=list)


class ScenarioChanges(BaseModel):
    added: list[str]
    removed: list[str]
    updated: list[VersionChangeResponse]


class DemoFinding(BaseModel):
    rule_id: str
    package: str
    version: str
    severity: str
    confidence: str
    priority_score: int
    ranking_source: str
    title: str
    explanation: str
    evidence: list[FindingEvidence]
    paths: list[list[str]]
    threat_explanation: ThreatExplanation | None
    remediation: list[RemediationRecommendation]
    blast_radius: BlastRadiusAnalysis | None

    @classmethod
    def from_finding(cls, finding: Finding) -> "DemoFinding":
        return cls.model_validate(finding.model_dump(exclude={"id", "ai_priority_score", "ai_rationale"}))


class PriorityChange(BaseModel):
    rule_id: str
    package: str
    baseline_version: str | None = None
    modified_version: str | None = None
    baseline_priority: int | None = None
    modified_priority: int | None = None


class ScenarioReport(BaseModel):
    scenario: str
    title: str
    description: str
    synthetic: Literal[True] = True
    baseline: ScenarioState
    modified: ScenarioState
    changes: ScenarioChanges
    new_findings: list[DemoFinding]
    resolved_findings: list[DemoFinding]
    risk_priority_changes: list[PriorityChange]
    dependency_paths: dict[str, list[list[str]]]
    blast_radius_summary: list[BlastRadiusAnalysis]
    remediation_recommendations: list[RemediationRecommendation]
    gate_verdict: str
    gate: GateReport
    evidence_sources: list[str]
    analysis_limitations: list[str]


class FixtureRegistry:
    """Minimal registry adapter backed only by exact synthetic release snapshots."""

    def __init__(self, values: dict[tuple[str, str], RegistryMetadata]) -> None:
        self.values = values

    async def fetch_many(self, releases: Iterable[tuple[str, str]]) -> dict[tuple[str, str], RegistryMetadata]:
        return {
            release: self.values.get(release)
            or RegistryMetadata(
                package=release[0],
                version=release[1],
                status="unavailable",
                error="Synthetic fixture intentionally has no metadata snapshot",
            )
            for release in dict.fromkeys(releases)
        }

    async def fetch_release_times_many(self, packages: Iterable[str]) -> dict[str, None]:
        return {package: None for package in dict.fromkeys(packages)}


class OfflineOsv:
    async def fetch_many(
        self, releases: Iterable[tuple[str, str]]
    ) -> dict[tuple[str, str], tuple[OsvAdvisory, ...]]:
        return {release: () for release in dict.fromkeys(releases)}


def build_services(
    scenario: ScenarioDefinition,
    database_url: str,
) -> tuple[ScanService, TrustGate]:
    registry = FixtureRegistry(scenario.metadata)
    inspector = _static_inspector(scenario.archives) if scenario.archives else None
    osv = OfflineOsv()
    service = ScanService(
        ScanRepository(database_url),
        registry,  # type: ignore[arg-type]
        osv=osv,  # type: ignore[arg-type]
        static_inspector=inspector,
        ai_ranking_enabled=False,
        ai_explanations_enabled=False,
    )
    gate = TrustGate(
        registry,  # type: ignore[arg-type]
        osv=osv,  # type: ignore[arg-type]
        static_inspector=inspector,
    )
    return service, gate


async def run_scenario(
    scenario: str | ScenarioDefinition,
    *,
    database_url: str | None = None,
) -> ScenarioReport:
    definition = SCENARIOS[scenario] if isinstance(scenario, str) else scenario
    return await _run(definition, database_url or "sqlite://")


async def run_all_scenarios() -> list[ScenarioReport]:
    reports: list[ScenarioReport] = []
    for identifier in SCENARIOS:
        reports.append(await run_scenario(identifier))
    return reports


async def _run(definition: ScenarioDefinition, database_url: str) -> ScenarioReport:
    owner = "phase3-offline-demo"
    service, gate = build_services(definition, database_url)
    baseline_id = service.create_scan(definition.baseline, definition.project_name, owner)
    await service.analyze_scan(baseline_id)
    current_id = service.create_scan(definition.modified, definition.project_name, owner)
    await service.analyze_scan(current_id)

    baseline_row = service.repository.get(baseline_id)
    current_row = service.repository.get(current_id)
    if baseline_row is None or current_row is None or baseline_row.graph is None or current_row.graph is None:
        raise RuntimeError("Synthetic scan did not persist a complete graph")
    if baseline_row.status != "complete" or current_row.status != "complete":
        raise RuntimeError(f"Synthetic scan failed: {baseline_row.error or current_row.error}")

    baseline_findings = [Finding.model_validate(value) for value in service.repository.get_findings(baseline_id)]
    current_findings = [Finding.model_validate(value) for value in service.repository.get_findings(current_id)]
    comparison = service.compare_scans(baseline_id, current_id, owner)
    gate_report = await gate.evaluate(
        definition.modified,
        definition.baseline,
        fail_on="medium",
        label=f"synthetic:{definition.identifier}",
    )

    baseline_by_signature = {_signature(finding): finding for finding in baseline_findings}
    current_by_signature = {_signature(finding): finding for finding in current_findings}
    new = [current_by_signature[key] for key in sorted(current_by_signature.keys() - baseline_by_signature.keys())]
    resolved = [baseline_by_signature[key] for key in sorted(baseline_by_signature.keys() - current_by_signature.keys())]
    priorities = _priority_changes(baseline_findings, current_findings)
    evidence_sources = sorted({evidence.source for finding in new for evidence in finding.evidence})
    recommendations = _unique_recommendations(new)
    paths = {
        f"{finding.rule_id}:{finding.package}@{finding.version}": finding.paths
        for finding in new
        if finding.paths
    }
    impacts = [finding.blast_radius for finding in new if finding.blast_radius is not None]
    limitations = _unique(
        [
            "All packages, identities, metadata, advisories, and source snippets in this report are synthetic fixtures.",
            "No package was installed, imported, or executed; no live registry, OSV, Gemini, or blockchain service was used.",
            *definition.limitations,
            *baseline_row.warnings,
            *current_row.warnings,
            *gate_report.warnings,
        ]
    )
    return ScenarioReport(
        scenario=definition.identifier,
        title=definition.title,
        description=definition.description,
        baseline=ScenarioState(
            status="complete",
            dependencies=sorted(node["id"] for node in baseline_row.graph["nodes"]),
            finding_count=len(baseline_findings),
            warnings=baseline_row.warnings,
        ),
        modified=ScenarioState(
            status="complete",
            dependencies=sorted(node["id"] for node in current_row.graph["nodes"]),
            finding_count=len(current_findings),
            warnings=current_row.warnings,
        ),
        changes=ScenarioChanges(
            added=comparison.added_packages,
            removed=comparison.removed_packages,
            updated=comparison.version_changes,
        ),
        new_findings=[DemoFinding.from_finding(finding) for finding in new],
        resolved_findings=[DemoFinding.from_finding(finding) for finding in resolved],
        risk_priority_changes=priorities,
        dependency_paths=paths,
        blast_radius_summary=impacts,
        remediation_recommendations=recommendations,
        gate_verdict=gate_report.verdict,
        gate=gate_report,
        evidence_sources=evidence_sources,
        analysis_limitations=limitations,
    )


def _static_inspector(archives: dict[str, bytes]) -> StaticArtifactInspector:
    def handler(request: httpx.Request) -> httpx.Response:
        data = archives.get(str(request.url))
        return httpx.Response(200, content=data) if data is not None else httpx.Response(404)

    return StaticArtifactInspector(
        allowed_hosts={"registry.npmjs.org"},
        transport=httpx.MockTransport(handler),
    )


def _signature(finding: Finding) -> tuple[str, str, str]:
    return finding.rule_id, finding.package, finding.version


def _priority_changes(baseline: list[Finding], current: list[Finding]) -> list[PriorityChange]:
    old = {(finding.rule_id, finding.package): finding for finding in baseline}
    new = {(finding.rule_id, finding.package): finding for finding in current}
    changes: list[PriorityChange] = []
    for key in sorted(old.keys() | new.keys()):
        before, after = old.get(key), new.get(key)
        if before and after and before.priority_score == after.priority_score and before.version == after.version:
            continue
        changes.append(
            PriorityChange(
                rule_id=key[0],
                package=key[1],
                baseline_version=before.version if before else None,
                modified_version=after.version if after else None,
                baseline_priority=before.priority_score if before else None,
                modified_priority=after.priority_score if after else None,
            )
        )
    return changes


def _unique_recommendations(findings: list[Finding]) -> list[RemediationRecommendation]:
    values: dict[str, RemediationRecommendation] = {}
    for finding in findings:
        for recommendation in finding.remediation:
            values.setdefault(recommendation.action, recommendation)
    return [values[action] for action in sorted(values)]


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
