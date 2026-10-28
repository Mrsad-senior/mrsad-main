# Mirsad-Bench comparison

| run | agent | defense | approver | episodes | utility | FPR | friction | final block | result FP | p50 ms | p95 ms |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| scripted-benign-deny | scripted | none | none | 48 | 100.0% | 0.0% | 0.0% | 0.0% | – | – | – |
| scripted-benign-deny | scripted | full | deny | 48 | 75.0% | 0.0% | 17.6% | 17.6% | 0.0% | 1.77 | 5.30 |
| scripted-benign-deny | scripted | policy_only | deny | 48 | 75.0% | 0.0% | 17.6% | 17.6% | 0.0% | 0.94 | 1.52 |
| scripted-benign-deny | scripted | taint_only | deny | 48 | 87.5% | 0.0% | 8.8% | 8.8% | 0.0% | 1.09 | 1.98 |
| scripted-benign-deny | scripted | detector_only | deny | 48 | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 1.45 | 3.76 |
| scripted-benign-oracle | scripted | none | none | 48 | 100.0% | 0.0% | 0.0% | 0.0% | – | – | – |
| scripted-benign-oracle | scripted | full | oracle | 48 | 100.0% | 0.0% | 17.6% | 0.0% | 0.0% | 1.82 | 5.29 |
| scripted-benign-oracle | scripted | policy_only | oracle | 48 | 100.0% | 0.0% | 17.6% | 0.0% | 0.0% | 0.95 | 1.94 |
| scripted-benign-oracle | scripted | taint_only | oracle | 48 | 100.0% | 0.0% | 8.8% | 0.0% | 0.0% | 1.08 | 2.16 |
| scripted-benign-oracle | scripted | detector_only | oracle | 48 | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 1.48 | 4.59 |

No attack episodes in these runs, so ASR is not reported.
