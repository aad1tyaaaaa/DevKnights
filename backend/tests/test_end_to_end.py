import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.api.routes import get_scan_service
from app.main import app
from app.models.database import ScanRepository
from app.parsers.npm_registry import NpmRegistryClient
from app.services import ScanService


FIXTURES = Path(__file__).parents[2] / "demo" / "fixtures"


def test_synthetic_update_flows_from_submission_to_evidence_backed_findings(tmp_path: Path):
    requested_releases: list[str] = []

    def registry_handler(request: httpx.Request) -> httpx.Response:
        requested_releases.append(request.url.path)
        version = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json={"version": version, "license": "MIT"})

    service = ScanService(
        ScanRepository(f"sqlite:///{tmp_path / 'e2e.db'}"),
        NpmRegistryClient(transport=httpx.MockTransport(registry_handler), retries=0),
    )
    app.dependency_overrides[get_scan_service] = lambda: service
    baseline = json.loads((FIXTURES / "baseline-package-lock.json").read_text())
    suspicious = json.loads((FIXTURES / "suspicious-update-package-lock.json").read_text())

    try:
        with TestClient(app) as client:
            baseline_response = client.post("/api/scans", json={"lockfile": baseline})
            current_response = client.post("/api/scans", json={"lockfile": suspicious})
            baseline_id = baseline_response.json()["scan_id"]
            current_id = current_response.json()["scan_id"]

            detail = client.get(f"/api/scans/{current_id}").json()
            graph = client.get(f"/api/scans/{current_id}/graph").json()
            findings = client.get(f"/api/scans/{current_id}/findings").json()
            comparison = client.get(f"/api/scans/{current_id}/compare/{baseline_id}").json()
            history = client.get("/api/scans").json()
    finally:
        app.dependency_overrides.clear()

    assert baseline_response.status_code == 202
    assert current_response.status_code == 202
    assert detail["status"] == "complete"
    assert detail["summary"] == {"packages": 2, "direct": 1, "transitive": 1, "findings": 2}
    assert {node["id"] for node in graph["nodes"]} == {
        "provenyx-synthetic-parent@1.0.0",
        "provenyx-synthetic-child@1.0.0",
    }
    assert {finding["rule_id"] for finding in findings} == {"new-dependency", "dependency-expansion"}
    assert all(finding["evidence"] and finding["paths"] for finding in findings)
    assert comparison["added_packages"] == ["provenyx-synthetic-child@1.0.0"]
    assert comparison["added_edges"] == [
        {
            "from": "provenyx-synthetic-parent@1.0.0",
            "to": "provenyx-synthetic-child@1.0.0",
            "type": "prod",
        }
    ]
    assert [scan["scan_id"] for scan in history] == [current_id, baseline_id]
    assert requested_releases
    assert not (tmp_path / "synthetic-never-executed.js").exists()


def test_validation_errors_do_not_echo_untrusted_lockfile_content():
    marker = "PRIVATE_LOCKFILE_MARKER"
    response = TestClient(app).post(
        "/api/scans",
        content=f'{{"lockfile":{{"name":"{marker}"'.encode(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert marker not in response.text