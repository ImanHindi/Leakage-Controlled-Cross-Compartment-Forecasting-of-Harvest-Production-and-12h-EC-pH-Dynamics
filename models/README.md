# Final frozen model artifacts

These are the model files selected by the executed leakage-controlled v4 analysis.

| File | Final family | Pipeline | Feature count |
|---|---|---|---:|
| `production_model.joblib` | Extra Trees | SimpleImputer → ExtraTreesRegressor | 205 |
| `ec_12h_model.joblib` | Histogram Gradient Boosting | SimpleImputer → HistGradientBoostingRegressor | 202 |
| `ph_12h_model.joblib` | Ridge (α = 0.01) | SimpleImputer → StandardScaler → Ridge | 202 |
| `metadata.json` | — | model families, feature order, split metadata, DOI | — |

The EC and pH pipelines predict **12-h changes**, not direct future states. The absolute forecast is reconstructed as:

```text
EC(t+12 h) = EC(t) + predicted ΔEC(t,12)
pH(t+12 h) = pH(t) + predicted ΔpH(t,12)
```

## Version compatibility

The serialized artifacts record scikit-learn **1.4.2** as the training version. Reproducing training should use that version where possible. The final target-device benchmark was run in the working Raspberry Pi environment reported in `../raspberry_pi/results/raspberry_pi_environment_v4.json`; its original environment record did not include the installed scikit-learn package version. The updated benchmark script records package versions on future runs.

If scikit-learn emits a cross-version unpickling warning, do not silently re-save or replace the artifact. Validate predictions against the frozen held-out result files before using a re-serialized copy.
