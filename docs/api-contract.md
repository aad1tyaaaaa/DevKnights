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

Submit an npm lockfile. The API validates it, stores a local snapshot, and starts dependency analysis in a background task.

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
  "message": "Lockfile received. Dependency analysis has started."
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

## Scan results

| Endpoint | Purpose |
| --- | --- |
| `GET /api/scans` | Recent persisted scans, newest first |
| `GET /api/scans/{scan_id}` | Status and summary |
| `GET /api/scans/{scan_id}/findings` | Evidence-backed findings |
| `GET /api/scans/{scan_id}/graph` | Dependency nodes and edges |
| `GET /api/scans/{scan_id}/compare/{baseline_scan_id}` | Additions, removals, upgrades, and new edges |
| `POST /api/releases/verify` | Compare release metadata with the on-chain manifest hash (Phase 6, not implemented) |

Implemented scan schemas:

```jsonc
// GET /api/scans/{scan_id}
{ "scan_id": "uuid", "status": "accepted | analyzing | complete | failed",
  "created_at": "ISO-8601", "project_name": "string|null",
  "summary": { "packages": 0, "direct": 0, "transitive": 0, "findings": 0 },
  "warnings": [], "error": null }

// Finding — every finding must carry evidence; no evidence, no finding
{ "id": "uuid", "rule_id": "string", "package": "name", "version": "x.y.z",
  "severity": "info | low | medium | high", "confidence": "low | medium | high",
  "priority_score": 0,
  "title": "string", "explanation": "string",
  "evidence": [ { "source": "npm-registry | lockfile | registry-contract", "field": "string", "value": "any", "observed_at": "ISO-8601" } ],
  "paths": [ ["root", "dep-a", "package"] ] }

// GET /api/scans/{scan_id}/graph
// Node id is "name@version" so multiple installed versions stay distinct.
{ "scan_id": "uuid", "status": "complete",
  "nodes": [ { "id": "name@version", "name": "string", "version": "string",
    "direct": true, "lockfile_paths": ["node_modules/..."],
    "resolved_urls": ["https://registry.npmjs.org/..."],
    "lockfile_integrities": ["sha512-..."],
    "registry": { "status": "available | unavailable", "description": "string|null",
      "license": "string|null", "deprecated": "string|null", "published_at": "ISO-8601|null",
      "dist_integrity": "sha512-...|null", "error": "string|null" } } ],
  "edges": [ { "from": "name@version", "to": "name@version", "type": "prod | dev | optional | peer" } ],
  "warnings": [] }

// GET /api/scans/{scan_id}/compare/{baseline_scan_id}
{ "baseline_scan_id": "uuid", "current_scan_id": "uuid",
  "added_packages": ["name@version"], "removed_packages": ["name@version"],
  "version_changes": [ { "name": "name", "from_versions": ["1.0.0"], "to_versions": ["2.0.0"] } ],
  "added_edges": [ { "from": "parent@version", "to": "child@version", "type": "prod" } ] }

// Release verification result
{ "release_id": "0x…", "status": "match | mismatch | no_record | unavailable", "manifest_hash": "0x…" }
// "no_record" is an evidence gap, not a risk signal. "match" is not a safety verdict.
```

## Compatibility rules

- Additive response fields are non-breaking; clients must ignore unknown fields.
- Removing/renaming fields or tightening validation requires bumping the API version and updating the extension.
