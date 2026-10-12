# Provenyx Security

**Trust Every Dependency. Verify Every Release.**

Provenyx helps JavaScript and TypeScript developers investigate the npm dependencies recorded in a project's `package-lock.json`, without installing or running any of them.

> **Preview.** The extension needs a running Provenyx API (see [Requirements](#requirements)). After you confirm a scan, the API builds a dependency graph from your lockfile, reads public npm metadata, and runs explainable detection rules. Findings are investigation signals, not security verdicts. Provenyx never shows invented findings.

## Features

- **Provenyx: Scan Dependencies.** Finds `package-lock.json` in your workspace (lockfile versions 1–3), checks it locally, and sends it to the Provenyx API after you confirm.
- **Findings sidebar.** Lists findings by severity, each with confidence, a plain-language explanation, and the dependency path that pulls the package into your project. Click a finding to investigate it in the web dashboard.
- **Scan status.** Shows the backend connection and the progress of your last scan.
- **Provenyx: Open Dashboard.** Opens the Provenyx web dashboard with the dependency graph, evidence, and release-record verification.
- **Provenyx: Check Backend Connection.** Checks that the configured API is reachable.

Findings are leads to investigate, not proof of compromise. When a release matches a blockchain-anchored record, its metadata is unchanged, but that does not prove the package is safe. A release with no record is not suspicious in itself.

## Screenshots

Findings with their evidence, and the dependency path that pulls a package into your project (the screenshot uses the repository's labelled synthetic test fixtures):

![Findings and dependency graph](https://raw.githubusercontent.com/aad1tyaaaaa/DevKnights/main/docs/images/findings-graph.png)

Release-record verification against a blockchain-anchored manifest (local development chain):

![Release verification](https://raw.githubusercontent.com/aad1tyaaaaa/DevKnights/main/docs/images/release-verification.png)

Scan history in the web dashboard:

![Dashboard](https://raw.githubusercontent.com/aad1tyaaaaa/DevKnights/main/docs/images/dashboard.png)

## Privacy and safety

- Provenyx **never installs, builds, or executes** packages from your project and never runs lifecycle scripts.
- Your lockfile is sent **only after you confirm** each scan, and only to the URL in `provenyx.apiBaseUrl`. By default that is a backend on your own machine, `http://localhost:8000`.
- Only `package-lock.json` is sent. No other files, credentials, or tokens are uploaded.
- On startup and before each scan, the extension calls the API's `/health` endpoint to show the connection state. This sends no project data.
- The extension collects no telemetry.

## Settings

| Setting | Default | Description |
| --- | --- | --- |
| `provenyx.apiBaseUrl` | `http://localhost:8000` | Provenyx API base URL. Lockfiles are only sent here after confirmation. |
| `provenyx.dashboardUrl` | `http://localhost:3000` | URL opened by **Open Dashboard** and by clicking findings. |
| `provenyx.autoScanEnabled` | `true` | Start the consent-gated scan flow when `package-lock.json` is created or changes. |

## Requirements

A running Provenyx API. The Visual Studio Marketplace hosts only the extension, not the API. To run the API and dashboard locally, follow [the development guide](https://github.com/aad1tyaaaaa/DevKnights/blob/main/docs/development.md).

## Support

Report issues at <https://github.com/aad1tyaaaaa/DevKnights/issues>.
