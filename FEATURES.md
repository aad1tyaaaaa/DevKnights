# Provenyx Feature List

This document lists the features currently implemented in Provenyx.

## VS Code Extension

- Scan npm projects directly from VS Code with **Provenyx: Scan Dependencies**.
- Find and validate `package-lock.json` files (lockfile versions 1, 2, and 3).
- Enforce a 10 MiB lockfile size limit before upload.
- Ask for explicit consent and show the destination API before sending a lockfile.
- Display backend connection state, scan status, and findings in a TreeView sidebar.
- Sort findings by severity and investigation priority.
- Show explanations, confidence, priority, and dependency paths in finding tooltips.
- Open the dashboard at the selected scan or finding.
- Automatically detect lockfile creation and changes with a debounced watcher.
- Configure the API URL, dashboard URL, and automatic scanning.
- Handle missing lockfiles, backend outages, and request timeouts without crashing.
- Operate without telemetry.

## Dependency Scanning and Analysis

- Parse npm `package-lock.json` versions 1, 2, and 3.
- Support scoped packages and nested `node_modules` installation paths.
- Extract exact package versions, dependency declarations, resolved URLs, and integrity values.
- Preserve multiple installed versions of the same package.
- Build direct and transitive dependency graphs using npm nearest-ancestor resolution.
- Fetch real npm registry metadata with bounded concurrency, caching, timeouts, and retries.
- Mark unavailable metadata as unknown instead of guessing.
- Persist scans, graphs, findings, and metadata in SQLite through SQLAlchemy.
- Compare a scan with the latest completed scan for the same project.
- Detect added and removed packages, version changes, and new dependency edges.
- Process scans in the background and expose live scan status through the API.
- Never install dependencies or execute package code and lifecycle scripts.

## Security Detection Rules

- **Known vulnerability:** checks exact installed package versions against OSV advisories.
- **New dependency:** identifies packages introduced since the previous scan.
- **Dependency expansion:** identifies existing packages that gained dependency edges.
- **Unusual release timing:** flags upgrades published unusually soon after a preceding release.
- **Publisher change:** identifies version-specific npm publisher changes when evidence is available.
- Attach evidence, evidence source, severity, confidence, and deterministic priority to every finding.
- Calculate dependency paths to show how a flagged package reaches the application.
- Keep severity, confidence, and priority as separate values.
- Optionally rerank generated finding summaries with Gemini while retaining deterministic scores.
- Fall back to deterministic ranking when AI is disabled, unavailable, or returns an invalid result.

## Web Dashboard

- Show backend health, setup guidance, latest-scan metrics, and scan history.
- Upload and validate a lockfile in the browser.
- Require explicit upload consent that names the destination API.
- Show live progress while a scan is running.
- Display scan metrics, findings, and analysis warnings.
- Filter findings by severity.
- Explore an interactive Cytoscape dependency graph with zoom, pan, fit, and node selection.
- Highlight dependency paths and packages that depend on a selected node.
- Inspect package evidence, unknowns, install locations, dependency paths, and npm metadata.
- Deep-link directly to a scan or selected finding from VS Code.
- Provide honest loading, empty, unavailable, and error states.
- Support desktop and mobile layouts without horizontal page scrolling.
- Switch between supported visual themes.

## Blockchain Release Verification

- Build a canonical release manifest from package name, version, integrity, and schema version.
- Serialize manifests deterministically and hash them with Keccak-256.
- Derive deterministic release IDs from `name@version`.
- Store approved manifest hashes and anchor timestamps in `ReleaseRegistry.sol`.
- Restrict anchoring to the contract owner and prevent records from being overwritten.
- Deploy the registry and anchor manifests on a local Hardhat chain.
- Verify releases through read-only JSON-RPC calls; the backend holds no private keys.
- Return one of four explicit results: `match`, `mismatch`, `no_record`, or `unavailable`.
- Show current and anchored hashes, anchor time, registry address, chain, and manifest fields.
- Clearly state that a hash match is not proof of safety and that no record is not a risk signal.
- Test Python and TypeScript manifest implementations against shared values.

## API and Reliability

- Provide health, scan submission, scan status, findings, graph, and release-verification endpoints.
- Validate request schemas and package identifiers.
- Cap request bodies while they stream in.
- Restrict CORS and avoid echoing uploaded input in errors.
- Handle npm registry, OSV, AI, and blockchain service failures without fabricating conclusions.
- Include automated backend, extension smoke, frontend build, contract, and end-to-end tests.
- Include benign and clearly labeled synthetic fixtures for reproducible demonstrations.

## Packaging and Documentation

- Build and package the extension as a VSIX.
- Include Marketplace metadata, icon, screenshots, changelog, license, and publishing checklist.
- Include local development, architecture, API contract, demo, and deployment documentation.

## Current Scope and Limitations

- Dependency analysis currently targets npm projects using `package-lock.json`.
- Change-based detection requires an earlier completed scan with the same project name.
- The blockchain workflow currently uses a local Hardhat development chain, not a public network.
- The FastAPI backend and dashboard must be hosted separately from the VS Code Marketplace extension.
- Marketplace publication requires the publisher's credentials and remains a manual step.