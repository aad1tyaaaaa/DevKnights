# Phase 3: attack simulation, validation, and judge demo

Phase 3 adds a safe, offline demonstration and an independent synthetic holdout evaluation. It
does not add findings to production responses, change detector thresholds, execute package code,
or depend on live npm, OSV, Gemini, blockchain, or GitHub services.

## Architecture

The `phase3_demo` package is an adapter around the existing architecture:

1. A scenario supplies baseline and modified npm lockfile dictionaries, exact synthetic registry
   snapshots, and (only where needed) a harmless in-memory tar archive.
2. `ScanService` parses each lockfile, builds the dependency graph, executes existing deterministic
   rules, performs bounded static inspection, enriches findings, and persists both scans in an
   isolated in-memory SQLite database.
3. `ScanService.compare_scans` reports added, removed, and updated package releases.
4. The runner compares persisted findings to identify new/resolved findings and priority changes.
5. The existing `TrustGate` independently evaluates the same lockfile diff at `fail_on=medium`.
6. The CLI projects these existing results into compact Markdown or JSON. There is no application-
   level risk score; every priority remains attached to an individual finding.

## Files created and modified

- `backend/phase3_demo/scenarios.py` — fixed synthetic scenario definitions and in-memory archive.
- `backend/phase3_demo/runner.py` — reusable scan/compare/gate workflow and structured report.
- `backend/phase3_demo/__main__.py` — Markdown/JSON command-line interface.
- `backend/benchmarks/phase3_holdout.py` — separate 20-case fixed holdout evaluator.
- `backend/benchmarks/phase3_holdout_report.md` — checked-in output from that evaluator.
- `backend/tests/test_phase3_simulation.py` — five-scenario and API/persistence integration tests.
- `backend/tests/test_phase3_holdout.py` — reproducibility and checked-in-report tests.
- `demo/README.md` — quick Phase 3 commands.
- `docs/phase3-attack-simulation.md` — this architecture, validation, and demo guide.

No frontend, extension, API schema, production configuration, blockchain contract, or security
threshold was changed.

## Scenarios

| Identifier | Before/after change | Expected demonstration |
|---|---|---|
| `typosquatting-attack` | Adds synthetic `expres@1.0.0` beside `express@4.18.2` | Name-similarity evidence, deterministic priority, remediation, and gate failure |
| `suspicious-package-update` | Updates a synthetic package from 1.0.0 to 2.0.0 | Install-script change plus correlated, file-level static indicators from an integrity-pinned in-memory archive |
| `publisher-change` | Changes publisher, adds an install script, and removes provenance | Reliable baseline/current snapshot comparison, correlated evidence, uncertainty, and ownership verification guidance |
| `transitive-dependency-compromise` | Adds `app -> package-a -> package-b -> lodahs` | Exact release/path, introducing direct dependency, bounded impact, reachability limitation, and gate failure |
| `legitimate-update` | Updates 1.0.0 to 1.1.0 with stable metadata | Version change with no unsupported security claim and a passing gate |

All names beginning with `provenyx-synthetic-` and all scenario identities are fictional fixtures.
`expres` and `lodahs` are used only as lockfile strings; the demo never downloads those packages.

## Safety controls

- Package code is never installed, imported, evaluated, or executed.
- The suspicious JavaScript is inert source text inside an in-memory tar archive.
- The only outbound-looking URL in source text uses the reserved `invalid.test` domain and is never
  requested.
- The archive itself is served by `httpx.MockTransport`, must match its synthetic SHA-512 lockfile
  integrity, and is read with the existing archive/file/decompression limits.
- Registry and OSV clients are fixture adapters with no network implementation.
- Gemini and blockchain verification are not configured.
- Scan persistence uses a new in-memory SQLite database for every scenario.
- Reports label scenarios as synthetic and preserve detector uncertainty.

## Before-and-after report

Every report contains:

- scenario identifier, title, description, and synthetic label;
- baseline and modified dependency sets, status, warning list, and finding counts;
- added/removed releases and version changes from the existing graph comparer;
- new and resolved findings plus per-rule/package priority changes;
- evidence, dependency paths, bounded blast-radius objects, and remediation actions;
- the complete existing trust-gate report and verdict;
- evidence-source names and deduplicated analysis limitations.

`affected_package_count` retains the Phase 2 definition: unique installed release nodes that are the
target or can reach it. It is dependency reachability, not runtime execution or exploitability.

## Phase 2 integration verification

The Phase 2 path was traced before adding demo code:

- `ScanService.analyze_scan` calls `enrich_findings` before persistence, even when Gemini is disabled.
- `ScanRepository.set_complete` stores the complete additive finding JSON.
- `GET /api/scans/{id}/findings` validates and returns the current `Finding` model.
- `frontend/lib/types.ts` includes `threat_explanation`, `remediation`, and `blast_radius`.
- `frontend/components/package-detail-drawer.tsx` renders all three and handles absent values.
- `extension/src/types/index.ts` includes the fields and `findingsTreeProvider.ts` displays the
  supported explanation, recommendation, and impact summary.

No integration defect was found. `test_phase2_fields_survive_persistence_and_api_serialization`
now protects the full AI-disabled scan -> persistence -> API path and verifies deterministic
explanations, remediation, and shortest paths. Older stored findings remain compatible because the
additive client fields are optional.

## End-to-end and edge validation

`test_phase3_simulation.py` drives baseline scan, parsing, graph construction, detection,
persistence, modified scan, comparison, enrichment, impact analysis, gate evaluation, and API
serialization. External providers are mocked.

