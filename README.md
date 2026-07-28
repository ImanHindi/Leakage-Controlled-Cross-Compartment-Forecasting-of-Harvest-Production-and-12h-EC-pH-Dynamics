# Towards Smart and Sustainable Agriculture in Jordan — Part II

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21645524.svg)](https://doi.org/10.5281/zenodo.21645524)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi-C51A4A.svg)](https://www.raspberrypi.com/)
[![Communication](https://img.shields.io/badge/Communication-LoRa%20P2P-2E8B57.svg)](#live-raspberry-pi-and-lora-p2p-deployment)

## Overview

This repository provides the reproducible training, evaluation, model artifacts,
edge-deployment software, cloud-streaming workflow, and visualization resources
developed for **Paper 2** of the *Towards Smart and Sustainable Agriculture in
Jordan* project.

The workflow supports:

- greenhouse data preparation and quality control;
- 12-hour drain electrical conductivity forecasting;
- 12-hour drain pH forecasting;
- weekly production-indicator prediction;
- chronological model evaluation and explainability;
- historical CSV replay to ThingSpeak;
- live LoRa point-to-point reception and inference on Raspberry Pi;
- local CSV logging and cloud streaming;
- Power BI monitoring and forecast visualization.

> **Research-use notice:** The forecasts are intended for research and
> decision support. They must not be interpreted as autonomous nutrient-dosing
> commands without facility-specific calibration, safety limits, and independent
> validation.

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
│   ├── sample/
│   └── README.md
├── models/
│   ├── ec_12h_model.joblib
│   ├── ph_12h_model.joblib
│   ├── production_model.joblib
│   ├── metadata.json
│   └── README.md
├── outputs/
│   ├── coefficients/
│   ├── figures/
│   ├── predictions/
│   └── tables/
├── src/
│   ├── raspberry_pi/
│   │   ├── live_lora_p2p_models_to_thingspeak.py
│   │   └── README.md
│   └── replay/
│       └── stream_one_team_two_thingspeak_channels.py
├── training/
│   ├── Paper_2_Enhanced_AGC2_Reproducible_Analysis_CORRECTED_v3.ipynb
│   └── README.md
├── CITATION.cff
├── DATA_AVAILABILITY.md
├── LICENSE
├── MODEL_CARD.md
├── requirements.txt
└── requirements-raspberry-pi.txt
```

## System workflow

```text
Historical greenhouse data
          │
          ▼
Preprocessing and hourly aggregation
          │
          ├──► EC 12-hour change model
          ├──► pH 12-hour change model
          └──► Weekly production model
          │
          ▼
Evaluation, explainability, and saved model pipelines
          │
          ├──► Historical CSV replay
          │         └──► ThingSpeak ──► Power BI
          │
          └──► Live LoRa P2P reception on Raspberry Pi
                    ├──► Local CSV logging
                    ├──► Live model inference
                    └──► ThingSpeak ──► Power BI
```

## 1. Training and paper reproduction

The main reproducible notebook is located at:

```text
training/Paper_2_Enhanced_AGC2_Reproducible_Analysis_CORRECTED_v3.ipynb
```

### Create the Python environment

```bash
python -m venv .venv
```

Activate the environment:

```bash
# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

### Obtain the dataset

The full **Autonomous Greenhouse Challenge, Second Edition** dataset is not
redistributed through this repository.

Obtain it from its authorized source using:

```text
DOI: 10.4121/uuid:88d22c60-21b3-4ea8-90db-20249a5be2a7
```

Place the authorized dataset under:

```text
data/raw/
```

Then run the notebook cells in order.

See [DATA_AVAILABILITY.md](DATA_AVAILABILITY.md) for the expected data
organization and repository data-availability statement.

## 2. Included models

The repository includes complete scikit-learn pipelines serialized using
**scikit-learn 1.4.2**:

- `models/ec_12h_model.joblib`
- `models/ph_12h_model.joblib`
- `models/production_model.joblib`
- `models/metadata.json`

The EC and pH models predict **12-hour changes**, rather than direct future
measurements. Future values are reconstructed as:

```text
EC(t + 12 h) = EC(t) + predicted EC change
pH(t + 12 h) = pH(t) + predicted pH change
```

The production model generates a weekly production indicator based on the
feature space and harvest records used during model training.

See [MODEL_CARD.md](MODEL_CARD.md) for model scope, intended use, assumptions,
and limitations.

### Validate the model artifacts

Create a private local configuration:

```bash
cp configs/live_lora_model_config.example.json \
   configs/live_lora_model_config.local.json
```

Validate the models without opening the Raspberry Pi serial port:

```bash
python src/raspberry_pi/live_lora_p2p_models_to_thingspeak.py \
  --config configs/live_lora_model_config.local.json \
  --validate-models
```

Real API keys and private configuration values must only be stored in ignored
`*.local.json` files.

## 3. Historical ThingSpeak replay

The historical replay script is located at:

```text
src/replay/stream_one_team_two_thingspeak_channels.py
```

It replays authorized greenhouse measurements and precomputed forecasts to two
ThingSpeak channels.

This mode supports:

- dashboard development;
- cloud-pipeline verification;
- reproduction of the paper's visualization workflow;
- testing without physical LoRa hardware.

Example:

```bash
python src/replay/stream_one_team_two_thingspeak_channels.py \
  --data-dir data/raw \
  --predictions-csv outputs/predictions/aicu_ec_ph_predictions.csv \
  --config configs/thingspeak_two_channels.local.json \
  --start-at-first-prediction \
  --interval 20
```

## 4. Live Raspberry Pi and LoRa P2P deployment

The live deployment script is:

```text
src/raspberry_pi/live_lora_p2p_models_to_thingspeak.py
```

It:

1. configures a RAK3172 receiver in LoRa P2P mode;
2. receives measurements through `/dev/serial0`;
3. decodes and validates incoming packets;
4. logs accepted measurements locally;
5. aggregates measurements into hourly medians;
6. constructs the lagged and rolling features used during training;
7. predicts EC and pH 12 hours ahead;
8. computes an experimental weekly production indicator;
9. uploads measurements and model outputs to ThingSpeak.

### Radio configuration

```text
AT+NWM=0
AT+P2P=868000000:7:0:0:10:14
AT+PRECV=65535
```

### Raspberry Pi installation

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip

python3 -m venv ~/paper2-live-env
source ~/paper2-live-env/bin/activate

pip install -r requirements-raspberry-pi.txt
sudo usermod -aG dialout "$USER"
```

Log out and sign in again after adding the user to the `dialout` group.

Create the private local configuration:

```bash
cp configs/live_lora_model_config.example.json \
   configs/live_lora_model_config.local.json
```

Edit the local file to provide:

- ThingSpeak write API keys;
- model and metadata paths;
- serial-port settings;
- legacy packet-conversion settings, when required.

Test without cloud upload:

```bash
python src/raspberry_pi/live_lora_p2p_models_to_thingspeak.py \
  --config configs/live_lora_model_config.local.json \
  --dry-run
```

Run with ThingSpeak upload enabled:

```bash
python src/raspberry_pi/live_lora_p2p_models_to_thingspeak.py \
  --config configs/live_lora_model_config.local.json
```

Additional deployment instructions are provided in:

```text
src/raspberry_pi/README.md
```

## Recommended LoRa payload

The preferred live payload contains the seven model variables in this order:

```text
Tair,Rhair,CO2air,Tot_PAR,EC_drain_PC,pH_drain_PC,Cum_irr
```

Example:

```text
25.4,68.2,430,115.6,2.18,5.82,14.3
```

A JSON payload using the same field names is also accepted.

The earlier eight-value payload is supported for compatibility, but it requires
approximations for variables that are not directly transmitted. These
approximations are recorded in the log and must be treated as experimental
until independently validated.

## 5. ThingSpeak channel mapping

### Channel A — greenhouse measurements

| Field | Variable |
|---:|---|
| 1 | `Tair` |
| 2 | `Rhair` |
| 3 | `CO2air` |
| 4 | `Tot_PAR` |
| 5 | `EC_drain_PC` |
| 6 | `pH_drain_PC` |
| 7 | `Cum_irr` |

### Channel B — measurements, predictions, and communication quality

| Field | Variable |
|---:|---|
| 1 | Measured EC |
| 2 | Predicted EC at +12 h |
| 3 | Measured pH |
| 4 | Predicted pH at +12 h |
| 5 | Weekly production indicator |
| 6 | Forecast age in minutes |
| 7 | RSSI |
| 8 | SNR |

ThingSpeak write API keys must never be committed to the public repository.

## 6. Power BI dashboard

The implemented Power BI dashboard is stored under:

```text
dashboard/
```

Open the `.pbix` file using Microsoft Power BI Desktop.

Before refreshing or publishing the dashboard:

1. open **Transform data**;
2. inspect all Power Query data sources;
3. replace project-specific ThingSpeak channel IDs or read keys;
4. remove private credentials and local computer paths;
5. confirm that the field mappings match this README;
6. refresh all report visuals.

The dashboard provides near-real-time monitoring and forecast visualization. It
is not a deterministic industrial SCADA system.

## 7. Reproducibility outputs

Selected research outputs are stored under:

```text
outputs/
```

These may include:

- held-out EC and pH predictions;
- weekly production predictions;
- evaluation tables;
- standardized Ridge coefficients;
- Extra-Trees feature importance;
- quality-control summaries;
- leave-one-team-out results;
- manuscript figures.

The full source dataset remains governed by the original data provider's terms.

## Limitations

- The models were trained in the greenhouse domain described in Paper 2.
- Deployment in another crop, facility, season, or sensing configuration
  requires independent validation.
- Legacy conversions from TDS to EC, lux to PAR, or pump status to cumulative
  irrigation are approximations.
- The production model may require variables that are unavailable in the
  compact live payload. Live production results must therefore be treated as
  experimental indicators.
- Model coefficients describe predictive associations rather than independent
  causal agronomic effects.
- Forecasts must not be used as direct chemical-dosing commands without
  calibrated safety limits and facility-specific testing.

## Citation

The archived release is available through Zenodo:

**DOI:** [10.5281/zenodo.21645524](https://doi.org/10.5281/zenodo.21645524)

Citation metadata are also provided in
[`CITATION.cff`](CITATION.cff). GitHub can use this file to generate formatted
citations.

## License

The repository software is released under the
[MIT License](LICENSE).

The original greenhouse dataset is not covered by the software license and
remains subject to the terms established by its provider.

## Acknowledgment

The authors acknowledge Al Hussein Technical University and the contributors
to the Autonomous Greenhouse Challenge dataset and experimental infrastructure.
