# Synthetic detection fixtures

These lockfiles are synthetic and exist only to exercise Provenyx detection rules. They are not records of real malicious packages or incidents.

- `baseline-package-lock.json` contains one direct package.
- `suspicious-update-package-lock.json` adds a synthetic transitive package and a new dependency edge.

The update includes a fake lifecycle-script string to verify that Provenyx treats lockfiles as data and never executes package scripts.