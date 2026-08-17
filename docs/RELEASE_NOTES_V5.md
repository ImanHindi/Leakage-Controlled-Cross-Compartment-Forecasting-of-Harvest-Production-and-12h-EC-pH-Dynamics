# Release notes — manuscript V5 alignment

This repository update replaces older Paper 2 artifacts/documentation with the final leakage-controlled v4 analysis and V5 manuscript-aligned terminology.

## Major corrections

- Replaced the old v3 training notebook with the executed v4 CEA-enhanced notebook.
- Removed environment folders, caches, stale raw-data copies, and old generated-output directories.
- Added the three final frozen model pipelines.
- Corrected the final EC family from the obsolete Ridge description to **Histogram Gradient Boosting**.
- Retained **Ridge (α=0.01)** as the final pH model and **Extra Trees** as the final production model.
- Added final LOCO model-family results, stage ablation, multi-horizon analysis, feature-group ablation, regime analysis, interpretation stability, and paired block-bootstrap skill results.
- Added definitive Raspberry Pi 4 benchmark results: 391.53 ms production, 46.67 ms EC, and 11.32 ms pH median single-sample inference.
- Renamed the notebook's Windows host benchmark output to `development_host_benchmark.csv` so it cannot be mistaken for Raspberry Pi evidence.
- Updated live-deployment documentation to distinguish advisory HTU execution from crop-specific predictive validation.
- Updated the live LoRa script/config to load the final complete pipelines and final feature metadata directly.
- Added release validation and SHA-256 artifact manifest.

## Removed/retired assumptions

The following older descriptions are no longer valid for the final paper:

- Ridge as the final EC model;
- weekly production as the scientific production target;
- random/chronological row-level split as the principal validation design;
- interpolated production targets;
- future-informed hourly interpolation;
- old 11-ms EC latency from pre-final model artifacts;
- live dashboard operation as evidence of lettuce-specific predictive accuracy.
