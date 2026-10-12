# Provenyx Phase 3 fixed holdout benchmark

Positive means the fixed synthetic scenario warrants security investigation; it does not mean the package is confirmed malware, compromised, or exploitable.

Twenty fixed, offline synthetic cases not copied from the Phase 2 case list. Detector thresholds are the production defaults and were not changed after observing these results.

> Limitation: This fixed holdout is independent from the original 16-case Phase 2 benchmark and uses different examples, but it remains a small synthetic indicator corpus rather than a representative npm ecosystem sample.

Exact evaluated cases: **20**

## Metrics

| TP | FP | TN | FN | Precision | Recall | F1 | False-positive rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 2 | 8 | 0 | 0.833 | 1.000 | 0.909 | 0.200 |

## Cases

| Case | Category | Expected | Predicted | Result |
|---|---|---:|---:|---|
| `near-miss-react-substitution` | package-name | true | true | TP |
| `near-miss-axios-transposition` | package-name | true | true | TP |
| `legitimate-react-companion` | package-name | false | false | TN |
| `scoped-angular-transposition` | package-name | true | true | TP |
| `different-scope-same-leaf` | package-name | false | false | TN |
| `legitimate-prettier-plugin` | package-name | false | false | TN |
| `install-process-network-combination` | static-indicator | true | true | TP |
| `credential-file-network-combination` | static-indicator | true | true | TP |
| `dynamic-obfuscation-combination` | static-indicator | true | true | TP |
| `credential-reference-only` | static-indicator | true | true | TP |
| `dynamic-loader-only` | static-indicator | true | true | TP |
| `telemetry-network-only` | static-indicator | false | false | TN |
| `noninstall-tool-version-check` | static-indicator | false | false | TN |
| `legitimate-install-file-copy` | static-indicator | false | false | TN |
| `legitimate-native-build-script` | static-indicator | false | true | FP |
| `encoded-data-without-execution` | static-indicator | false | true | FP |
| `authorized-owner-transition` | publisher-snapshot | true | true | TP |
| `stable-release-owner` | publisher-snapshot | false | false | TN |
| `missing-publisher-snapshots` | publisher-snapshot | false | false | TN |
| `owner-transition-with-install-change` | publisher-snapshot | true | true | TP |
