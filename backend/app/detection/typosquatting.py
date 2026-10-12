"""Deterministic npm package-name similarity checks.

Name similarity is an investigation signal only.  The detector deliberately requires a
very small edit distance and contextual evidence, and never flags an exact trusted name.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

from app.detection.rules import _dependency_paths, _finding_id
from app.models.schemas import Finding, FindingEvidence, ScanGraph


DEFAULT_TRUSTED_PACKAGES = frozenset(
    {
        "axios", "chalk", "commander", "debug", "dotenv", "eslint", "express", "jest",
        "lodash", "moment", "mongoose", "next", "nodemon", "prettier", "react", "react-dom",
        "redux", "rxjs", "typescript", "uuid", "vite", "webpack", "yargs", "zod",
        "@angular/core", "@nestjs/core", "@types/node", "@types/react",
    }
)

_VALID_NAME = re.compile(r"^(?:@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*$")


def normalize_package_name(value: str) -> tuple[str | None, str | None]:
    """Return normalized ``(scope, leaf)`` or ``(None, None)`` for malformed names."""
    if not isinstance(value, str):
        return None, None
    normalized = value.strip().lower()
    if not normalized or len(normalized) > 214 or not _VALID_NAME.fullmatch(normalized):
        return None, None
    if normalized.startswith("@"):
        scope, leaf = normalized[1:].split("/", 1)
        return scope, leaf
    return "", normalized


def damerau_levenshtein(left: str, right: str) -> int:
    """Optimal-string-alignment distance, including adjacent transpositions."""
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    matrix = [[0] * (len(right) + 1) for _ in range(len(left) + 1)]
    for i in range(len(left) + 1):
        matrix[i][0] = i
    for j in range(len(right) + 1):
        matrix[0][j] = j
    for i in range(1, len(left) + 1):
        for j in range(1, len(right) + 1):
            cost = 0 if left[i - 1] == right[j - 1] else 1
            matrix[i][j] = min(
                matrix[i - 1][j] + 1,
                matrix[i][j - 1] + 1,
                matrix[i - 1][j - 1] + cost,
            )
            if i > 1 and j > 1 and left[i - 1] == right[j - 2] and left[i - 2] == right[j - 1]:
                matrix[i][j] = min(matrix[i][j], matrix[i - 2][j - 2] + 1)
    return matrix[-1][-1]


def detect_typosquatting(
    current: ScanGraph,
    *,
    candidate_ids: set[str],
    observed_at: datetime,
    trusted_packages: Iterable[str] = DEFAULT_TRUSTED_PACKAGES,
) -> list[Finding]:
    trusted: list[tuple[str, str, str]] = []
    exact: set[str] = set()
    for value in trusted_packages:
        scope, leaf = normalize_package_name(value)
        if leaf is None or scope is None:
            continue
        canonical = f"@{scope}/{leaf}" if scope else leaf
        exact.add(canonical)
        trusted.append((canonical, scope, leaf))

    findings: list[Finding] = []
    for node in current.nodes:
        if node.id not in candidate_ids:
            continue
        scope, leaf = normalize_package_name(node.name)
        if leaf is None or scope is None or len(leaf) < 3:
            continue
        canonical = f"@{scope}/{leaf}" if scope else leaf
        if canonical in exact:
            continue

        matches: list[tuple[int, int, str, str, str]] = []
        for trusted_name, trusted_scope, trusted_leaf in trusted:
            # Scoped packages are compared only within their namespace.  Comparing an arbitrary
            # scope to an unscoped brand produces too many legitimate-name collisions.
            if scope != trusted_scope:
                continue
            distance = damerau_levenshtein(leaf, trusted_leaf)
            compact_distance = damerau_levenshtein(leaf.replace("-", ""), trusted_leaf.replace("-", ""))
            effective = min(distance, compact_distance)
            max_distance = 1 if max(len(leaf), len(trusted_leaf)) < 10 else 2
            if effective <= max_distance and (effective > 0 or distance > 0):
                matches.append((effective, distance, trusted_name, leaf, trusted_leaf))
        if not matches:
            continue
        effective_distance, edit_distance, similar_to, candidate_leaf, trusted_leaf = min(
            matches, key=lambda item: (item[0], item[1], item[2])
        )
        publisher_known = bool(node.registry.publisher)
        priority = min(80, 58 + (8 if node.direct else 0) + (4 if not publisher_known else 0) + (4 if effective_distance <= 1 else 0))
        transformation = _transformation(candidate_leaf, trusted_leaf)
        findings.append(
            Finding(
                id=_finding_id(current.scan_id, "possible-typosquatting", node.id),
                rule_id="possible-typosquatting",
                package=node.name,
                version=node.version,
                severity="medium",
                confidence="medium" if effective_distance <= 1 else "low",
                priority_score=priority,
                title="Package name resembles a trusted package",
                explanation=(
                    f"{node.name!r} is {transformation} from trusted package {similar_to!r}. "
                    "Similar names can be legitimate; verify the requested dependency, publisher, and project links."
                ),
                evidence=[
                    FindingEvidence(
                        source="lockfile",
                        field="package_name_similarity",
                        value={
                            "similar_to": similar_to,
                            "edit_distance": edit_distance,
                            "transformation": transformation,
                            "newly_introduced": True,
                            "publisher": node.registry.publisher,
                            "publisher_known": publisher_known,
                        },
                        observed_at=observed_at,
                    )
                ],
                paths=_dependency_paths(current, node.id),
            )
        )
    return sorted(findings, key=lambda finding: (-finding.priority_score, finding.package, finding.version))


def _transformation(candidate: str, trusted: str) -> str:
    if candidate.replace("-", "") == trusted.replace("-", ""):
        return "a hyphen insertion or removal"
    if len(candidate) == len(trusted) and sum(a != b for a, b in zip(candidate, trusted)) == 2:
        for index in range(len(candidate) - 1):
            if candidate[index:index + 2] == trusted[index:index + 2][::-1]:
                return "an adjacent-character transposition"
    if len(candidate) < len(trusted):
        return "a character deletion"
    if len(candidate) > len(trusted):
        return "a character insertion or duplication"
    return "a character substitution"
