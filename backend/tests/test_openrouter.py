import asyncio
import json

import httpx
import pytest
from starlette.testclient import TestClient

from app.llm.openrouter import OpenRouterSimplifier, clean_llm_json_text
from app.main import app
from app.models.schemas import Finding, FindingEvidence, ScanComparisonResponse, VersionChangeResponse
from tests.test_detection_rules import OBSERVED_AT


def make_finding(finding_id: str, package: str, rule: str = "new-dependency") -> Finding:
    return Finding(
        id=finding_id,
        rule_id=rule,
        package=package,
        version="1.0.0",
        severity="high" if "vuln" in rule else "info",
        confidence="high",
        priority_score=85 if "vuln" in rule else 40,
        title=f"Finding for {package}",
        explanation=f"Technical detail for {package}.",
        evidence=[FindingEvidence(source="lockfile", field="test", value=True, observed_at=OBSERVED_AT)],
    )


def test_clean_llm_json_text_strips_markdown_fences():
    fenced = "```json\n{\"headline\": \"test\"}\n```"
    assert clean_llm_json_text(fenced) == '{"headline": "test"}'


def test_fallback_simplification_when_openrouter_key_unset():
    simplifier = OpenRouterSimplifier(api_key=None)
    findings = [make_finding("f1", "pkg-a", "known-vulnerabilities")]
    analysis, provider = asyncio.run(
        simplifier.simplify_scan_output(
            project_name="test-project",
            summary={"packages": 10, "direct": 2, "transitive": 8, "findings": 1},
            findings=findings,
            language="Spanish",
        )
    )
    assert provider == "fallback"
    assert "pkg-a" in analysis.key_points[0]
    assert len(analysis.simplified_findings) == 1
    assert analysis.simplified_findings[0].package == "pkg-a"


def test_openrouter_simplification_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-openrouter-key"
        payload = json.loads(request.content)
        assert "plain, clear, non-technical English" in payload["messages"][1]["content"]
        response_json = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "headline": "All dependencies look good and safe",
                                "summary": "Added 2 packages with no critical supply-chain risks.",
                                "risk_level": "low",
                                "key_points": ["Clean update with verified package origins"],
                                "simplified_findings": [
                                    {
                                        "finding_id": "f1",
                                        "package": "pkg-a",
                                        "version": "1.0.0",
                                        "title": "Newly added direct package",
                                        "what_happened": "Package pkg-a was added directly to package.json.",
                                        "why_it_matters": "Direct dependencies introduce new code into your build.",
                                        "recommendation": "Confirm this package was requested by your team.",
                                    }
                                ],
                                "action_items": ["Proceed with the build"],
                            }
                        )
                    }
                }
            ]
        }
        return httpx.Response(200, json=response_json)

    simplifier = OpenRouterSimplifier(
        api_key="test-openrouter-key",
        transport=httpx.MockTransport(handler),
    )
    findings = [make_finding("f1", "pkg-a")]
    analysis, provider = asyncio.run(
        simplifier.simplify_scan_output(
            project_name="my-app",
            summary={"packages": 5, "direct": 2, "transitive": 3, "findings": 1},
            findings=findings,
            language="English",
        )
    )
    assert provider == "openrouter"
    assert analysis.risk_level == "low"
    assert analysis.headline == "All dependencies look good and safe"
    assert analysis.simplified_findings[0].finding_id == "f1"


def test_simplify_scan_endpoint_works():
    lockfile = {
        "name": "sample-app",
        "lockfileVersion": 3,
        "packages": {
            "": {"name": "sample-app", "dependencies": {"dep": "1.0.0"}},
            "node_modules/dep": {"version": "1.0.0"},
        },
    }

    with TestClient(app) as client:
        submit_res = client.post("/api/scans", json={"lockfile": lockfile})
        assert submit_res.status_code == 202
        scan_id = submit_res.json()["scan_id"]

        # Request simplified explanation in French
        sim_res = client.get(f"/api/scans/{scan_id}/simplify?language=French")
        assert sim_res.status_code == 200
        sim_data = sim_res.json()
        assert sim_data["scan_id"] == scan_id
        assert sim_data["language"] == "French"
        assert "headline" in sim_data
        assert "summary" in sim_data
        assert "risk_level" in sim_data
        assert isinstance(sim_data["key_points"], list)
        assert isinstance(sim_data["action_items"], list)

        # POST variant
        post_res = client.post(f"/api/scans/{scan_id}/simplify", json={"language": "German"})
        assert post_res.status_code == 200
        assert post_res.json()["language"] == "German"
