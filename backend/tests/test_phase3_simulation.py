import asyncio

from fastapi.testclient import TestClient

from app.api.routes import get_scan_service, get_trust_gate
from app.main import app
from phase3_demo.runner import build_services, run_all_scenarios, run_scenario
from phase3_demo.scenarios import SCENARIOS


EXPECTED_VERDICTS = {
    "typosquatting-attack": "fail",
    "suspicious-package-update": "fail",
    "publisher-change": "fail",
    "transitive-dependency-compromise": "fail",
    "legitimate-update": "pass",
}


def test_all_five_synthetic_scenarios_use_real_analysis_and_gate_paths():
    reports = asyncio.run(run_all_scenarios())

    assert [report.scenario for report in reports] == list(SCENARIOS)
    assert len(reports) == 5
    for report in reports:
        expected = SCENARIOS[report.scenario]
        actual_rules = {finding.rule_id for finding in report.new_findings}
        assert set(expected.expected_rules) <= actual_rules
        assert report.synthetic is True
        assert report.baseline.status == report.modified.status == "complete"
        assert report.gate_verdict == EXPECTED_VERDICTS[report.scenario]
        assert any("No package was installed" in value for value in report.analysis_limitations)
        for finding in report.new_findings:
            assert finding.evidence
            assert finding.threat_explanation is not None
            assert finding.threat_explanation.source == "deterministic"
            assert finding.remediation
            assert finding.blast_radius is not None


def test_transitive_report_has_exact_path_bounded_impact_and_remediation():
    report = asyncio.run(run_scenario("transitive-dependency-compromise"))
    typo = next(finding for finding in report.new_findings if finding.rule_id == "possible-typosquatting")

    assert typo.version == "1.0.0"
    assert typo.blast_radius is not None
    assert typo.blast_radius.shortest_path == [
        "root",
        "package-a@1.0.0",
        "package-b@1.0.0",
        "lodahs@1.0.0",
    ]
    assert typo.blast_radius.introducing_direct_dependencies == ["package-a@1.0.0"]
    assert typo.blast_radius.affected_package_count == 3
    assert "does not prove" in typo.blast_radius.reachability_note
    assert report.remediation_recommendations


def test_legitimate_update_does_not_create_unsupported_claims_or_block():
    report = asyncio.run(run_scenario("legitimate-update"))

    assert report.changes.updated[0].name == "provenyx-benign-library"
    assert report.new_findings == []
    assert report.gate_verdict == "pass"
    assert report.gate.summary.failed == 0
    assert report.gate.summary.warned == 0


def test_phase2_fields_survive_persistence_and_api_serialization(tmp_path):
    scenario = SCENARIOS["suspicious-package-update"]
    service, gate = build_services(scenario, f"sqlite:///{tmp_path / 'phase3-api.db'}")
    app.dependency_overrides[get_scan_service] = lambda: service
    app.dependency_overrides[get_trust_gate] = lambda: gate
    try:
        with TestClient(app) as client:
            baseline = client.post(
                "/api/scans", json={"lockfile": scenario.baseline, "project_name": scenario.project_name}
            )
            modified = client.post(
                "/api/scans", json={"lockfile": scenario.modified, "project_name": scenario.project_name}
            )
            findings_response = client.get(f"/api/scans/{modified.json()['scan_id']}/findings")
            comparison_response = client.get(
                f"/api/scans/{modified.json()['scan_id']}/compare/{baseline.json()['scan_id']}"
            )
            gate_response = client.post(
                "/api/gate",
                json={
                    "base_lockfile": scenario.baseline,
                    "head_lockfile": scenario.modified,
                    "fail_on": "medium",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert baseline.status_code == modified.status_code == 202
    assert findings_response.status_code == comparison_response.status_code == gate_response.status_code == 200
    findings = findings_response.json()
    assert {finding["rule_id"] for finding in findings} >= set(scenario.expected_rules)
    assert all(finding["threat_explanation"]["source"] == "deterministic" for finding in findings)
    assert all(finding["remediation"] for finding in findings)
    assert all(finding["blast_radius"]["shortest_path"] for finding in findings)
    assert comparison_response.json()["version_changes"] == [
        {
            "name": "provenyx-synthetic-widget",
            "from_versions": ["1.0.0"],
            "to_versions": ["2.0.0"],
        }
    ]
    assert gate_response.json()["verdict"] == "fail"
