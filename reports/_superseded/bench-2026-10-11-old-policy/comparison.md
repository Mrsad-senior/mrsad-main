# Mirsad-Bench comparison

| run | agent | defense | approver | episodes | utility | FPR | friction | final block | result FP | p50 ms | p95 ms |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| scripted-benign-deny | scripted | none | none | 48 | 100.0% | 0.0% | 0.0% | 0.0% | – | – | – |
| scripted-benign-deny | scripted | full | deny | 48 | 75.0% | 0.0% | 17.6% | 17.6% | 0.0% | 1.90 | 3.18 |
| scripted-benign-deny | scripted | policy_only | deny | 48 | 75.0% | 0.0% | 17.6% | 17.6% | 0.0% | 1.08 | 1.85 |
| scripted-benign-deny | scripted | taint_only | deny | 48 | 87.5% | 0.0% | 8.8% | 8.8% | 0.0% | 1.22 | 2.28 |
| scripted-benign-deny | scripted | detector_only | deny | 48 | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 1.43 | 2.78 |
| scripted-benign-oracle | scripted | none | none | 48 | 100.0% | 0.0% | 0.0% | 0.0% | – | – | – |
| scripted-benign-oracle | scripted | full | oracle | 48 | 100.0% | 0.0% | 17.6% | 0.0% | 0.0% | 1.94 | 3.95 |
| scripted-benign-oracle | scripted | policy_only | oracle | 48 | 100.0% | 0.0% | 17.6% | 0.0% | 0.0% | 1.05 | 2.07 |
| scripted-benign-oracle | scripted | taint_only | oracle | 48 | 100.0% | 0.0% | 8.8% | 0.0% | 0.0% | 1.23 | 2.53 |
| scripted-benign-oracle | scripted | detector_only | oracle | 48 | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 1.42 | 2.87 |

No attack episodes in these runs, so ASR is not reported.
