from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterable

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.models.schemas import Finding, ScanComparisonResponse, ScanSummary, SimplifiedFindingItem

logger = logging.getLogger("provenyx.llm")


class OpenRouterError(RuntimeError):
    """Raised when an OpenRouter call fails or returns an unparseable response."""
    pass


class SimplifiedAnalysis(BaseModel):
    headline: str
    summary: str
    risk_level: str = Field(description="safe, low, medium, or high")
    key_points: list[str] = Field(default_factory=list)
    simplified_findings: list[SimplifiedFindingItem] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)


def clean_llm_json_text(text: str) -> str:
    """Extract and clean valid JSON string even if enclosed in markdown code fences."""
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        cleaned = match.group(1).strip()
    return cleaned


class OpenRouterSimplifier:
    """Connects to OpenRouter to translate technical dependency security changes

    and findings into plain, accessible language for developers and team members.
    Supports rotating through multiple API keys to prevent exhaustion and rate-limits.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_keys: list[str] | None = None,
        model: str = "liquid/lfm-2.5-2.6b:free",
        base_url: str = "https://openrouter.ai/api/v1",
        site_url: str = "https://provenyx.dev",
        app_name: str = "Provenyx",
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._keys: list[str] = []
        if api_keys:
            self._keys.extend(k.strip() for k in api_keys if k and k.strip())
        if api_key and api_key.strip() and api_key.strip() not in self._keys:
            self._keys.append(api_key.strip())

        self._key_index = 0
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._site_url = site_url
        self._app_name = app_name
        self._timeout = timeout_seconds
        self._transport = transport

    @property
    def is_configured(self) -> bool:
        return len(self._keys) > 0

    @property
    def model_name(self) -> str:
        return self._model

    def _get_next_key(self) -> str:
        if not self._keys:
            raise OpenRouterError("No OpenRouter API key configured")
        key = self._keys[self._key_index % len(self._keys)]
        self._key_index = (self._key_index + 1) % len(self._keys)
        return key

    async def simplify_scan_output(
        self,
        *,
        project_name: str | None,
        summary: ScanSummary | dict[str, Any] | None,
        findings: Iterable[Finding | dict[str, Any]],
        comparison: ScanComparisonResponse | dict[str, Any] | None = None,
        language: str = "English",
    ) -> tuple[SimplifiedAnalysis, str]:
        """Simplifies scan results and changes into the user's requested language.

        Returns (SimplifiedAnalysis, provider_name). Provider is 'openrouter' or 'fallback'.
        """
        norm_findings = [
            f if isinstance(f, Finding) else Finding.model_validate(f)
            for f in findings
        ]

        if not self.is_configured:
            return self._fallback_simplification(project_name, summary, norm_findings, comparison, language), "fallback"

        prompt = self._build_scan_prompt(
            project_name=project_name,
            summary=summary,
            findings=norm_findings,
            comparison=comparison,
            language=language,
        )

        try:
            analysis = await self._call_openrouter(prompt)
            return analysis, "openrouter"
        except OpenRouterError as exc:
            logger.warning("OpenRouter simplification failed (%s); falling back to deterministic explanation", exc)
            return self._fallback_simplification(project_name, summary, norm_findings, comparison, language), "fallback"

    async def simplify_single_finding(
        self,
        finding: Finding | dict[str, Any],
        language: str = "English",
    ) -> tuple[SimplifiedFindingItem, str]:
        """Simplifies an individual finding into plain language."""
        f = finding if isinstance(finding, Finding) else Finding.model_validate(finding)

        if not self.is_configured:
            return self._fallback_finding(f, language), "fallback"

        prompt = (
            "You are a friendly software security assistant. Explain this npm package security finding "
            "in simple, plain, easy-to-understand English without any security jargon or obscure acronyms.\n\n"
            f"Package: {f.package}@{f.version}\n"
            f"Rule ID: {f.rule_id}\n"
            f"Title: {f.title}\n"
            f"Technical Explanation: {f.explanation}\n"
            f"Severity: {f.severity}\n\n"
            "Return ONLY valid JSON matching this exact structure:\n"
            "{\n"
            f'  "finding_id": "{f.id}",\n'
            f'  "package": "{f.package}",\n'
            f'  "version": "{f.version}",\n'
            '  "title": "Clear friendly plain-English title",\n'
            '  "what_happened": "In 1-2 simple sentences, what actually happened or changed in plain English",\n'
            '  "why_it_matters": "In 1-2 simple sentences, why the user should care or what the risk is in plain English",\n'
            '  "recommendation": "In 1-2 simple sentences, what practical step the user should take in plain English"\n'
            "}"
        )

        try:
            result = await self._call_openrouter_raw(prompt)
            parsed = json.loads(clean_llm_json_text(result))
            return SimplifiedFindingItem.model_validate(parsed), "openrouter"
        except Exception as exc:
            logger.warning("Failed to simplify finding with OpenRouter (%s); using fallback", exc)
            return self._fallback_finding(f, language), "fallback"

    async def _call_openrouter(self, prompt: str) -> SimplifiedAnalysis:
        raw_text = await self._call_openrouter_raw(prompt)
        cleaned = clean_llm_json_text(raw_text)
        try:
            data = json.loads(cleaned)
            return SimplifiedAnalysis.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise OpenRouterError(f"OpenRouter response could not be parsed into SimplifiedAnalysis: {exc}") from exc

    async def _call_openrouter_raw(self, prompt: str) -> str:
        if not self._keys:
            raise OpenRouterError("No OpenRouter API key configured")

        body = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert security engineer and software educator. "
                        "Your job is to translate npm dependency changes and security audit findings "
                        "into clear, practical, non-alarmist plain language for developers and product owners. "
                        "Explain what changed, whether it matters, and what to do next. "
                        "Always respond with valid JSON and no extra conversational filler."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        endpoint = f"{self._base_url}/chat/completions"
        total_keys = len(self._keys)
        last_exc: Exception | None = None

        # Try across keys with rotation; if a key hits 429/401/402/quota error, automatically advance to next
        for _ in range(total_keys):
            api_key = self._get_next_key()
            headers = {
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": self._site_url,
                "X-Title": self._app_name,
                "Content-Type": "application/json",
            }
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout,
                    transport=self._transport,
                    follow_redirects=True,
                ) as client:
                    response = await client.post(endpoint, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
                return payload["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code in (401, 402, 429, 503) and total_keys > 1:
                    logger.warning(
                        "OpenRouter key returned HTTP %s; rotating to next available key...",
                        exc.response.status_code,
                    )
                    continue
                raise OpenRouterError(f"OpenRouter API request failed: {exc}") from exc
            except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
                last_exc = exc
                if total_keys > 1:
                    logger.warning("OpenRouter request error (%s); rotating to next key...", exc)
                    continue
                raise OpenRouterError(f"OpenRouter API request failed: {exc}") from exc

        raise OpenRouterError(f"All configured OpenRouter keys exhausted: {last_exc}") from last_exc

    def _build_scan_prompt(
        self,
        *,
        project_name: str | None,
        summary: ScanSummary | dict[str, Any] | None,
        findings: list[Finding],
        comparison: ScanComparisonResponse | dict[str, Any] | None,
        language: str,
    ) -> str:
        findings_data = [
            {
                "id": f.id,
                "package": f.package,
                "version": f.version,
                "rule_id": f.rule_id,
                "title": f.title,
                "explanation": f.explanation,
                "severity": f.severity,
                "priority_score": f.priority_score,
            }
            for f in findings[:20]  # limit to top 20 to avoid context overload
        ]

        changes_summary: dict[str, Any] = {}
        if comparison:
            if isinstance(comparison, ScanComparisonResponse):
                changes_summary = {
                    "added_packages_count": len(comparison.added_packages),
                    "removed_packages_count": len(comparison.removed_packages),
                    "version_changes_count": len(comparison.version_changes),
                    "sample_updates": [
                        f"{c.name}: {c.from_versions} -> {c.to_versions}"
                        for c in comparison.version_changes[:5]
                    ],
                }
            elif isinstance(comparison, dict):
                changes_summary = {
                    "added_packages_count": len(comparison.get("added_packages", [])),
                    "removed_packages_count": len(comparison.get("removed_packages", [])),
                    "version_changes_count": len(comparison.get("version_changes", [])),
                }

        summary_dict = summary if isinstance(summary, dict) else (summary.model_dump() if summary else {})

        return (
            "Please analyze these npm dependency scan results and simplify them for the end user in plain, clear, non-technical English.\n\n"
            f"Project: {project_name or 'Current project'}\n"
            f"Scan Summary: {json.dumps(summary_dict)}\n"
            f"Changes detected: {json.dumps(changes_summary)}\n"
            f"Findings detected: {json.dumps(findings_data)}\n\n"
            "Translate technical supply-chain terms (e.g. provenance, build attestations, install scripts, "
            "transitive expansion, OSV advisories) into friendly, plain-English concepts.\n"
            "Return ONLY valid JSON matching this exact structure:\n"
            "{\n"
            '  "headline": "A quick 1-sentence verdict on this dependency update in plain English",\n'
            '  "summary": "A friendly 2-3 sentence overview explaining what changed and overall risk in plain English",\n'
            '  "risk_level": "safe | low | medium | high",\n'
            '  "key_points": [\n'
            '    "Clear point 1 in simple English",\n'
            '    "Clear point 2 in simple English"\n'
            '  ],\n'
            '  "simplified_findings": [\n'
            '    {\n'
            '      "finding_id": "id from findings data",\n'
            '      "package": "package name",\n'
            '      "version": "version",\n'
            '      "title": "Plain-English title",\n'
            '      "what_happened": "What actually changed in plain words",\n'
            '      "why_it_matters": "Why this matters or what risk it brings",\n'
            '      "recommendation": "What the user should do next"\n'
            '    }\n'
            '  ],\n'
            '  "action_items": [\n'
            '    "Concrete next step 1 in plain English",\n'
            '    "Concrete next step 2 in plain English"\n'
            '  ]\n'
            "}"
        )

    def _fallback_simplification(
        self,
        project_name: str | None,
        summary: ScanSummary | dict[str, Any] | None,
        findings: list[Finding],
        comparison: ScanComparisonResponse | dict[str, Any] | None,
        language: str,
    ) -> SimplifiedAnalysis:
        pkg_count = (
            summary.get("packages")
            if isinstance(summary, dict)
            else (summary.packages if summary else 0)
        )
        findings_count = len(findings)

        high_count = sum(1 for f in findings if f.severity == "high")
        med_count = sum(1 for f in findings if f.severity == "medium")

        if high_count > 0:
            risk = "high"
            headline = f"Attention needed: {high_count} high-priority security item(s) found in dependencies."
        elif med_count > 0:
            risk = "medium"
            headline = f"Review recommended: {med_count} moderate item(s) detected after dependency changes."
        elif findings_count > 0:
            risk = "low"
            headline = f"Minor items noted: {findings_count} informational item(s) found."
        else:
            risk = "safe"
            headline = "All clear: Dependency changes look clean with no security warnings."

        summary_text = (
            f"Analyzed {pkg_count} packages for '{project_name or 'this project'}'. "
            f"Found {findings_count} item(s) to review. "
            f"Signals are pointers for review, not proof that your code is broken."
        )

        key_points = []
        if comparison:
            added = (
                len(comparison.added_packages)
                if isinstance(comparison, ScanComparisonResponse)
                else len(comparison.get("added_packages", []))
            )
            changes = (
                len(comparison.version_changes)
                if isinstance(comparison, ScanComparisonResponse)
                else len(comparison.get("version_changes", []))
            )
            if added or changes:
                key_points.append(f"Detected {added} newly added package(s) and {changes} updated version(s).")

        if findings:
            key_points.append(f"Highest severity item: {findings[0].title} on package {findings[0].package}.")
        else:
            key_points.append("No known vulnerabilities or unusual supply-chain behaviors detected.")

        simplified_findings = [self._fallback_finding(f, language) for f in findings[:10]]

        action_items = []
        if high_count > 0:
            action_items.append("Review packages with high severity before merging or deploying.")
        if med_count > 0:
            action_items.append("Check updated packages to confirm they were intended by your team.")
        if not action_items:
            action_items.append("No immediate action required.")

        return SimplifiedAnalysis(
            headline=headline,
            summary=summary_text,
            risk_level=risk,
            key_points=key_points,
            simplified_findings=simplified_findings,
            action_items=action_items,
        )

    def _fallback_finding(self, f: Finding, language: str) -> SimplifiedFindingItem:
        # Rule-specific plain language explanations
        rule = f.rule_id
        if "vulnerability" in rule or "osv" in rule:
            what = f"The installed version {f.version} of {f.package} has a known public security vulnerability."
            why = "Attackers might be able to exploit this known flaw if the vulnerable code is executed."
            rec = "Update to a patched version of this package as soon as possible."
        elif "provenance" in rule:
            what = f"Package {f.package}@{f.version} no longer includes a cryptographic proof of where it was built."
            why = "Without provenance, you cannot verify that the package was built on a trusted CI system like GitHub Actions."
            rec = "Verify that the maintainer intentionally switched build systems and the package is legitimate."
        elif "publisher" in rule:
            what = f"A different person or account published this version of {f.package}."
            why = "Unexpected maintainer changes sometimes indicate account takeovers."
            rec = "Check the repository commit history to ensure the publisher was officially added to the project."
        elif "install_script" in rule:
            what = f"This package introduced a new install or post-install script that runs automatically."
            why = "Install scripts run arbitrary commands on your computer or build server during npm install."
            rec = "Inspect the package's scripts in package.json to verify what commands are executed."
        elif "release_timing" in rule or "timing" in rule:
            what = f"This package version was released unusually quickly or at an atypical interval."
            why = "Rapid successive releases sometimes indicate a typo-squatted release or hurried patch."
            rec = "Confirm the release notes on GitHub to understand why multiple releases occurred."
        else:
            what = f.explanation
            why = "This behavior differs from typical npm dependency updates."
            rec = f"Review the changes in {f.package}."

        return SimplifiedFindingItem(
            finding_id=f.id,
            package=f.package,
            version=f.version,
            title=f.title,
            what_happened=what,
            why_it_matters=why,
            recommendation=rec,
        )
