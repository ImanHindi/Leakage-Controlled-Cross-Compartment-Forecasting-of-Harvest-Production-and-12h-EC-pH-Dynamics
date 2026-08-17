# Repository update report — Paper 2 final V5 alignment

## Inputs reconciled

The repository was rebuilt using:

- the previously prepared Paper 2 repository archive;
- the executed enhanced v4 analysis package and its generated outputs;
- the final Paper 2 V5 manuscript as the terminology/claim boundary;
- the definitive Raspberry Pi benchmark artifacts already present in the repository history.

## What was intentionally retained

- Executed v4 notebook.
- Frozen final Extra Trees, HGB, and Ridge pipelines.
- Full final v4 result tables/figures and held-out predictions.
- Definitive Raspberry Pi 4 benchmark CSV/JSON/environment evidence.
- LoRa/ThingSpeak/Power BI deployment resources.
- Dashboard binary already included in the repository.

## What was intentionally removed

- Local Python/virtual environments.
- Cache folders and IDE artifacts.
- Raw AGC dataset copies.
- Old v3 notebook.
- Old generated-output folders duplicated under `data/`.
- Local runtime harvest state/config files.

## Stale enhanced-package files not promoted into the final repository

The enhanced submission archive also contained a `verified_results/` folder with **pre-final** values (including an older Ridge EC selection and older Raspberry Pi timing values). Those files were not copied into the final repository because they conflict with the executed v4 source of truth and final manuscript.

The notebook's Windows benchmark output was retained only after renaming it to `development_host_benchmark.csv`; the manuscript-reported Pi values are kept separately under `raspberry_pi/results/`.

## Final model alignment

- Production: Extra Trees, 205 predictors.
- EC: Histogram Gradient Boosting, 202 predictors.
- pH: Ridge α=0.01, 202 predictors.

The repository validator enforces these families and key manuscript values.

## Confirmed authorship

The final Paper 2 author set has been confirmed as **Iman Hindi and Khalid Al-Zaareer**. Repository citation metadata have been aligned to this author set in `CITATION.cff`. No additional contributor is listed as an author or contributor in the final repository metadata.
