# Leakage-Controlled Cross-Compartment Forecasting of Harvest Production and 12-Hour EC/pH Dynamics with Edge Computing Benchmarking

This repository is the reproducibility and deployment package aligned with the final Paper 2 (manuscript V5). It contains the executed leakage-controlled analysis notebook, frozen scikit-learn model pipelines, held-out AICU predictions, manuscript-ready result tables and figures, Raspberry Pi 4 benchmark evidence, and the advisory HTU LoRa–edge–ThingSpeak–Power BI deployment resources.

## Study design at a glance

The predictive evaluation is intentionally separated at the greenhouse-compartment level.

- **Development compartments:** TheAutomators, Automatoes, Digilog, IUACAAS, and Reference.
- **Untouched final test compartment:** AICU.
- **Harvest production:** only recorded ProdA harvest events are modeled; no daily target interpolation is used.
- **EC/pH:** five-minute climate records are quality screened, aggregated hourly, and converted to strictly past-derived 12-h change-prediction tasks.
- **Model selection:** leave-one-compartment-out (LOCO) validation is performed only within the five development compartments.
- **Final evaluation:** the selected specification is refitted on all development compartments and evaluated once on AICU.
- **Deployment assessment:** target-device benchmarking and live HTU advisory execution occur after model selection and are not treated as lettuce-specific predictive validation.

The exact numeric source of truth used to align the repository and manuscript is:

`results/v4/tables/FINAL_MANUSCRIPT_SOURCE_OF_TRUTH.csv`

## Final selected models

| Task | Final model | Predictors | Held-out AICU result |
|---|---|---:|---|
| Harvest-event ProdA | Extra Trees | 205 | RMSE 0.1675; MAE 0.1324; R² 0.3360 |
| EC, +12 h | Histogram Gradient Boosting | 202 | RMSE 0.2879; 32.3% RMSE skill over persistence |
| pH, +12 h | Ridge (α = 0.01) | 202 | RMSE 0.1898; 34.3% RMSE skill over persistence |

The production model improves RMSE by **11.2%** relative to the strongest tested historical baseline (previous-three-harvest mean). Paired 24-h moving-block bootstrap 95% intervals for persistence-relative RMSE skill are **23.4–42.2% for EC** and **24.9–44.5% for pH**.

## Final Raspberry Pi benchmark

The definitive target-device benchmark was run on a **Raspberry Pi 4 Model B Rev. 1.5**, 64-bit aarch64 Linux, Python 3.13.5. The protocol used 50 warm-up calls followed by 1,000 timed single-sample `pipeline.predict()` calls for each frozen model.

| Artifact | Model | Median | 95th percentile | Max |
|---|---|---:|---:|---:|
| Production | Extra Trees | 391.53 ms | 601.30 ms | 693.98 ms |
| EC, +12 h | Histogram Gradient Boosting | 46.67 ms | 60.41 ms | 167.31 ms |
| pH, +12 h | Ridge | 11.32 ms | 12.47 ms | 14.77 ms |

Process RSS with all three final pipelines and dependencies loaded was **160.99 MB**. The benchmark measures estimator/pipeline inference only and excludes LoRa reception, packet decoding, feature-state maintenance, cloud upload, dashboard refresh, and actuator communication.

See `raspberry_pi/results/` for the final CSV/JSON evidence and `raspberry_pi/benchmark_v4_selected_models.py` for the benchmark script.

## Repository structure

```text
.
├── configs/
│   ├── harvest_state.example.json
│   └── live_lora_model_config.example.json
├── dashboard/
│   ├── LiveGreenHouseMonitoring.pbix
│   └── README.md
├── data/
│   ├── README.md
│   └── sample/live_packet_example.csv
├── docs/
│   ├── CEA_HIGHLIGHTS.md
│   ├── MANUSCRIPT_ALIGNMENT.md
│   └── RELEASE_NOTES_V5.md
├── models/
│   ├── production_model.joblib
│   ├── ec_12h_model.joblib
│   ├── ph_12h_model.joblib
│   ├── metadata.json
│   └── README.md
├── raspberry_pi/
│   ├── benchmark_v4_selected_models.py
│   ├── live_lora_p2p_models_to_thingspeak.py
│   ├── README_live_lora_models.md
│   └── results/
├── results/v4/
│   ├── aicu_ec_ph_predictions.csv
│   ├── aicu_production_predictions.csv
│   ├── figures/
│   ├── raspberry_pi/
│   └── tables/
├── tools/
│   └── validate_release.py
├── training/
│   ├── Paper_2_CEA_Enhanced_Reproducible_Analysis_v4.ipynb
│   └── README.md
├── DATA_AVAILABILITY.md
├── FINAL_RELEASE_CHECKLIST.md
├── MODEL_CARD.md
├── RELEASE_MANIFEST_SHA256.txt
├── requirements.txt
└── requirements-raspberry-pi.txt
```

