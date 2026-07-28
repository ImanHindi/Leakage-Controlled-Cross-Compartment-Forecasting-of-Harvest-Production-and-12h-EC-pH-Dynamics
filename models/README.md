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

=======
Place the exact fitted artifacts exported by the Paper 2 training workflow in
this directory.

Expected files in the example configuration:

- `ec_ridge_model.joblib`
- `ec_scaler.joblib`
- `ec_feature_names.json`
- `ph_ridge_model.joblib`
- `ph_scaler.joblib`
- `ph_feature_names.json`
- `production_extra_trees.joblib`
- `production_imputer.joblib`
- `production_feature_names.json`

The EC and pH models are expected to predict 12-hour changes. The live script
reconstructs the future values as:

- `EC(t+12 h) = EC(t) + predicted EC change`
- `pH(t+12 h) = pH(t) + predicted pH change`


