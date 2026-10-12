# Provenyx Security

**Trust Every Dependency. Verify Every Release.**

Provenyx helps JavaScript and TypeScript developers investigate the npm dependencies recorded in a project's `package-lock.json`.

> **Preview (0.1.0).** A scan validates and submits your lockfile, then the API builds a persisted dependency graph and retrieves public npm metadata. The sidebar shows evidence-backed investigation signals and links to the matching dashboard scan. Signals are not security verdicts.

## Features

- **Provenyx: Scan Dependencies** — finds `package-lock.json` in your workspace, checks that it is valid, and (after you confirm) sends it to the Provenyx API.
- **Provenyx: Show Findings** — opens the Provenyx sidebar showing the project, backend state, completed scan status, and real findings.
- **Provenyx: Open Dashboard** — opens the Provenyx web dashboard.
- **Provenyx: Check Backend Connection** — checks that the configured API is reachable.

## Privacy and safety

- Provenyx **never installs, builds, or executes** packages from your project and never runs lifecycle scripts.
- Your lockfile is sent **only after you confirm** each scan, and only to the URL in `provenyx.apiBaseUrl` (by default a backend running on your own machine, `http://localhost:8000`).
- Only `package-lock.json` is sent. No other files, credentials, or tokens are uploaded.
- On startup the extension calls the API's `/health` endpoint to show the connection state; this sends no project data.
- The extension collects no telemetry.

## Settings

| Setting | Default | Description |
| --- | --- | --- |
| `provenyx.apiBaseUrl` | `http://localhost:8000` | Provenyx API base URL. Lockfiles are only sent here after confirmation. |
| `provenyx.dashboardUrl` | `http://localhost:3000` | URL opened by **Open Dashboard**. |
| `provenyx.autoScanEnabled` | `false` | Offer to scan when `package-lock.json` changes. You are still asked before anything is sent. |

## Requirements

A running Provenyx API. During development, see the repository's `docs/development.md`.

## Support

See the repository's issue tracker (to be published).
