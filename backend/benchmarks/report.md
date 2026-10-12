# Provenyx synthetic detection benchmark

Positive means the labeled synthetic scenario is expected to produce a security investigation indicator; it does not mean confirmed malware or exploitation.

> Limitation: Synthetic indicator benchmark only; it is not an independent real-world malware corpus. Behavior classes overlap unit-test categories, although thresholds were not optimized against this suite.

## Metrics

| TP | FP | TN | FN | Precision | Recall | F1 | False-positive rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 7 | 0 | 9 | 0 | 1.000 | 1.000 | 1.000 | 0.000 |

## Cases

| Case | Category | Expected indicator | Predicted indicator | Result |
|---|---|---:|---:|---|
| `typo-deletion` | typosquatting | true | true | TP |
| `typo-transposition` | typosquatting | true | true | TP |
| `typo-exact-trusted` | typosquatting | false | false | TN |
| `typo-legitimate-suffix` | typosquatting | false | false | TN |
| `typo-different-scope` | typosquatting | false | false | TN |
| `static-install-correlation` | static-analysis | true | true | TP |
| `static-credential-network` | static-analysis | true | true | TP |
| `static-benign-install-script` | static-analysis | false | false | TN |
| `static-benign-process` | static-analysis | false | false | TN |
| `static-network-only` | static-analysis | false | false | TN |
| `publisher-changed` | publisher-intelligence | true | true | TP |
| `publisher-unchanged` | publisher-intelligence | false | false | TN |
| `publisher-metadata-missing` | publisher-intelligence | false | false | TN |
| `publisher-install-correlation` | publisher-intelligence | true | true | TP |
| `known-vulnerability` | known-vulnerability | true | true | TP |
| `no-known-vulnerability` | known-vulnerability | false | false | TN |
