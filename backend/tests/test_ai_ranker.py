import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.detection.ai_ranker import AiRankingError, GeminiFindingRanker
from app.models.database import ScanRepository
from app.models.schemas import Finding, FindingEvidence
from app.parsers.npm_registry import NpmRegistryClient
from app.services import ScanService
from tests.test_detection_rules import OBSERVED_AT


def finding(identifier: str, package: str, score: int) -> Finding:
    return Finding(
        id=identifier,
        rule_id="new-dependency",
        package=package,
        version="1.0.0",
        severity="info",
        confidence="high",
        priority_score=score,
        title="New dependency",
        explanation="Review this dependency.",
        evidence=[FindingEvidence(source="lockfile", field="dependency_added", value=True, observed_at=OBSERVED_AT)],
    )


def test_gemini_ranking_is_transparent_and_does_not_send_lockfile_evidence():
    request_payload: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_payload
        request_payload = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "rankings": [
                                                {"id": "low", "score": 90, "rationale": "Needs early review."},
                                                {"id": "high", "score": 40, "rationale": "Lower contextual concern."},
                                            ]
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
        )

    ranker = GeminiFindingRanker(api_key="test-key", transport=httpx.MockTransport(handler))
    ranked = asyncio.run(ranker.rank([finding("high", "a", 70), finding("low", "b", 20)]))

    assert [item.id for item in ranked] == ["low", "high"]
    assert ranked[0].ranking_source == "gemini"
    assert ranked[0].ai_priority_score == 90
    assert ranked[0].ai_rationale == "Needs early review."
    assert request_payload["generationConfig"]["responseMimeType"] == "application/json"
    prompt = request_payload["contents"][0]["parts"][0]["text"]
    assert "dependency_added" not in prompt
    assert "test-key" not in prompt


def test_gemini_ranking_rejects_incomplete_results():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": '{"rankings":[{"id":"one","score":50,"rationale":"ok"}]}' }]}}
                ]
            },
        )

    ranker = GeminiFindingRanker(api_key="test-key", transport=httpx.MockTransport(handler))

    with pytest.raises(AiRankingError, match="cover each finding"):
        asyncio.run(ranker.rank([finding("one", "a", 20), finding("two", "b", 30)]))


def test_scan_service_persists_gemini_ranking(tmp_path: Path):
    def gemini_handler(request: httpx.Request) -> httpx.Response:
        prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
        candidates = json.loads(prompt.partition("Candidates: ")[2])
        rankings = [
            {
                "id": candidate["id"],
                "score": 90 if candidate["rule_id"] == "new-dependency" else 40,
                "rationale": f"Reviewed {candidate['rule_id']}",
            }
            for candidate in candidates
        ]
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": json.dumps({"rankings": rankings})}]}}]},
        )

    service = _scan_service(tmp_path, GeminiFindingRanker(api_key="test-key", transport=httpx.MockTransport(gemini_handler)))
    current_id = _analyze_update(service)

    findings = [Finding.model_validate(item) for item in service.repository.get_findings(current_id)]
    assert [item.rule_id for item in findings] == ["new-dependency", "dependency-expansion"]
    assert all(item.ranking_source == "gemini" for item in findings)
    assert [item.ai_priority_score for item in findings] == [90, 40]


def test_scan_service_falls_back_when_gemini_response_is_invalid(tmp_path: Path):
    ranker = GeminiFindingRanker(
        api_key="test-key",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"candidates": []})),
    )
    service = _scan_service(tmp_path, ranker)
    current_id = _analyze_update(service)

    row = service.repository.get(current_id)
    assert row is not None
    findings = [Finding.model_validate(item) for item in service.repository.get_findings(current_id)]
    assert all(item.ranking_source == "deterministic" for item in findings)
    assert "AI ranking was unavailable; deterministic priorities were retained" in row.warnings


def _scan_service(tmp_path: Path, ranker: GeminiFindingRanker) -> ScanService:
    registry = NpmRegistryClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"name": "pkg", "version": request.url.path.rsplit("/", 1)[-1]})
        ),
        retries=0,
    )
    return ScanService(
        ScanRepository(f"sqlite:///{tmp_path / 'ai-ranking.db'}"),
        registry,
        finding_ranker=ranker,
    )


def _analyze_update(service: ScanService) -> str:
    baseline = {
        "name": "ai-ranking-demo",
        "lockfileVersion": 3,
        "packages": {"": {"dependencies": {"parent": "1.0.0"}}, "node_modules/parent": {"version": "1.0.0"}},
    }
    current = {
        "name": "ai-ranking-demo",
        "lockfileVersion": 3,
        "packages": {
            "": {"dependencies": {"parent": "1.0.0"}},
            "node_modules/parent": {"version": "1.0.0", "dependencies": {"child": "1.0.0"}},
            "node_modules/child": {"version": "1.0.0"},
        },
    }
    baseline_id = service.create_scan(baseline, "ai-ranking-demo")
    current_id = service.create_scan(current, "ai-ranking-demo")
    asyncio.run(service.analyze_scan(baseline_id))
    asyncio.run(service.analyze_scan(current_id))
    return current_id