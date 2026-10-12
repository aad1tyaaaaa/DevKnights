"""Bounded, non-executing inspection of verified npm tarballs.

This is intentionally a lightweight lexical analyzer, not a JavaScript parser.  It reports
deterministic indicators and correlations without claiming that matched code is malware.
Archives are never extracted and package code is never imported or executed.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import posixpath
import re
import tarfile
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

import httpx

from app.detection.rules import _dependency_paths, _finding_id
from app.models.schemas import Finding, FindingEvidence, GraphNode, ScanGraph


@dataclass(frozen=True)
class StaticAnalysisLimits:
    max_archive_bytes: int = 8 * 1024 * 1024
    max_decompressed_bytes: int = 32 * 1024 * 1024
    max_files: int = 2_000
    max_file_bytes: int = 512 * 1024
    timeout_seconds: float = 8.0
    concurrency: int = 3


@dataclass(frozen=True)
class CodeIndicator:
    kind: str
    label: str
    path: str
    line: int


@dataclass(frozen=True)
class InspectedFile:
    path: str
    install_reachable: bool
    indicators: tuple[CodeIndicator, ...]


@dataclass(frozen=True)
class StaticInspection:
    identity: str | None
    verified: bool
    files: tuple[InspectedFile, ...] = ()
    limitation: str | None = None


_CODE_SUFFIXES = (".js", ".cjs", ".mjs", ".jsx", ".ts", ".tsx")
_PROCESS = re.compile(
    r"(?:child_process\s*\.\s*(?:exec|execSync|spawn|spawnSync)|"
    r"require\s*\(\s*['\"]child_process['\"]\s*\)\s*\.\s*(?:exec|execSync|spawn|spawnSync)|"
    r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*require\s*\(\s*['\"]child_process['\"]\s*\)"
    r"[\s\S]{0,2000}?\1\s*\.\s*(?:exec|execSync|spawn|spawnSync))"
)
_DYNAMIC = re.compile(r"(?:\beval\s*\(|\bnew\s+Function\s*\(|\brequire\s*\(\s*[^'\"\s][^)]*\))")
_CREDENTIAL = re.compile(
    r"(?:\.npmrc|(?:^|[/\\])\.env(?:\b|[/\\])|id_(?:rsa|dsa|ecdsa|ed25519)|"
    r"\.aws[/\\]credentials|\.config[/\\]gcloud|process\.env\s*(?:\.\s*|\[\s*['\"]?)"
    r"(?:[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|PRIVATE_KEY|ACCESS_KEY)[A-Z0-9_]*))",
    re.IGNORECASE,
)
_NETWORK = re.compile(
    r"(?:https?://|\b(?:fetch|axios\.(?:get|post|request)|https?\.(?:get|request))\s*\(|"
    r"require\s*\(\s*['\"]https?['\"]\s*\))",
    re.IGNORECASE,
)
_BASE64_EXEC = re.compile(
    r"(?:Buffer\.from\s*\([^)]{0,500}['\"]base64['\"]|atob\s*\(|fromBase64|base64.*(?:eval|Function))",
    re.IGNORECASE,
)
_LONG_ENCODED = re.compile(r"['\"][A-Za-z0-9+/]{240,}={0,2}['\"]")
_CONCATENATION = re.compile(r"(?:['\"][^'\"]{0,20}['\"]\s*\+\s*){10,}")
_SCRIPT_TARGET = re.compile(r"(?:^|\s)(?:node\s+)?([./A-Za-z0-9_@-]+\.(?:c?js|mjs|ts))(?:\s|$)")


class StaticArtifactInspector:
    def __init__(
        self,
        *,
        allowed_hosts: set[str],
        limits: StaticAnalysisLimits | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.allowed_hosts = {host.lower() for host in allowed_hosts if host}
        self.limits = limits or StaticAnalysisLimits()
        self.transport = transport
        self._cache: dict[str, StaticInspection] = {}

    async def analyze(
        self,
        graph: ScanGraph,
        *,
        candidate_ids: list[str],
        observed_at: datetime,
    ) -> tuple[list[Finding], list[str]]:
        nodes = {node.id: node for node in graph.nodes}
        semaphore = asyncio.Semaphore(max(1, self.limits.concurrency))

        async def inspect(node: GraphNode) -> tuple[GraphNode, StaticInspection]:
            async with semaphore:
                return node, await self.inspect_node(node)

        results = await asyncio.gather(*(inspect(nodes[node_id]) for node_id in candidate_ids if node_id in nodes))
        findings: list[Finding] = []
        warnings: list[str] = []
        for node, result in results:
            if result.limitation:
                warnings.append(f"Static inspection skipped for {node.id}: {result.limitation}")
                continue
            findings.extend(_findings_for_inspection(graph, node, result, observed_at))
        return findings, warnings

    async def inspect_node(self, node: GraphNode) -> StaticInspection:
        url = node.registry.tarball_url or next(iter(node.resolved_urls), None)
        if not url:
            return StaticInspection(None, False, limitation="no package archive URL was available")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.username or parsed.password or not parsed.hostname:
            return StaticInspection(None, False, limitation="archive URL was not a credential-free HTTPS URL")
        if parsed.hostname.lower() not in self.allowed_hosts:
            return StaticInspection(None, False, limitation="archive URL host is not in the trusted registry allowlist")

        lockfile_integrities = list(node.lockfile_integrities)
        registry_integrities = [node.registry.dist_integrity] if node.registry.dist_integrity else []
        integrities = [*lockfile_integrities, *registry_integrities]
        identity = next((value for value in integrities if value), None)
        if not identity:
            return StaticInspection(None, False, limitation="no trusted integrity value was available")
        if identity in self._cache:
            return self._cache[identity]

        try:
            archive = await self._download(url)
        except (httpx.HTTPError, ValueError) as exc:
            return StaticInspection(identity, False, limitation=f"archive retrieval failed ({type(exc).__name__})")
        # A lockfile pin is the expected artifact identity and takes precedence.  A matching
        # registry digest must never mask a lockfile-integrity mismatch.
        required_integrities = lockfile_integrities or registry_integrities
        if not _matches_any_integrity(archive, required_integrities):
            result = StaticInspection(identity, False, limitation="archive integrity did not match lockfile or registry metadata")
            return result
        try:
            files = _inspect_archive(archive, self.limits)
        except (tarfile.TarError, ValueError, OSError) as exc:
            result = StaticInspection(identity, True, limitation=f"archive was rejected ({str(exc)})")
            self._cache[identity] = result
            return result
        result = StaticInspection(identity, True, files=files)
        self._cache[identity] = result
        return result

    async def _download(self, url: str) -> bytes:
        timeout = httpx.Timeout(self.limits.timeout_seconds)
        async with httpx.AsyncClient(
            timeout=timeout,
            transport=self.transport,
            follow_redirects=False,
        ) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                length = response.headers.get("content-length")
                if length and int(length) > self.limits.max_archive_bytes:
                    raise ValueError("archive exceeds compressed size limit")
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > self.limits.max_archive_bytes:
                        raise ValueError("archive exceeds compressed size limit")
                    chunks.append(chunk)
                return b"".join(chunks)


def _inspect_archive(archive: bytes, limits: StaticAnalysisLimits) -> tuple[InspectedFile, ...]:
    sources: dict[str, str] = {}
    package_json: dict = {}
    total_size = 0
    count = 0
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:*") as bundle:
        for member in bundle:
            count += 1
            if count > limits.max_files:
                raise ValueError("file count limit exceeded")
            path = _safe_member_path(member.name)
            if member.issym() or member.islnk():
                raise ValueError("symlink or hardlink entry")
            if not (member.isfile() or member.isdir()):
                raise ValueError("unusual archive entry type")
            if member.size < 0 or member.size > limits.max_file_bytes:
                raise ValueError("individual file size limit exceeded")
            total_size += member.size
            if total_size > limits.max_decompressed_bytes:
                raise ValueError("decompressed size limit exceeded")
            if member.isdir():
                continue
            if not (path.endswith(_CODE_SUFFIXES) or path.endswith("/package.json") or path == "package.json"):
                continue
            stream = bundle.extractfile(member)
            if stream is None:
                raise ValueError("unreadable regular file")
            raw = stream.read(limits.max_file_bytes + 1)
            if len(raw) > limits.max_file_bytes:
                raise ValueError("individual file size limit exceeded")
            text = raw.decode("utf-8", errors="replace")
            if path.endswith("/package.json") or path == "package.json":
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        package_json = parsed
                except (ValueError, TypeError):
                    pass
            elif path.endswith(_CODE_SUFFIXES):
                sources[path] = text

    targets = _install_targets(package_json)
    inspected: list[InspectedFile] = []
    for path, source in sorted(sources.items()):
        reachable = _matches_install_target(path, targets)
        indicators = tuple(_scan_source(path, source))
        if indicators:
            inspected.append(InspectedFile(path=path, install_reachable=reachable, indicators=indicators))
    return tuple(inspected)


def _safe_member_path(value: str) -> str:
    normalized = posixpath.normpath(value.replace("\\", "/"))
    if not value or value.startswith(("/", "\\")) or normalized in ("", ".", "..") or normalized.startswith("../"):
        raise ValueError("unsafe archive path")
    if re.match(r"^[A-Za-z]:", normalized):
        raise ValueError("unsafe archive path")
    return normalized


def _install_targets(package_json: dict) -> set[str]:
    scripts = package_json.get("scripts")
    if not isinstance(scripts, dict):
        return set()
    targets: set[str] = set()
    for name in ("preinstall", "install", "postinstall"):
        command = scripts.get(name)
        if not isinstance(command, str):
            continue
        targets.update(match.group(1).lstrip("./") for match in _SCRIPT_TARGET.finditer(command))
    return targets


def _matches_install_target(path: str, targets: set[str]) -> bool:
    package_path = path.removeprefix("package/")
    return any(package_path == target or package_path.endswith("/" + target) for target in targets)


def _scan_source(path: str, source: str) -> list[CodeIndicator]:
    indicators: list[CodeIndicator] = []
    patterns = (
        ("process-execution", "Process execution", _PROCESS),
        ("dynamic-code", "Dynamic code execution", _DYNAMIC),
        ("credential-access", "Potential credential access", _CREDENTIAL),
        ("network", "Outbound network communication", _NETWORK),
        ("obfuscation", "Encoded or heavily constructed code", _BASE64_EXEC),
        ("obfuscation", "Large encoded string", _LONG_ENCODED),
        ("obfuscation", "Excessive string concatenation", _CONCATENATION),
    )
    for kind, label, pattern in patterns:
        match = pattern.search(source)
        if match:
            indicators.append(CodeIndicator(kind, label, path, source.count("\n", 0, match.start()) + 1))
    return indicators


def _matches_any_integrity(data: bytes, integrity_values: list[str]) -> bool:
    for value in integrity_values:
        for token in value.split():
            algorithm, separator, encoded = token.partition("-")
            if not separator or algorithm not in hashlib.algorithms_available:
                continue
            try:
                expected = base64.b64decode(encoded, validate=True)
            except ValueError:
                continue
            if hashlib.new(algorithm, data).digest() == expected:
                return True
    return False


def _findings_for_inspection(
    graph: ScanGraph,
    node: GraphNode,
    inspection: StaticInspection,
    observed_at: datetime,
) -> list[Finding]:
    findings: list[Finding] = []
    for item in inspection.files:
        kinds = {indicator.kind for indicator in item.indicators}
        correlated = (
            ("credential-access" in kinds and "network" in kinds)
            or ("dynamic-code" in kinds and "obfuscation" in kinds)
            or (item.install_reachable and "process-execution" in kinds and len(kinds) > 1)
        )
        if kinds == {"network"} or (kinds == {"process-execution"} and not item.install_reachable):
            continue
        if item.install_reachable and "process-execution" in kinds and correlated:
            rule_id, priority = "suspicious-install-time-behavior", 88
        elif "credential-access" in kinds and "network" in kinds:
            rule_id, priority = "possible-credential-exfiltration", 82
        elif "dynamic-code" in kinds and "obfuscation" in kinds:
            rule_id, priority = "obfuscated-dynamic-code", 78
        elif item.install_reachable and "process-execution" in kinds:
            rule_id, priority = "install-time-process-execution", 65
        elif "dynamic-code" in kinds:
            rule_id, priority = "dynamic-code-execution", 60
        elif "credential-access" in kinds:
            rule_id, priority = "potential-credential-access", 50
        elif "obfuscation" in kinds:
            rule_id, priority = "obfuscation-indicator", 45
        else:
            continue
        severity = "high" if priority >= 80 else "medium" if priority >= 60 else "low"
        findings.append(
            Finding(
                id=_finding_id(graph.scan_id, rule_id, f"{node.id}:{item.path}"),
                rule_id=rule_id,
                package=node.name,
                version=node.version,
                severity=severity,
                confidence="medium" if correlated or item.install_reachable else "low",
                priority_score=min(100, priority),
                title="Suspicious install-time behavior" if item.install_reachable else "Suspicious static code indicators",
                explanation=(
                    f"Static inspection found {len(item.indicators)} indicator(s) in {item.path}. "
                    "The archive matched trusted integrity metadata, but lexical matches do not prove malicious intent. "
                    "Review the file and package ownership before approving this release."
                ),
                evidence=[
                    FindingEvidence(
                        source="static-analysis",
                        field="code_indicators",
                        value={
                            "artifact_identity": inspection.identity,
                            "integrity_verified": inspection.verified,
                            "file_path": item.path,
                            "install_reachable": item.install_reachable,
                            "indicators": [
                                {"type": indicator.kind, "label": indicator.label, "line": indicator.line}
                                for indicator in item.indicators
                            ],
                            "analysis_method": "bounded lexical pattern matching",
                        },
                        observed_at=observed_at,
                    )
                ],
                paths=_dependency_paths(graph, node.id),
            )
        )
    return findings
