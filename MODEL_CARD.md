# Model card — Paper 2 final v4 artifacts

## Intended use

The frozen models support research on leakage-controlled cross-compartment forecasting in controlled-environment agriculture and edge-execution feasibility.

They predict:

- class-A cherry-tomato production (ProdA) at **recorded harvest events**;
- drain EC **12 h ahead** through prediction of the 12-h EC change;
- drain pH **12 h ahead** through prediction of the 12-h pH change.

The HTU live implementation uses the artifacts for **advisory monitoring and engineering integration only**. It is not a lettuce-specific validated forecasting or autonomous dosing system.

## Training/evaluation domain

Dataset: Autonomous Greenhouse Challenge, Second Edition (2019).

Development compartments:

- TheAutomators
- Automatoes
- Digilog
- IUACAAS
- Reference

Untouched final test compartment: **AICU**.

No AICU observation is used for model-family selection, hyperparameter tuning, training-derived preprocessing parameters, or training-defined decision rules.

## Final models

### Harvest-event production

- Family: **Extra Trees**
- Pipeline: median `SimpleImputer` → `ExtraTreesRegressor`
- Predictors: 205
- Development events: 110
- AICU test events: 23
- AICU RMSE: 0.167498
- AICU MAE: 0.132449
- AICU R²: 0.336038
- RMSE reduction vs strongest historical baseline: 11.2%

### EC, 12 h

- Family: **Histogram Gradient Boosting**
- Pipeline: median `SimpleImputer` → `HistGradientBoostingRegressor`
- Predictors: 202
- Development samples: 19,265
- AICU test samples: 3,538
- AICU RMSE: 0.287900
- Persistence RMSE: 0.424969
- Persistence-relative RMSE skill: 32.3%
- Paired moving-block bootstrap 95% skill interval: 23.4–42.2%

### pH, 12 h

- Family: **Ridge**, α = 0.01
- Pipeline: median `SimpleImputer` → `StandardScaler` → `Ridge`
- Predictors: 202
- AICU RMSE: 0.189796
- Persistence RMSE: 0.288976
- Persistence-relative RMSE skill: 34.3%
- Paired moving-block bootstrap 95% skill interval: 24.9–44.5%

## Interpretation boundaries

- Tree feature importance and permutation importance quantify dependence within fitted models; they are not causal agronomic effects.
- Ridge coefficients are conditional on standardized, strongly correlated lag/rolling predictors and are not dosing rules.
- pH is strongly autoregressive at the 12-h horizon; high R² must be interpreted together with persistence-relative skill.
- Performance varies by operating regime. The models add the clearest value during rapid changes; persistence can be competitive or better during stable periods.
- EC performance becomes worse than persistence at the tested 24-h horizon; the 12-h models should not be extrapolated to longer horizons without redevelopment and validation.

## Deployment limitations

The HTU NFT platform differs from the AGC training domain in crop, facility, sensor definitions, and management strategy. Live use can require interface adaptations (for example, TDS-derived EC or missing-variable imputation). The live predictions are therefore advisory and must not be reported as quantitative lettuce validation.

## Artifact provenance

The model files under `models/` were serialized by the executed v4 workflow and record scikit-learn version **1.4.2**. The definitive target-device benchmark files are under `raspberry_pi/results/`.
