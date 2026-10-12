# Phase 1 advanced threat detection

Provenyx now adds three deterministic supply-chain signals to the existing scan and pull-request gate flows. Findings remain investigation signals: a match does not by itself prove malware.

## Integration

`ScanService` parses a lockfile, fetches exact-release npm metadata, builds the dependency graph, runs OSV and deterministic rules, optionally inspects selected archives, reranks only when configured, and persists the existing `Finding` JSON shape. `TrustGate` runs the same rules only for added or updated releases. The dashboard and VS Code extension continue to use the existing findings endpoint and require no contract changes.

Registry graph snapshots now retain the release tarball URL and observed maintainer list. These are additive response fields; existing clients can ignore them.

## Detectors and scoring

### Package-name similarity

`possible-typosquatting` uses case-normalized Damerau-Levenshtein distance, including insertion, deletion, substitution, adjacent transposition, duplication, and hyphen-only changes. Exact trusted names are ignored. Scoped names are compared only inside the same scope to reduce unrelated namespace collisions. Only newly introduced package names are checked when a baseline exists.

The default priority is bounded to 58–80 and increases for a direct dependency, distance one, or missing publisher identity. Confidence is medium for distance one and low for the longer-name distance-two case. Configure the reference set with `PROVENYX_TYPOSQUAT_TRUSTED_PACKAGES`.

### Publisher and maintainer intelligence

Publisher changes continue to compare exact release metadata from the persisted baseline and current graph. Maintainer changes are emitted only when both persisted snapshots contain maintainer data. npm does not expose an authoritative ownership timeline, so missing history remains unknown and the evidence records this limitation.

A publisher change has base priority 60. Independent same-release signals add bounded weights: new install script +10, provenance removal +8, dependency expansion +5, suspicious install-time behavior or possible credential exfiltration +15, and credential access +8. The score is capped at 95. Correlation enriches the existing publisher finding instead of creating a duplicate takeover finding.

### Static source indicators

Static inspection is disabled by default. When enabled, it considers newly added or updated releases, orders them by existing risk/directness/install scripts, and inspects at most the configured package count. Results are cached in memory by artifact integrity.

The inspector:

- accepts only credential-free HTTPS URLs on the configured host allowlist;
- streams downloads with timeout and compressed-size limits;
- requires the archive to match lockfile integrity when present (registry integrity is only a fallback);
- reads tar members in memory and never extracts, installs, imports, or executes package code;
- rejects traversal paths, absolute/drive paths, links, unusual entries, excessive files, oversized files, and excessive decompressed size;
- records indicator type, package-relative path, and line number, but never captured secret values.

Lexical rules detect process execution, dynamic evaluation, credential-file/environment access, network behavior, encoded execution, long encoded strings, and excessive string construction. A lone non-install `child_process` call or lone network call is not reported. Correlated credential/network, encoded/dynamic, or install-time combinations receive higher priorities. This is bounded pattern analysis rather than a full JavaScript AST/data-flow engine, so manual review is required.

## Configuration

Copy `backend/.env.example` to `backend/.env`. To enable safe static inspection locally:

```dotenv
PROVENYX_STATIC_ANALYSIS_ENABLED=true
PROVENYX_STATIC_ANALYSIS_ALLOWED_HOSTS=registry.npmjs.org
PROVENYX_STATIC_ANALYSIS_MAX_PACKAGES=20
```

The example file documents all archive, decompression, file-count, file-size, timeout, and concurrency controls. Keep custom registries on an explicit narrow allowlist and serve archives over HTTPS.

## Run locally

From the repository root on Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Run the dashboard separately with the existing frontend instructions, then submit a `package-lock.json` through the dashboard, extension, or `POST /api/scans`.

The CLI trust gate reads the same environment configuration:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.gate --head ..\demo\fixtures\suspicious-update-package-lock.json --base ..\demo\fixtures\baseline-package-lock.json --fail-on medium
```

## Demonstrate and test

The synthetic tests never execute suspicious samples:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_typosquatting.py tests/test_static_analysis.py tests/test_detection_rules.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

For a quick name-similarity demo, scan a lockfile that introduces `expres@1.0.0`; the existing findings endpoint will return `possible-typosquatting`. Static-analysis tests build integrity-pinned in-memory tarballs for install-time execution, credential/network correlation, obfuscation, corrupt archives, traversal, links, size limits, timeout, and integrity mismatch.

## Limitations

- Similar names can be legitimate; the trusted-name set and thresholds need periodic curation.
- npm maintainer arrays are observations, not a historical ownership ledger.
- Downloads/age are not used because no additional popularity API is trusted or required in Phase 1.
- Pattern matching can miss aliases, generated behavior, or complex data flow and can flag legitimate tooling.
- Minification alone is not treated as malicious.
- Failed or unverifiable archive inspection is surfaced as a warning and never treated as a clean result.