## Reproduce the historical analysis

1. Obtain the **Autonomous Greenhouse Challenge, Second Edition (2019)** dataset from its authorized source using DOI `10.4121/uuid:88d22c60-21b3-4ea8-90db-20249a5be2a7`.
2. Place the six compartment folders under a local `agc2_data/` directory beside the notebook, or update the notebook data path.
3. Create a clean Python environment and install `requirements.txt`.
4. Open `training/Paper_2_CEA_Enhanced_Reproducible_Analysis_v4.ipynb` and run from first cell to last.
5. Compare the generated primary results against `results/v4/tables/FINAL_MANUSCRIPT_SOURCE_OF_TRUTH.csv`.

The repository intentionally does **not** redistribute the raw AGC dataset.

## Model artifacts

The frozen final pipelines are included under `models/`:

- `production_model.joblib`: `SimpleImputer` + `ExtraTreesRegressor`;
- `ec_12h_model.joblib`: `SimpleImputer` + `HistGradientBoostingRegressor`;
- `ph_12h_model.joblib`: `SimpleImputer` + `StandardScaler` + `Ridge(alpha=0.01)`.

The serialized artifacts record scikit-learn **1.4.2** as their training version. See `models/README.md` for compatibility notes.

## Live HTU advisory deployment

The live script in `raspberry_pi/` loads the **same frozen final pipelines** and supports the implemented sensing–edge–cloud path:

```text
HTU sensors → ESP32/LoRa P2P → Raspberry Pi → model inference → ThingSpeak → Power BI
```

This component is an **engineering integration and advisory-monitoring demonstration**. The AGC-trained models have not been prospectively validated for lettuce, and their live outputs must not be interpreted as lettuce-specific predictive accuracy or autonomous nutrient-control performance. Missing or non-equivalent HTU variables are explicitly logged as interface adaptations; no such mapping is used to create the manuscript's quantitative AICU results.

Copy the example configuration and keep secrets local:

```bash
cp configs/live_lora_model_config.example.json configs/live_lora_model_config.local.json
python raspberry_pi/live_lora_p2p_models_to_thingspeak.py \
  --config configs/live_lora_model_config.local.json --dry-run
```

See `raspberry_pi/README_live_lora_models.md` for details.

## Dashboard

`dashboard/LiveGreenHouseMonitoring.pbix` is the Power BI monitoring resource used with ThingSpeak. It visualizes live measurements and advisory model outputs. Inspect and replace local channel IDs/read keys before public use. **Never commit ThingSpeak write API keys.**

## Data and software availability

- Reproducibility archive DOI: `10.5281/zenodo.21645524`
- AGC dataset DOI: `10.4121/uuid:88d22c60-21b3-4ea8-90db-20249a5be2a7`

See `DATA_AVAILABILITY.md` for the repository's data-handling policy.

## Release validation

Before committing or creating a release, run:

```bash
python tools/validate_release.py
```

The validator checks the final model families, feature counts, primary manuscript values, Raspberry Pi benchmark identity/results, expected files, absence of raw data/environment directories, and obvious secret placeholders.

## Citation

The confirmed Paper 2 author set is **Iman Hindi and Khalid Al-Zaareer**. Citation metadata are provided in [`CITATION.cff`](CITATION.cff). Please cite the associated manuscript together with the versioned Zenodo software archive (`10.5281/zenodo.21645524`).

## License

No software license is imposed automatically by this package. See `LICENSE_NOTE.md` and confirm institutional/co-author requirements before adding a public repository license.
