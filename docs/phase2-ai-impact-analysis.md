# Phase 2: AI security intelligence and impact analysis

Phase 2 enriches every finding with deterministic explanation, remediation, and bounded dependency-impact data. Gemini can optionally improve explanation wording for important findings, but deterministic detection, severity, confidence, priority, and gate verdicts remain authoritative.

## Architecture and data flow

1. Existing deterministic rules create evidence-backed `Finding` objects.
2. `detection/intelligence.py` adds a deterministic `threat_explanation` and rule-specific `remediation` actions.
3. `graph/impact.py` calculates bounded `blast_radius` data from stable `name@version` graph node IDs.
4. Optional Gemini ranking and explanations run after deterministic enrichment. Provider errors add a warning and preserve deterministic content.
5. The existing JSON persistence, scan endpoints, dashboard, extension, and PR gate consume the additive fields without a database migration.

## Evidence-grounded AI

The Gemini prompt never includes package names, versions, descriptions, publisher names, source text, raw evidence values, lockfiles, credentials, tokens, or file contents. The provider receives opaque finding IDs, controlled rule/severity/confidence labels, deterministic priority, evidence source/field descriptors, direct/transitive status, and deterministic allowed investigation actions.

Responses must match a Pydantic schema, cover every requested finding exactly once, and reference valid evidence indexes. Text lengths, list lengths, HTTP timeouts, retry counts, and response caching are bounded. Model output cannot change deterministic scores, remediation, or gate decisions.

Example AI-assisted explanation:

```json
{
  "source": "gemini",
  "what_was_detected": "Release publisher changed",
  "why_it_may_be_risky": "A publisher change can indicate an expected ownership transition or an unauthorized release, so the release identity should be verified.",
  "evidence_summary": ["npm-registry: publisher_change"],
  "uncertainty": "The registry observation does not establish malicious intent or compromise.",
  "investigation_steps": ["Verify the ownership change through the project's official channels."]
}
```

When Gemini is disabled or unavailable, the same fields are populated with deterministic wording and `source: "deterministic"`.

## Blast-radius algorithm

The impact analyzer builds a directed NetworkX graph from the scan snapshot and:

- enumerates deterministic simple paths from direct dependencies with configurable path/depth limits;
- prevents cycles by disallowing repeated node IDs in a path;
- calculates an independently bounded shortest path;
- reports every direct dependency that can introduce the target;
- counts unique root-reachable upstream package-release nodes plus the target;
- reports bounded upstream dependents and enumerated path concentration per direct branch;
- marks truncated path/dependent collections explicitly.

Example:

```json
{
  "target_node_id": "suspicious-package@2.0.0",
  "direct": false,
  "reachable": true,
  "shortest_path": ["root", "package-a@1.0.0", "package-b@3.0.0", "suspicious-package@2.0.0"],
  "introducing_direct_dependencies": ["package-a@1.0.0"],
  "affected_package_count": 4,
  "branch_path_counts": {"package-a@1.0.0": 1},
  "paths_truncated": false,
  "reachability_note": "A dependency path shows that installation resolution can reach the package. It does not prove that application code imports or executes the package."
}
```

`affected_package_count` means unique installed package-release nodes that are the target or can reach it from a root dependency. It describes dependency reachability, not runtime impact.

## Deterministic remediation

Recommendations are mapped by rule and work without AI. For example:

```json
[
  {
    "action": "Verify the intended package name against the project manifest and upstream documentation.",
    "rationale": "A near-match can result from a typing error or intentional impersonation.",
    "confidence": "high",
    "limitation": null
  }
]
```

Known-vulnerability remediation uses fixed versions only when collected evidence explicitly contains them. Otherwise it instructs the developer to review OSV and states that no alternate version was verified as safe.

## Configuration

```dotenv
PROVENYX_AI_RANKING_ENABLED=false
PROVENYX_AI_EXPLANATIONS_ENABLED=false
PROVENYX_AI_EXPLANATION_MIN_PRIORITY=50
PROVENYX_GEMINI_API_KEY=configure-locally
PROVENYX_GEMINI_TIMEOUT_SECONDS=10
PROVENYX_GEMINI_RETRIES=1
PROVENYX_GEMINI_CACHE_ENABLED=true

PROVENYX_BLAST_RADIUS_MAX_PATHS=25
PROVENYX_BLAST_RADIUS_MAX_DEPTH=20
PROVENYX_BLAST_RADIUS_MAX_UPSTREAM_DEPENDENTS=100
```

AI remains opt-in. Blast-radius analysis and deterministic explanations/remediation are always available.

## Benchmark

Run the offline suite:

```powershell
cd backend
.\.venv\Scripts\python.exe -m benchmarks.detection_benchmark --format markdown
.\.venv\Scripts\python.exe -m benchmarks.detection_benchmark --format json
```

The checked-in [benchmark report](../backend/benchmarks/report.md) measures 16 synthetic cases:

- TP: 7
- FP: 0
- TN: 9
- FN: 0
- Precision: 1.000
- Recall: 1.000
- F1: 1.000
- False-positive rate: 0.000

These numbers are actual outputs from the reproducible runner, but they must not be interpreted as real-world malware-detection performance. The corpus is synthetic, behavior classes overlap unit-test categories, and it is not an independent ecosystem sample. Ground truth means “expected investigation indicator,” not confirmed malware.

## Testing

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm.cmd run typecheck

cd ..\extension
npm.cmd run check-types
```

## Known limitations

- Structured validation cannot prove that every model sentence is semantically perfect; deterministic evidence remains visible and authoritative.
- Static patterns and synthetic benchmarks do not replace expert review or real-world validation datasets.
- Path limits can truncate alternate routes; truncation is reported.
- Dependency reachability does not establish import, runtime execution, exploitability, or compromise.
- OSV integration preserves exact npm versions from advisory `fixed` events, but does not infer safety from ranges or claim that unlisted versions are safe.
- Gemini caching is in-memory and process-local.
