# Model artifacts

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

Do not commit sensitive or very large model files unless repository and license
policies allow it. Git LFS may be used when necessary.
