# Model artifacts

This directory contains the fitted scikit-learn Pipelines exported by the Paper
2 notebook:

- `ec_12h_model.joblib` — Ridge pipeline predicting 12-hour EC change;
- `ph_12h_model.joblib` — Ridge pipeline predicting 12-hour pH change;
- `production_model.joblib` — Extra-Trees production pipeline;
- `metadata.json` — dataset, split, model, feature, and limitation metadata.

The pipelines include their fitted preprocessing steps, so separate scaler and
imputer files are not required. They were serialized with scikit-learn 1.4.2;
use the pinned environment in `requirements.txt` to avoid incompatible model
loading.

The live application reconstructs future nutrient values as:

- `EC(t+12 h) = EC(t) + predicted EC change`;
- `pH(t+12 h) = pH(t) + predicted pH change`.

Production inference from the compact live payload contains many unavailable
training variables. The bundled pipeline imputes those values, but such output
is an extrapolative decision-support indicator and is not a validated yield
estimate for a different crop or facility.
