"""Pull request dependency trust gate.

Compares a pull request's npm lockfile with its base and examines only the releases the PR adds or
updates: OSV advisories, publisher changes, install scripts, build provenance, deprecation, release
timing and (when a chain is reachable) Provenyx release anchors. Optional bounded static inspection
downloads integrity-verified archives, but package code is never installed or executed.

    python -m app.gate --head package-lock.json [--base base-lock.json] [--fail-on high]
                       [--label frontend/package-lock.json] [--markdown report.md] [--json report.json]
                       [--no-osv] [--no-anchors]

Exit code: 1 when the verdict is "fail", 2 when a lockfile is invalid, otherwise 0.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import ValidationError

from app.blockchain.verify import ReleaseVerifier
from app.detection.osv import OsvClient
from app.detection.typosquatting import DEFAULT_TRUSTED_PACKAGES, detect_typosquatting
from app.detection.static_analysis import StaticAnalysisLimits, StaticArtifactInspector
from app.detection.rules import (
    _dependency_paths,
    detect_deprecated_releases,
    detect_graph_changes,
    detect_install_script_changes,
    detect_known_vulnerabilities,
    detect_provenance_regressions,
    detect_publisher_changes,
    detect_unusual_release_timing,
    correlate_publisher_risk,
    install_scripts,
)
from app.graph.comparison import compare_graphs
from app.models.schemas import (
    Finding,
    GateCheck,
    GateCheckStatus,
    GateRelease,
    GateReport,
    GateSummary,
    GateThreshold,
    GateVerdict,
    GraphNode,
    Lockfile,
    ScanGraph,
    VerificationResult,
)
from app.parsers.lockfile import parse_lockfile
from app.parsers.npm_registry import NpmRegistryClient
from app.services import build_scan_graph

COMMENT_MARKER = "<!-- provenyx-trust-gate"  # the report's first line; the GitHub Action updates the comment it starts
SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3}
THRESHOLD_RANK = {"high": 3, "medium": 2, "low": 1, "never": 99}
VERDICT_RANK = {"pass": 0, "warn": 1, "fail": 2}
MAX_DETAILED_RELEASES = 30
MAX_COMMENT_CHARS = 60_000  # GitHub rejects comments over 65,536 characters


class TrustGate:
    def __init__(
        self,
        registry: NpmRegistryClient,
        *,
        osv: OsvClient | None = None,
        verifier: ReleaseVerifier | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        trusted_packages: tuple[str, ...] | list[str] | None = None,
        static_inspector: StaticArtifactInspector | None = None,
        static_max_packages: int = 20,
    ) -> None:
        self.registry = registry
        self.osv = osv
        self.verifier = verifier
        self.clock = clock
        self.trusted_packages = tuple(trusted_packages or DEFAULT_TRUSTED_PACKAGES)
        self.static_inspector = static_inspector
        self.static_max_packages = max(1, static_max_packages)

    async def evaluate(
        self,
        head_lockfile: dict[str, Any],
        base_lockfile: dict[str, Any] | None = None,
        *,
        fail_on: GateThreshold = "high",
        label: str | None = None,
    ) -> GateReport:
        observed_at = self.clock()
        head_parsed = parse_lockfile(head_lockfile)
        base_parsed = parse_lockfile(base_lockfile) if base_lockfile is not None else None

        # Diff on structure first, so registry metadata is fetched only for what the PR changes.
        empty_base = ScanGraph(scan_id="pr-base", status="complete")
        head_shape = build_scan_graph("pr-head", head_parsed, {})
        base_shape = build_scan_graph("pr-base", base_parsed, {}) if base_parsed else empty_base
        comparison = compare_graphs(base_shape, head_shape)
        head_nodes = {node.id: node for node in head_shape.nodes}
        changed_ids = list(comparison.added_packages)
        changed_names = {head_nodes[node_id].name for node_id in changed_ids}
        changed_releases = [(head_nodes[node_id].name, head_nodes[node_id].version) for node_id in changed_ids]
        predecessor_releases = [(node.name, node.version) for node in base_shape.nodes if node.name in changed_names]
        head_names = {node.name for node in head_shape.nodes}
        # A replaced version is an update, not a removal; only packages gone entirely count as removed.
        removed = [node_id for node_id in comparison.removed_packages if _package_name(node_id) not in head_names]

        metadata = await self.registry.fetch_many([*changed_releases, *predecessor_releases])
        head = build_scan_graph("pr-head", head_parsed, metadata)
        base = build_scan_graph("pr-base", base_parsed, metadata) if base_parsed else empty_base
        # Lockfile resolution notes are only relevant to the PR when they concern a release it changed.
        notes = [note for note in head.warnings if any(node_id in note for node_id in changed_ids)]
        warnings: list[str] = []
        if base_parsed is None:
            warnings.append("No base lockfile was found, so every release is treated as newly added.")
        unavailable = sum(metadata[release].status != "available" for release in changed_releases)
        if unavailable:
            warnings.append(f"npm registry metadata was unavailable for {unavailable} changed release(s); their checks are incomplete.")

        findings: list[Finding] = [
            *detect_graph_changes(base, head, observed_at=observed_at),
            *detect_publisher_changes(base, head, observed_at=observed_at),
            *detect_install_script_changes(base, head, observed_at=observed_at),
            *detect_provenance_regressions(base, head, observed_at=observed_at),
            *detect_deprecated_releases(head, set(changed_ids), observed_at=observed_at),
        ]
        base_names = {node.name for node in base.nodes}
        typo_candidate_ids = {node_id for node_id in changed_ids if head_nodes[node_id].name not in base_names}
        findings.extend(
            detect_typosquatting(
                head,
                candidate_ids=typo_candidate_ids,
                observed_at=observed_at,
                trusted_packages=self.trusted_packages,
            )
        )
        if self.static_inspector is not None and changed_ids:
            risk_by_id: dict[str, int] = {}
            for finding in findings:
                node_id = f"{finding.package}@{finding.version}"
                risk_by_id[node_id] = max(risk_by_id.get(node_id, 0), finding.priority_score)
            selected = sorted(
                changed_ids,
                key=lambda node_id: (
                    -risk_by_id.get(node_id, 0),
                    not head_nodes[node_id].direct,
                    not bool(head_nodes[node_id].registry.install_scripts),
                    node_id,
                ),
            )[: self.static_max_packages]
            static_findings, static_warnings = await self.static_inspector.analyze(
                head, candidate_ids=selected, observed_at=observed_at
            )
            findings.extend(static_findings)
            warnings.extend(static_warnings)
        findings = correlate_publisher_risk(findings, observed_at=observed_at)
        if comparison.version_changes:
            release_times = await self.registry.fetch_release_times_many(change.name for change in comparison.version_changes)
            findings.extend(detect_unusual_release_timing(base, head, release_times=release_times, observed_at=observed_at))

        advisories: dict[tuple[str, str], Any] | None = None
        if self.osv is not None:
            advisories = await self.osv.fetch_many(changed_releases)
            missing = sum(result is None for result in advisories.values())
            if missing:
                warnings.append(f"OSV advisory lookup was unavailable for {missing} changed release(s); vulnerability status is unknown.")
            findings.extend(detect_known_vulnerabilities(head, advisories=advisories, observed_at=observed_at))

        anchors = await self._verify_anchors(changed_releases, warnings)

        by_release: dict[str, list[Finding]] = {}
        for finding in findings:
            by_release.setdefault(f"{finding.package}@{finding.version}", []).append(finding)
        base_versions: dict[str, list[str]] = {}
        for node in base.nodes:
            base_versions.setdefault(node.name, []).append(node.version)

        enriched = {node.id: node for node in head.nodes}
        releases = [
            self._release(
                head,
                enriched[node_id],
                sorted(base_versions.get(head_nodes[node_id].name, [])),
                by_release.get(node_id, []),
                advisories,
                anchors.get(node_id),
                fail_on,
                project=head_parsed.name or "project",
            )
            for node_id in changed_ids
        ]
        releases.sort(key=lambda release: (-VERDICT_RANK[release.verdict], not release.direct, release.package, release.version))
        verdict: GateVerdict = max((release.verdict for release in releases), key=VERDICT_RANK.__getitem__, default="pass")
        report = GateReport(
            verdict=verdict,
            fail_on=fail_on,
            label=label,
            summary=GateSummary(
                added=sum(release.change == "added" for release in releases),
                updated=sum(release.change == "updated" for release in releases),
                removed=len(removed),
                failed=sum(release.verdict == "fail" for release in releases),
                warned=sum(release.verdict == "warn" for release in releases),
            ),
            releases=releases,
            removed_packages=removed,
            warnings=warnings,
            notes=notes,
            markdown="",
        )
        return report.model_copy(update={"markdown": render_markdown(report)})

    async def _verify_anchors(self, releases: list[tuple[str, str]], warnings: list[str]) -> dict[str, VerificationResult]:
        if self.verifier is None or not releases:
            return {}
        results = await asyncio.gather(*(self.verifier.verify(name, version) for name, version in releases))
        if all(result.status == "unavailable" for result in results):
            detail = next((result.detail for result in results if result.detail), "the release registry is unreachable")
            warnings.append(f"Release anchors were not checked: {detail}.")
            return {}
        return {f"{result.package}@{result.version}": result for result in results}

    def _release(
        self,
        head: ScanGraph,
        node: GraphNode,
        from_versions: list[str],
        findings: list[Finding],
        advisories: dict[tuple[str, str], Any] | None,
        anchor: VerificationResult | None,
        fail_on: GateThreshold,
        *,
        project: str,
    ) -> GateRelease:
        change = "updated" if from_versions else "added"
        if change == "added":
            # A brand-new package always brings new edges; expansion only means something on an update.
            findings = [finding for finding in findings if finding.rule_id != "dependency-expansion"]
        checks = _checks(node, change, findings, advisories, anchor, fail_on)
        verdict: GateVerdict = "pass"
        if any(check.status == "fail" for check in checks):
            verdict = "fail"
        elif any(check.status == "warn" for check in checks):
            verdict = "warn"
        blast_radius: list[str] = []
        if verdict != "pass":
            paths = next((finding.paths for finding in findings if finding.paths), None) or _dependency_paths(head, node.id)
            if paths:
                blast_radius = [project if step == "root" else _package_name(step) for step in paths[0]]
        return GateRelease(
            package=node.name,
            version=node.version,
            change=change,
            from_versions=from_versions,
            direct=node.direct,
            verdict=verdict,
            checks=checks,
            findings=sorted(findings, key=lambda finding: -finding.priority_score),
            anchor=anchor,
            blast_radius=blast_radius,
        )


def _package_name(node_id: str) -> str:
    """'name@version' or '@scope/name@version' -> name."""
    at = node_id.rfind("@")
    return node_id[:at] if at > 0 else node_id


def _severity_status(severity: str, fail_on: GateThreshold) -> GateCheckStatus:
    rank = SEVERITY_RANK[severity]
    if rank >= THRESHOLD_RANK[fail_on]:
        return "fail"
    return "warn" if rank >= SEVERITY_RANK["low"] else "info"


def _checks(
    node: GraphNode,
    change: str,
    findings: list[Finding],
    advisories: dict[tuple[str, str], Any] | None,
    anchor: VerificationResult | None,
    fail_on: GateThreshold,
) -> list[GateCheck]:
    by_rule = {finding.rule_id: finding for finding in findings}
    meta = node.registry
    checks: list[GateCheck] = []
    if meta.status == "unavailable":
        # Not on the public registry: private, unpublished, or a name that could be claimed later.
        checks.append(GateCheck(status="warn", label=f"Not verifiable on the npm registry ({meta.error})"))

    def from_finding(rule_id: str, label: str) -> bool:
        finding = by_rule.pop(rule_id, None)
        if finding is None:
            return False
        checks.append(GateCheck(status=_severity_status(finding.severity, fail_on), label=label))
        return True

    # Vulnerabilities
    if advisories is not None:
        vulnerability = by_rule.get("known-vulnerability")
        if vulnerability is not None:
            ids = vulnerability.evidence[0].value.get("identifiers", [])
            from_finding("known-vulnerability", f"Known vulnerabilities: {', '.join(ids[:4])}{' …' if len(ids) > 4 else ''}")
        elif advisories.get((node.name, node.version)) is None:
            checks.append(GateCheck(status="warn", label="Vulnerability lookup unavailable"))
        else:
            checks.append(GateCheck(status="pass", label="No known vulnerabilities"))

    # Install scripts
    known_scripts = install_scripts(node)
    scripts = ", ".join(known_scripts or [])
    if not from_finding("install-script-added", f"New {scripts} script introduced") and not from_finding(
        "install-script-present", f"Runs an install script ({scripts})"
    ):
        if known_scripts is None:
            checks.append(GateCheck(status="info", label="Install scripts unknown (registry metadata unavailable)"))
        elif known_scripts:
            checks.append(GateCheck(status="info", label=f"Runs an install script ({scripts}), unchanged from the previous version"))
        else:
            checks.append(GateCheck(status="pass", label="No install scripts"))

    # Publisher
    publisher_change = by_rule.get("publisher-change")
    if publisher_change is not None:
        value = publisher_change.evidence[0].value
        # Correlation can raise the aggregate finding, but preserve the publisher check's
        # established medium threshold; the correlated constituent checks carry their own status.
        by_rule.pop("publisher-change")
        checks.append(
            GateCheck(
                status=_severity_status("medium", fail_on),
                label=f"Publisher changed: {', '.join(value['previous_publishers'])} → {value['current_publisher']}",
            )
        )
    elif meta.publisher:
        checks.append(GateCheck(status="pass" if change == "updated" else "info", label=f"{'Same publisher' if change == 'updated' else 'Published by'} {meta.publisher}"))
    maintainer_change = by_rule.get("maintainer-change")
    if maintainer_change is not None:
        value = maintainer_change.evidence[0].value
        from_finding(
            "maintainer-change",
            f"Maintainer snapshot changed (+{len(value.get('added_maintainers', []))}/-{len(value.get('removed_maintainers', []))})",
        )
    elif change == "updated" and meta.maintainers is None:
        checks.append(GateCheck(status="info", label="Historical maintainer comparison unavailable"))

    # Provenance
    if not from_finding("provenance-removed", "Build provenance missing (previous version had it)"):
        if meta.has_provenance:
            checks.append(GateCheck(status="pass", label="npm build provenance attested"))
        elif meta.has_provenance is False:
            checks.append(GateCheck(status="info", label="No npm build provenance"))

    timing = by_rule.get("unusual-release-timing")
    if timing is not None:
        seconds = timing.evidence[0].value.get("interval_seconds")
        from_finding("unusual-release-timing", f"Published {seconds}s after the previous release")
    deprecated = by_rule.get("deprecated-package")
    if deprecated is not None:
        from_finding("deprecated-package", f"Deprecated: {meta.deprecated}")
    expansion = by_rule.get("dependency-expansion")
    if expansion is not None:
        edges = expansion.evidence[0].value.get("edges", [])
        from_finding("dependency-expansion", f"Adds {len(edges)} new dependency edge(s)")
    from_finding("new-dependency", f"New {'direct' if node.direct else 'transitive'} dependency")
    for finding in list(by_rule.values()):  # any rule without a dedicated label
        from_finding(finding.rule_id, finding.title)

    # Release anchor: "match" means unchanged from an approved record, never "safe"; no record is an evidence gap.
    if anchor is not None:
        if anchor.status == "match":
            checks.append(GateCheck(status="pass", label="Matches its anchored release record"))
        elif anchor.status == "mismatch":
            checks.append(GateCheck(status="fail" if fail_on != "never" else "warn", label="Differs from its anchored release record"))
        elif anchor.status == "no_record":
            checks.append(GateCheck(status="info", label="No release anchor (evidence gap, not a risk signal)"))
        else:
            checks.append(GateCheck(status="info", label="Release anchor could not be checked"))
    return checks


CHECK_ICON = {"pass": "✓", "warn": "⚠", "fail": "✗", "info": "·"}
VERDICT_HEADLINE = {"pass": "✅ Dependency Trust Check: PASSED", "warn": "⚠️ Dependency Trust Check: WARNING", "fail": "❌ Dependency Trust Check: FAILED"}
VERDICT_ICON = {"pass": "✓", "warn": "⚠", "fail": "✗"}


def _change_text(release: GateRelease) -> str:
    if release.change == "updated":
        return f"{', '.join(release.from_versions)} → {release.version}"
    return f"{release.version} (new)"


def render_markdown(report: GateReport) -> str:
    s = report.summary
    # One marker per lockfile, so a PR touching several lockfiles keeps one comment for each.
    marker = f"{COMMENT_MARKER}{':' + report.label if report.label else ''} -->"
    lines = [marker, f"## {VERDICT_HEADLINE[report.verdict]}", ""]
    scope = f"`{report.label}` · " if report.label else ""
    lines.append(
        f"{scope}**{s.added + s.updated}** release(s) changed ({s.added} added, {s.updated} updated, {s.removed} removed)"
        f" · fails on `{report.fail_on}` findings"
    )
    lines.append("")
    if not report.releases:
        lines.append("No dependency releases were added or updated.")

    flagged = [release for release in report.releases if release.verdict != "pass"]
    for release in flagged[:MAX_DETAILED_RELEASES]:
        lines.append(f"### {VERDICT_ICON[release.verdict]} `{release.package}` {_change_text(release)}")
        lines.extend(f"- {CHECK_ICON[check.status]} {check.label}" for check in release.checks)
        if release.blast_radius:
            lines.append(f"- Blast radius: `{' → '.join(release.blast_radius)}`")
        explained = [finding for finding in release.findings if finding.severity != "info"]
        if explained:
            lines.append("")
            lines.append("<details><summary>Evidence</summary>")
            lines.append("")
            lines.extend(f"- **{finding.title}** ({finding.severity}, `{finding.rule_id}`): {finding.explanation}" for finding in explained)
            lines.append("")
            lines.append("</details>")
        lines.append("")
    if len(flagged) > MAX_DETAILED_RELEASES:
        rest = flagged[MAX_DETAILED_RELEASES:]
        lines.append(f"…and {len(rest)} more flagged release(s): " + ", ".join(f"`{r.package}@{r.version}`" for r in rest))
        lines.append("")

    passed = [release for release in report.releases if release.verdict == "pass"]
    if passed:
        lines.append(f"<details><summary>✓ {len(passed)} release(s) passed</summary>")
        lines.append("")
        lines.extend(f"- `{release.package}` {_change_text(release)}" for release in passed)
        lines.append("")
        lines.append("</details>")
        lines.append("")
    if report.warnings:
        lines.extend(f"> ⚠ {warning}" for warning in report.warnings)
        lines.append("")
    if report.notes:
        lines.append(f"<details><summary>Lockfile notes ({len(report.notes)})</summary>")
        lines.append("")
        lines.extend(f"- {note}" for note in report.notes)
        lines.append("")
        lines.append("</details>")
        lines.append("")
    lines.append(
        "<sub>Provenyx never installs or executes package code; optional static inspection only reads verified archives. "
        "Findings are investigation signals, not verdicts; "
        "a matching release anchor means unchanged from an approved record, not safe.</sub>"
    )
    markdown = "\n".join(lines)
    if len(markdown) > MAX_COMMENT_CHARS:
        markdown = markdown[:MAX_COMMENT_CHARS] + "\n\n…report truncated; see the JSON report for every release."
    return markdown


def _load_lockfile(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    file = Path(path)
    if not file.is_file() or not file.read_text(encoding="utf-8").strip():
        return None
    return Lockfile.model_validate_json(file.read_text(encoding="utf-8")).model_dump(mode="json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.gate", description="Provenyx pull request dependency trust gate")
    parser.add_argument("--head", required=True, help="the pull request's package-lock.json")
    parser.add_argument("--base", help="the base branch's package-lock.json (missing or empty = new lockfile)")
    parser.add_argument("--fail-on", choices=list(THRESHOLD_RANK), default="high", help="lowest finding severity that fails the gate")
    parser.add_argument("--label", help="lockfile path shown in the report")
    parser.add_argument("--markdown", help="write the Markdown report here")
    parser.add_argument("--json", help="write the JSON report here")
    parser.add_argument("--no-osv", action="store_true", help="skip OSV vulnerability lookups")
    parser.add_argument("--no-anchors", action="store_true", help="skip release anchor verification")
    args = parser.parse_args(argv)

    try:
        head = _load_lockfile(args.head)
        base = _load_lockfile(args.base)
    except (ValidationError, ValueError, OSError) as exc:
        print(f"Invalid lockfile: {exc}", file=sys.stderr)
        return 2
    if head is None:
        print(f"Head lockfile {args.head!r} was not found or is empty", file=sys.stderr)
        return 2

    from app.core.config import settings

    registry = NpmRegistryClient(
        base_url=settings.npm_registry_url,
        concurrency=settings.npm_registry_concurrency,
        timeout_seconds=settings.npm_registry_timeout_seconds,
        retries=settings.npm_registry_retries,
    )
    osv = None if args.no_osv else OsvClient(
        base_url=settings.osv_api_url,
        concurrency=settings.osv_concurrency,
        timeout_seconds=settings.osv_timeout_seconds,
        retries=settings.osv_retries,
    )
    verifier = None
    if not args.no_anchors:
        from app.blockchain.registry import ReleaseRegistryReader

        verifier = ReleaseVerifier(
            ReleaseRegistryReader(
                rpc_url=settings.registry_rpc_url,
                deployment_file=settings.registry_deployment_file,
                address=settings.registry_address,
                timeout_seconds=settings.registry_timeout_seconds,
            ),
            registry,
        )

    allowed_hosts = settings.static_analysis_allowed_host_set
    if registry_host := urlparse(settings.npm_registry_url).hostname:
        allowed_hosts.add(registry_host.lower())
    static_inspector = (
        StaticArtifactInspector(
            allowed_hosts=allowed_hosts,
            limits=StaticAnalysisLimits(
                max_archive_bytes=settings.static_analysis_max_archive_bytes,
                max_decompressed_bytes=settings.static_analysis_max_decompressed_bytes,
                max_files=settings.static_analysis_max_files,
                max_file_bytes=settings.static_analysis_max_file_bytes,
                timeout_seconds=settings.static_analysis_timeout_seconds,
                concurrency=settings.static_analysis_concurrency,
            ),
        )
        if settings.static_analysis_enabled
        else None
    )
    report = asyncio.run(
        TrustGate(
            registry,
            osv=osv,
            verifier=verifier,
            trusted_packages=settings.typosquat_trusted_package_list,
            static_inspector=static_inspector,
            static_max_packages=settings.static_analysis_max_packages,
        ).evaluate(head, base, fail_on=args.fail_on, label=args.label)
    )
    if args.markdown:
        Path(args.markdown).write_text(report.markdown, encoding="utf-8")
    if args.json:
        Path(args.json).write_text(report.model_dump_json(indent=2), encoding="utf-8")
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"verdict={report.verdict}\n")
    s = report.summary
    print(f"Dependency trust check: {report.verdict.upper()} ({s.failed} failed, {s.warned} warned, {s.added + s.updated} changed)")
    return 1 if report.verdict == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