The complete backend suite covers the required failure and limit cases across these tests:

| Edge case | Coverage |
|---|---|
| Missing npm metadata / publisher history | detection-rule, scan-service, and gate tests keep unknown evidence unknown |
| Registry timeout | npm-registry and static-analysis timeout tests |
| OSV unavailable | OSV/scan/gate tests preserve an explicit unknown warning |
| Gemini unavailable | AI-ranker tests retain deterministic content |
| Invalid lockfile | scan API and end-to-end validation tests return bounded 422 errors |
| Scoped packages / multiple installed versions | typosquatting and graph-builder tests |
| Circular / large graphs and truncated paths | impact-analysis bounded traversal tests |
| No findings / legitimate update | `legitimate-update` scenario |
| Duplicate/correlated findings | publisher-correlation tests enrich rather than duplicate |
| Static resource limits / unverified integrity | static-analysis archive, size, timeout, and integrity tests |
| Suspicious update | `suspicious-package-update` scan/API/gate tests |

## Independent holdout methodology and actual result

The Phase 3 holdout is separate from the original 16-case Phase 2 report. Its 20 examples use
different names and source snippets, include ambiguous evidence and difficult benign near misses,
and were labeled before execution. Production thresholds were not changed after observing results.

The positive class is **a synthetic scenario warranting investigation**, not confirmed malware.

Actual output:

| Cases | TP | FP | TN | FN | Precision | Recall | F1 | False-positive rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 10 | 2 | 8 | 0 | 0.833 | 1.000 | 0.909 | 0.200 |

The two false positives are deliberately difficult benign cases: a conventional native build
command and a small base64-decoded data value. This exposes where lexical static analysis needs
human review or future context-aware suppression. The result is not a real-world npm malware
accuracy claim.

Reproduce it:

```powershell
cd backend
.\.venv\Scripts\python.exe -m benchmarks.phase3_holdout --format markdown
.\.venv\Scripts\python.exe -m benchmarks.phase3_holdout --format json
```

The original Phase 2 report and runner are unchanged.

## Actual validation results

Executed on Windows from this feature branch:

```text
backend full suite:        143 passed
Phase 3 focused tests:       6 passed
frontend typecheck:          passed (tsc --noEmit)
extension typecheck:         passed (tsc --noEmit)
Phase 2 benchmark:           16 cases, 7 TP / 0 FP / 9 TN / 0 FN
Phase 3 holdout:             20 cases, 10 TP / 2 FP / 8 TN / 0 FN
git diff --check:            passed
```

These are the outputs of commands run after the implementation, not estimates. The final Git status
contains only the Phase 3 files listed above; nothing was committed, pushed, merged, or deployed.

## Windows PowerShell setup and commands

Install the existing backend dependencies once, if needed:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the recommended 90–120 second scenario:

```powershell
.\.venv\Scripts\python.exe -m phase3_demo --scenario transitive-dependency-compromise --format markdown
```

Run the suspicious static-update scenario or all five reports:

```powershell
.\.venv\Scripts\python.exe -m phase3_demo --scenario suspicious-package-update --format markdown
.\.venv\Scripts\python.exe -m phase3_demo --scenario all --format json
```

No backend server, OAuth app, network, Gemini key, npm install, or blockchain node is required.

## Judge walkthrough (90–120 seconds)

1. State that the scenario is synthetic, offline, and non-executing.
2. Run the transitive scenario command above.
3. Point out the baseline package count and the one added exact release.
4. Show `possible-typosquatting`, its severity/confidence, and deterministic priority.
5. Read the exact `root -> package-a -> package-b -> lodahs` shortest path.
6. Point out `package-a` as the introducing direct dependency and the bounded affected-node count.
7. Read the reachability limitation: a path does not prove runtime execution.
8. Show the rule-specific package-name verification recommendation.
9. Finish with the existing trust gate's `FAIL` verdict at `fail_on=medium`.
10. If time remains, run `legitimate-update` and show zero findings plus `PASS` for false-positive
    control.

To show the same schema in the dashboard, start the normal backend/frontend, submit the baseline and
modified lockfiles from an equivalent synthetic fixture in order, then open the modified scan. The
CLI is the preferred judge path because it is faster and requires no GitHub OAuth.

## Known limitations

- The scenario and holdout corpora are synthetic and small.
- Lexical analysis does not perform JavaScript AST, control-flow, or data-flow analysis.
- Publisher snapshots show observed identity changes, not whether a transfer was authorized.
- Similar names can be legitimate; name findings require human verification.
- Missing external evidence stays unknown and can reduce coverage.
- Path bounds can omit alternate paths; truncation is explicit.
- Dependency reachability does not prove import, runtime execution, exploitability, or compromise.
- The report does not invent an application-wide risk score.

## Troubleshooting

- `No module named phase3_demo`: run the command from `backend`, not the repository root.
- Virtual-environment executable not found: create `.venv` and install `backend/requirements.txt`.
- A scenario unexpectedly accesses the network: stop the run and verify the working tree; the
  fixture registry, OSV adapter, and archive `MockTransport` must remain configured.
- Static scenario reports an integrity limitation: regenerate neither finding nor digest manually;
  confirm the unchanged in-memory archive and lockfile integrity are paired in `scenarios.py`.
- Terminal glyphs render incorrectly: use JSON output or a UTF-8 PowerShell terminal; the data is
  unchanged.
- A gate verdict differs after intentional policy changes: compare the scenario's finding severities
  to the configured `fail_on` threshold rather than hardcoding a verdict.
