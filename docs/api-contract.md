# Provenyx API contract (v0.1.0)

Shared contract between the VS Code extension (`extension/src/types/index.ts`), the dashboard, and the backend (`backend/app/models/schemas.py`). Change all three together.

Base URL (development): `http://localhost:8000`. Interactive docs: `http://localhost:8000/docs`.

## `GET /health`

`200 OK`

```json
{ "status": "ok", "service": "provenyx-api", "version": "0.1.0" }
```

Sends and returns no project data. The extension calls it on activation and before every scan.

## `POST /api/scans`

Submit an npm lockfile. **Phase 1 validates and acknowledges only — no analysis is performed and nothing is stored.**

Request headers: `Content-Type: application/json` (otherwise `415`).

Request body (max 10 MiB, configurable with `PROVENYX_MAX_SCAN_BYTES`; otherwise `413`):

```json
{
  "lockfile": { "name": "my-app", "lockfileVersion": 3, "packages": { "": { "name": "my-app" } } },
  "project_name": "my-app",
  "client": "vscode-extension/0.1.0"
}
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `lockfile` | object | yes | Parsed `package-lock.json`. Unknown keys are allowed and passed through. |
| `lockfile.lockfileVersion` | integer | yes | `1`, `2` or `3`. |
| `lockfile.packages` | object | for v2/v3 | |
| `lockfile.dependencies` | object | for v1 | |
| `project_name` | string ≤ 214 | no | |
| `client` | string ≤ 64 | no | Identifies the caller. |

No other top-level fields are accepted.

`202 Accepted`

```json
{
  "scan_id": "3f1c9a52-6a77-4a8e-9d4e-1c0b2f6f9e10",
  "status": "accepted",
  "message": "Lockfile received. Dependency analysis is not implemented in Phase 1."
}
```

## Errors

| Status | When | Body |
| --- | --- | --- |
| `413` | Body larger than the limit | `{ "detail": "Request body exceeds N bytes" }` |
| `415` | Content-Type is not `application/json` | `{ "detail": "Content-Type must be application/json" }` |
| `422` | Malformed JSON or schema violation | `{ "detail": [ { "type", "loc", "msg" } ] }` (FastAPI format; input values are not echoed) |

## CORS

Browser access is restricted to `PROVENYX_CORS_ORIGINS` (default `http://localhost:3000,http://127.0.0.1:3000`), methods `GET`/`POST`, header `Content-Type`. The extension runs in Node and is not subject to CORS.

## Planned endpoints (owner: Omkar) — agreed shapes

Not implemented yet. The extension (Phase 2) and dashboard (Phase 5) already call these and handle `404`/`405`/`501` as "not available from this API yet", so the backend can ship them one at a time. All are `GET` except verify.

| Endpoint | Purpose | Phase |
| --- | --- | --- |
| `GET /api/scans` | Recent scans, newest first (max 50) | 3 |
| `GET /api/scans/{scan_id}` | Status and summary | 3 |
| `GET /api/scans/{scan_id}/graph` | Dependency nodes and edges | 3 |
| `GET /api/scans/{scan_id}/findings` | Evidence-backed findings | 4 |
| `POST /api/releases/verify` | Compare release metadata with the on-chain manifest hash | 6 |

Unknown `scan_id` → `404 { "detail": "Scan not found" }`.

### Scan — `GET /api/scans/{scan_id}`; `GET /api/scans` returns `{ "scans": [Scan, ...] }`

```jsonc
{
  "scan_id": "uuid",
  "status": "accepted",            // accepted | analyzing | complete | failed
  "created_at": "2026-10-12T10:00:00Z",
  "project_name": "my-app",        // or null
  "error": null,                   // human-readable reason when status = failed
  "summary": {                     // null until status = complete
    "packages": 120, "direct": 8, "transitive": 112, "findings": 2
  }
}
```

### Graph — `GET /api/scans/{scan_id}/graph`

Node `id` is `name@version`, so multiple installed versions stay distinct.

```jsonc
{
  "scan_id": "uuid",
  "root": "my-app@1.0.0",
  "nodes": [
    { "id": "ms@2.1.3", "name": "ms", "version": "2.1.3",
      "direct": true, "dev": false, "lockfile_paths": ["node_modules/ms"] }
  ],
  "edges": [ { "from": "my-app@1.0.0", "to": "ms@2.1.3", "type": "prod" } ]   // prod | dev | optional | peer
}
```

### Findings — `GET /api/scans/{scan_id}/findings`

Every finding carries evidence; no evidence, no finding. `severity` and `confidence` are independent.

```jsonc
{
  "scan_id": "uuid",
  "findings": [
    {
      "id": "uuid",
      "rule_id": "new-dependency",
      "package": "example-pkg", "version": "1.2.0",
      "severity": "medium",          // info | low | medium | high
      "confidence": "high",          // low | medium | high
      "title": "Short, factual headline",
      "explanation": "Why this was flagged and what to check.",
      "evidence": [
        { "source": "lockfile", "field": "packages.node_modules/example-pkg.version", "value": "1.2.0", "observed_at": null }
      ],                              // source: lockfile | npm-registry | release-registry
      "unknowns": ["Publisher history unavailable"],
      "paths": [["my-app@1.0.0", "dep-a@2.0.0", "example-pkg@1.2.0"]]   // root → package, node ids from the graph
    }
  ]
}
```

### Release verification — `POST /api/releases/verify`

Request: `{ "package": "ms", "version": "2.1.3" }`

`release_id` is `keccak256(utf8("<name>@<version>"))` as 0x-prefixed hex — the same id used by `ReleaseRegistry.anchor` (see `contracts/README.md`).

```jsonc
{
  "package": "ms", "version": "2.1.3",
  "release_id": "0x…",
  "status": "match",               // match | mismatch | no_record | unavailable
  "manifest_hash": "0x…",          // hash recomputed now; null if it could not be computed
  "anchored_hash": "0x…",          // hash stored on-chain; null if no record
  "anchored_at": "2026-10-12T10:00:00Z",   // null if no record
  "manifest": { "schema_version": 1, "name": "ms", "version": "2.1.3", "integrity": "sha512-…" },  // canonical fields, or null
  "registry": { "network": "hardhat-local", "chain_id": 31337, "address": "0x…" },             // null if not configured
  "detail": null                   // reason when status = unavailable
}
```

Interpretation rules (UI and API must both follow):

- `match` — metadata equals the approved record. **Not** a safety verdict.
- `mismatch` — metadata differs from the approved record; investigate.
- `no_record` — evidence gap, **not** a risk signal. Must not be reported as a mismatch.
- `unavailable` — chain or metadata unreachable; say so, don't guess.

## Compatibility rules

- Additive response fields are non-breaking; clients must ignore unknown fields.
- Removing/renaming fields or tightening validation requires bumping the API version and updating the extension.
