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

## Planned endpoints (not implemented — draft shapes for Phase 2+)

| Endpoint | Purpose |
| --- | --- |
| `GET /api/scans/{scan_id}` | Status and summary |
| `GET /api/scans/{scan_id}/findings` | Evidence-backed findings |
| `GET /api/scans/{scan_id}/graph` | Dependency nodes and edges |
| `POST /api/releases/verify` | Compare release metadata with the on-chain manifest hash |

Draft schemas (subject to change until implemented):

```jsonc
// Scan
{ "scan_id": "uuid", "status": "accepted | analyzing | complete | failed",
  "created_at": "ISO-8601", "project_name": "string|null",
  "summary": { "packages": 0, "direct": 0, "transitive": 0, "findings": 0 } }

// Finding — every finding must carry evidence; no evidence, no finding
{ "id": "uuid", "rule_id": "string", "package": "name", "version": "x.y.z",
  "severity": "info | low | medium | high",
  "title": "string", "explanation": "string",
  "evidence": [ { "source": "npm-registry | lockfile | registry-contract", "field": "string", "value": "any", "observed_at": "ISO-8601" } ],
  "paths": [ ["root", "dep-a", "package"] ] }

// Graph — node id is "name@version" so multiple installed versions stay distinct
{ "nodes": [ { "id": "name@version", "name": "string", "version": "string", "direct": true, "lockfile_paths": ["node_modules/..."] } ],
  "edges": [ { "from": "name@version", "to": "name@version", "type": "prod | dev | optional | peer" } ] }

// Release verification result
{ "release_id": "0x…", "status": "match | mismatch | no_record | unavailable", "manifest_hash": "0x…" }
// "no_record" is an evidence gap, not a risk signal. "match" is not a safety verdict.
```

## Compatibility rules

- Additive response fields are non-breaking; clients must ignore unknown fields.
- Removing/renaming fields or tightening validation requires bumping the API version and updating the extension.
