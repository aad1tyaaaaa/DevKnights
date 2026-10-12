import asyncio
import json

import httpx

from app.detection.osv import OsvClient
from app.models.schemas import Finding, FindingEvidence
from app.gate import COMMENT_MARKER, TrustGate, _load_lockfile, _safe_markdown_text
from app.parsers.npm_registry import NpmRegistryClient
from tests.fakes import osv_transport


def lockfile(packages: dict[str, dict], root_deps: dict[str, str]) -> dict:
    return {
        "name": "shop-app",
        "version": "1.0.0",
        "lockfileVersion": 3,
        "packages": {"": {"name": "shop-app", "version": "1.0.0", "dependencies": root_deps}, **packages},
    }


BASE = lockfile(
    {
        "node_modules/express": {"version": "4.18.2", "dependencies": {"body-parser": "^1.0.0"}},
        "node_modules/body-parser": {"version": "1.0.0"},
        "node_modules/left-pad": {"version": "1.3.0"},
    },
    {"express": "^4.18.2", "left-pad": "^1.3.0"},
)
HEAD = lockfile(
    {
        "node_modules/express": {"version": "4.18.3", "dependencies": {"body-parser": "^1.0.0", "evil-helper": "^1.0.0"}},
        "node_modules/body-parser": {"version": "1.0.0"},
        "node_modules/evil-helper": {"version": "1.0.0"},
        "node_modules/chalk": {"version": "5.0.0"},
    },
    {"express": "^4.18.3", "chalk": "^5.0.0"},
)

PROVENANCE = {"attestations": {"provenance": {"predicateType": "https://slsa.dev/provenance/v1"}}}
RELEASES = {
    "/express/4.18.2": {"_npmUser": {"name": "alice"}, "scripts": {"test": "jest"}, "dist": {"integrity": "sha512-a", **PROVENANCE}},
    "/express/4.18.3": {"_npmUser": {"name": "mallory"}, "scripts": {"postinstall": "node collect.js"}, "dist": {"integrity": "sha512-b"}},
    "/body-parser/1.0.0": {"_npmUser": {"name": "alice"}, "dist": {"integrity": "sha512-c"}},
    "/evil-helper/1.0.0": {"_npmUser": {"name": "mallory"}, "scripts": {"install": "node-gyp rebuild"}, "dist": {"integrity": "sha512-d"}},
    "/chalk/5.0.0": {"_npmUser": {"name": "sindre"}, "dist": {"integrity": "sha512-e", **PROVENANCE}},
}


def make_gate(requested: list[str] | None = None, *, advisories: dict | None = None) -> TrustGate:
    def registry(request: httpx.Request) -> httpx.Response:
        if requested is not None:
            requested.append(request.url.path)
        if request.url.path == "/express":  # release history; a week apart, so no timing finding
            return httpx.Response(200, json={"time": {"4.18.2": "2026-01-01T00:00:00Z", "4.18.3": "2026-01-08T00:00:00Z"}})
        payload = RELEASES.get(request.url.path)
        return httpx.Response(200, json=payload) if payload is not None else httpx.Response(404)

    osv = OsvClient(transport=osv_transport(advisories), retries=0)
    return TrustGate(NpmRegistryClient(transport=httpx.MockTransport(registry), retries=0), osv=osv)


def test_gate_fails_when_an_update_introduces_an_install_script():
    requested: list[str] = []
    report = asyncio.run(make_gate(requested).evaluate(HEAD, BASE, label="package-lock.json"))

    assert report.verdict == "fail"
    assert (report.summary.added, report.summary.updated, report.summary.removed) == (2, 1, 1)
    assert report.removed_packages == ["left-pad@1.3.0"]

    express = next(release for release in report.releases if release.package == "express")
    assert express.verdict == "fail"
    assert (express.change, express.from_versions) == ("updated", ["4.18.2"])
    checks = {check.label: check.status for check in express.checks}
    assert checks["New postinstall script introduced"] == "fail"
    assert checks["Publisher changed: alice → mallory"] == "warn"
    assert checks["Build provenance missing (previous version had it)"] == "warn"
    assert checks["No known vulnerabilities"] == "pass"
    assert checks["Adds 1 new dependency edge(s)"] == "warn"  # evil-helper; the existing body-parser edge is not new
    assert express.blast_radius == ["shop-app", "express"]
    assert all(finding.threat_explanation is not None for finding in express.findings)
    assert all(finding.remediation for finding in express.findings)
    assert all(finding.blast_radius is not None for finding in express.findings)

    helper = next(release for release in report.releases if release.package == "evil-helper")
    assert helper.verdict == "warn"  # a new package's install script is reviewed, not blocked, at fail_on=high
    assert {check.label: check.status for check in helper.checks}["Runs an install script (install)"] == "warn"
    assert helper.blast_radius == ["shop-app", "express", "evil-helper"]

    chalk = next(release for release in report.releases if release.package == "chalk")
    assert chalk.verdict == "pass"

    # Only changed releases and their predecessors are fetched; unchanged body-parser never is.
    assert "/body-parser/1.0.0" not in requested
    assert report.releases[0].package == "express"  # failures sort first

    assert report.markdown.startswith(COMMENT_MARKER)
    assert "❌ Dependency Trust Check: FAILED" in report.markdown
    assert "### ✗ `express` 4.18.2 → 4.18.3" in report.markdown
    assert "- ✗ New postinstall script introduced" in report.markdown
    assert "Blast radius: `shop-app → express`" in report.markdown
    assert "1 release(s) passed" in report.markdown
    assert "Recommended:" in report.markdown


