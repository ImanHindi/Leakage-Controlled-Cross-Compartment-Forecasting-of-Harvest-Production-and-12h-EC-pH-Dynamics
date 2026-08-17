# Final v4 analysis outputs

This directory contains outputs from the executed Paper 2 v4 analysis plus the definitive target-device benchmark copied into `raspberry_pi/` for manuscript traceability.

## Authoritative numeric files

Use these first when checking the manuscript:

- `tables/FINAL_MANUSCRIPT_SOURCE_OF_TRUTH.csv` — consolidated final manuscript values and target-device values.
- `tables/CEA_MANUSCRIPT_SOURCE_OF_TRUTH.csv` — notebook-generated v4 analysis values.
- `aicu_production_predictions.csv` — untouched AICU harvest-event predictions.
- `aicu_ec_ph_predictions.csv` — untouched AICU 12-h EC/pH predictions.
- `raspberry_pi/raspberry_pi_benchmark_v4.csv` — definitive Raspberry Pi timing result.

## Important benchmark distinction

`tables/development_host_benchmark.csv` is the benchmark cell executed on the Windows development computer. It is retained for provenance only and **must not** be reported as Raspberry Pi performance.

The manuscript target-device values come from `raspberry_pi/` (and the identical files under the repository-level `raspberry_pi/results/`).

## Interpretation files

For the final EC HGB model, `tables/ec_model_interpretation.csv` contains **permutation importance**. The notebook-generated filename `figures/fig_ec_coefficients.png` is a historical filename only; when the EC family is HGB, the plot content is permutation importance rather than Ridge coefficients. `figures/fig_ec_permutation_importance.png` is the preferred clearly named figure for final use.

For the final pH Ridge model, `tables/ph_model_interpretation.csv` contains standardized Ridge coefficients.
