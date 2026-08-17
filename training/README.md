# Training and reproducibility — executed v4 workflow

Primary notebook:

`Paper_2_CEA_Enhanced_Reproducible_Analysis_v4.ipynb`

The notebook was executed on the authorized six-compartment Autonomous Greenhouse Challenge dataset. Its generated v4 tables/figures/models are the analysis source for the final Paper 2 manuscript.

## Leakage-control design

1. AICU is reserved as an untouched final test compartment.
2. The other five compartments are used for model development.
3. Candidate model families and hyperparameters are selected with leave-one-compartment-out validation within the development set only.
4. Training-derived preprocessing is fitted within training folds/pools.
5. Temporal predictors use observations available at or before forecast time.
6. Production targets are recorded harvest events only; no artificial daily ProdA targets are created.
7. The selected specification is fixed before the one-time AICU evaluation.

## Production task

- Raw production is restricted to the climate-coverage period.
- The first valid harvest initializes production history; it is not a supervised target.
- Predictors summarize the preceding inter-harvest interval plus fixed 7-day and 14-day historical windows.
- Candidate families: Extra Trees, Random Forest, Histogram Gradient Boosting.
- Final family: **Extra Trees**.
- Final predictor count: 205.
- Development/test event counts: 110 / 23.

## EC/pH task

- EC QC range: 0.5–12 mS cm⁻¹.
- pH QC range: 3.0–8.5.
- Five-minute data are aggregated by **hourly median**.
- Feature histories use **past-only forward fill limited to 3 h**; future-informed interpolation is not used.
- Lags: 1, 3, 6, 12, 24, 48 h.
- Rolling windows: 3, 6, 12, 24, 48 h, with mean, sample standard deviation, and linear trend.
- Calendar terms: hour and day-of-year sine/cosine.
- Final predictor count: 202.
- Models predict 12-h changes and future states are reconstructed from the observed current EC/pH.
- EC final family: **Histogram Gradient Boosting**.
- pH final family: **Ridge (α = 0.01)**.
- Persistence is a mandatory operational baseline.

## Robustness/sensitivity modules

The executed v4 notebook includes:

- model-family LOCO comparison;
- production stage-proxy ablation;
- 3-, 6-, 12-, and 24-h forecast-horizon sensitivity;
- 12-h feature-group ablation;
- training-defined operating-regime and rapid-change error analysis;
- cross-fold interpretation stability;
- ordinary bootstrap for the harvest-event test set;
- moving-block bootstrap for EC/pH metrics;
- paired 24-h moving-block bootstrap of persistence-relative RMSE skill.

## Output locations in this repository

- Frozen models: `../models/`
- Held-out predictions: `../results/v4/`
- Figures: `../results/v4/figures/`
- Tables: `../results/v4/tables/`
- Primary numeric audit: `../results/v4/tables/FINAL_MANUSCRIPT_SOURCE_OF_TRUTH.csv`

## Environment note

The executed notebook reports Python **3.12.13** on Windows 11. The serialized final model artifacts record scikit-learn **1.4.2**. Use `requirements.txt` as the reproducibility environment baseline.

The notebook also contains a host benchmarking cell. Its Windows output is retained only as `development_host_benchmark.csv`; it must not be confused with the definitive Raspberry Pi target-device results under `../raspberry_pi/results/`.