def test_fail_threshold_never_downgrades_failures_to_warnings():
    report = asyncio.run(make_gate().evaluate(HEAD, BASE, fail_on="never"))

    assert report.verdict == "warn"
    assert report.summary.failed == 0


def test_known_vulnerability_in_a_new_release_fails_at_medium_threshold():
    advisory = {"id": "GHSA-xxxx", "aliases": ["CVE-2026-1"], "database_specific": {"severity": "MODERATE"}}
    report = asyncio.run(make_gate(advisories={("chalk", "5.0.0"): [advisory]}).evaluate(HEAD, BASE, fail_on="medium"))

    chalk = next(release for release in report.releases if release.package == "chalk")
    assert chalk.verdict == "fail"
    assert any(check.label.startswith("Known vulnerabilities: CVE-2026-1") for check in chalk.checks)


def test_unchanged_lockfile_passes_without_registry_traffic():
    requested: list[str] = []
    report = asyncio.run(make_gate(requested).evaluate(BASE, BASE))

    assert report.verdict == "pass"
    assert report.releases == []
    assert requested == []
    assert "No dependency releases were added or updated." in report.markdown


def test_missing_base_lockfile_treats_every_release_as_added(tmp_path):
    report = asyncio.run(make_gate().evaluate(HEAD, None))

    assert report.summary.updated == 0
    assert report.summary.added == 4
    assert any("No base lockfile" in warning for warning in report.warnings)

    head_file = tmp_path / "package-lock.json"
    head_file.write_text(json.dumps(HEAD), encoding="utf-8")
    assert _load_lockfile(str(head_file))["lockfileVersion"] == 3
    assert _load_lockfile(str(tmp_path / "missing.json")) is None


def test_gate_api_returns_the_report_and_validates_lockfiles():
    from fastapi.testclient import TestClient

    from app.api.routes import get_trust_gate
    from app.main import app

    app.dependency_overrides[get_trust_gate] = make_gate
    client = TestClient(app)

    response = client.post("/api/gate", json={"base_lockfile": BASE, "head_lockfile": HEAD, "fail_on": "never"})
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "warn"
    assert body["markdown"].startswith(COMMENT_MARKER)

    assert client.post("/api/gate", json={"head_lockfile": {"lockfileVersion": 9}}).status_code == 422
    assert client.post("/api/gate", content=b"{}", headers={"content-type": "text/plain"}).status_code == 415


def test_lockfile_install_script_flag_is_used_when_the_registry_has_no_record():
    head = lockfile(
        {**HEAD["packages"], "node_modules/private-tool": {"version": "0.1.0", "hasInstallScript": True}},
        {**HEAD["packages"][""]["dependencies"], "private-tool": "^0.1.0"},
    )

    report = asyncio.run(make_gate().evaluate(head, BASE))
    tool = next(release for release in report.releases if release.package == "private-tool")
    checks = {check.label: check.status for check in tool.checks}

    assert checks["Runs an install script (declared in lockfile)"] == "warn"
    assert checks["Not verifiable on the npm registry (Release metadata was not found in the npm registry)"] == "warn"


def test_typosquatting_finding_is_evaluated_by_the_gate():
    head = lockfile({"node_modules/expres": {"version": "1.0.0"}}, {"expres": "1.0.0"})
    report = asyncio.run(make_gate().evaluate(head, None, fail_on="medium"))
    release = report.releases[0]
    assert report.verdict == "fail"
    assert any(finding.rule_id == "possible-typosquatting" for finding in release.findings)


def test_static_finding_is_evaluated_by_the_gate():
    class StaticInspector:
        async def analyze(self, graph, *, candidate_ids, observed_at):
            node = next(node for node in graph.nodes if node.id in candidate_ids)
            return [
                Finding(
                    id="gate-static",
                    rule_id="suspicious-install-time-behavior",
                    package=node.name,
                    version=node.version,
                    severity="high",
                    confidence="medium",
                    priority_score=88,
                    title="Suspicious install-time behavior",
                    explanation="Synthetic gate integration finding; package code was not executed.",
                    evidence=[
                        FindingEvidence(
                            source="static-analysis",
                            field="code_indicators",
                            value={"integrity_verified": True},
                            observed_at=observed_at,
                        )
                    ],
                )
            ], []

    gate = make_gate()
    gate.static_inspector = StaticInspector()
    head = lockfile({"node_modules/tool": {"version": "1.0.0"}}, {"tool": "1.0.0"})
    report = asyncio.run(gate.evaluate(head, None, fail_on="high"))
    assert report.verdict == "fail"
    assert report.releases[0].findings[0].rule_id == "suspicious-install-time-behavior"


def test_provider_text_is_rendered_as_inert_gate_markdown():
    rendered = _safe_markdown_text("[click](https://evil.invalid) @everyone <img src=x>\nnext")
    assert "\\[click\\]\\(" in rendered
    assert "@\u200beveryone" in rendered
    assert "&lt;img" in rendered
    assert "\n" not in rendered
