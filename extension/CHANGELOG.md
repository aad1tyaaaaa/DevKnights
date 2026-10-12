# Changelog

## 0.1.0 (preview)

- **Provenyx: Scan Dependencies** finds `package-lock.json` (v1–v3), validates it locally, and sends it to the Provenyx API only after you confirm.
- The sidebar shows the project, backend connection, last scan status, and findings with severity, confidence, explanation, and dependency path.
- After a scan, the extension follows its status and loads findings once the API provides them. Clicking a finding opens it in the web dashboard.
- **Provenyx: Open Dashboard** and **Provenyx: Check Backend Connection**.
- Settings: `provenyx.apiBaseUrl`, `provenyx.dashboardUrl`, `provenyx.autoScanEnabled` (off by default; still asks before sending).
- The dashboard verifies releases against blockchain-anchored manifests: match, mismatch, no record, or unavailable.
- No telemetry. Never installs or executes packages.
