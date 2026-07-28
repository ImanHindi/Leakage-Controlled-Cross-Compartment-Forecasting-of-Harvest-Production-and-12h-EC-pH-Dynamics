# Towards Smart and Sustainable Agriculture in Jordan — Part II

Reproducible training, evaluation, edge inference, cloud streaming, and Power BI
visualization for greenhouse EC, pH, and production forecasting.

## Included work

- final Paper 2 training and evaluation notebook;
- fitted EC and pH 12-hour delta-prediction pipelines;
- fitted Extra-Trees production pipeline;
- held-out predictions, coefficients, evaluation tables, and manuscript figures;
- historical CSV replay to two ThingSpeak channels;
- live RAK3172 LoRa P2P reception and inference on Raspberry Pi;
- local CSV logging and two-channel ThingSpeak upload;
- Power BI dashboard and PDF dashboard export;
- model card, data-availability statement, pinned environments, and citation metadata.

## Repository structure

```text
.
├── configs/                 # public configuration templates only
├── dashboard/               # PBIX dashboard and documentation
├── data/
│   ├── sample/              # synthetic schema example
│   └── README.md
├── models/                  # fitted pipelines and metadata
├── outputs/                 # figures, tables, and held-out predictions
├── src/
│   ├── raspberry_pi/        # live LoRa P2P inference and ThingSpeak upload
│   └── replay/              # historical CSV replay to ThingSpeak
├── training/                # reproducible analysis notebook
├── DATA_AVAILABILITY.md
├── MODEL_CARD.md
├── CITATION.cff
├── LICENSE
├── requirements.txt
└── requirements-raspberry-pi.txt
```

## 1. Training and paper reproduction

The notebook is located at:

```text
training/Paper_2_Enhanced_AGC2_Reproducible_Analysis_CORRECTED_v3.ipynb
```

Create a local environment:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Obtain the Autonomous Greenhouse Challenge, Second Edition dataset from its
authorized source using DOI
`10.4121/uuid:88d22c60-21b3-4ea8-90db-20249a5be2a7`, place it under
`data/raw/`, and run all notebook cells in order. Raw data are intentionally not
redistributed.

## 2. Included models

The checked-in model files are complete scikit-learn Pipelines serialized with
scikit-learn 1.4.2:

- `models/ec_12h_model.joblib`;
- `models/ph_12h_model.joblib`;
- `models/production_model.joblib`;
- `models/metadata.json`.

The EC and pH models predict changes over 12 hours. Future values are obtained
by adding the predicted change to the current measurement.

Validate the artifacts without opening a serial port:

```bash
cp configs/live_lora_model_config.example.json configs/live_lora_model_config.local.json
python src/raspberry_pi/live_lora_p2p_models_to_thingspeak.py \
  --config configs/live_lora_model_config.local.json \
  --validate-models
```

## 3. Historical ThingSpeak replay

`src/replay/stream_one_team_two_thingspeak_channels.py` replays authorized
historical team data and precomputed forecasts to two ThingSpeak channels. It is
useful for reproducing the cloud/dashboard pipeline without physical hardware.

## 4. Raspberry Pi and LoRa P2P deployment

The live script configures the RAK3172 receiver with:

```text
AT+NWM=0
AT+P2P=868000000:7:0:0:10:14
AT+PRECV=65535
```

Install the Raspberry Pi environment:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
python3 -m venv ~/paper2-live-env
source ~/paper2-live-env/bin/activate
pip install -r requirements-raspberry-pi.txt
sudo usermod -aG dialout "$USER"
```

Copy both local templates, add ThingSpeak write keys to the local configuration,
and follow `src/raspberry_pi/README.md`.

### Recommended live payload

```text
Tair,Rhair,CO2air,Tot_PAR,EC_drain_PC,pH_drain_PC,Cum_irr
```

The script calculates `HumDef`, uses an explicit configurable fallback for
`Tot_PAR_Lamps`, generates the exact lag/rolling feature names required by the
included nutrient models, predicts EC and pH at +12 hours, computes an
experimental production indicator, logs locally, and uploads results.

## 5. ThingSpeak mappings

### Channel A — measurements

| Field | Variable |
|---|---|
| 1 | Tair |
| 2 | Rhair |
| 3 | CO2air |
| 4 | Tot_PAR |
| 5 | EC_drain_PC |
| 6 | pH_drain_PC |
| 7 | Cum_irr |

### Channel B — predictions and link quality

| Field | Variable |
|---|---|
| 1 | measured EC |
| 2 | predicted EC at +12 h |
| 3 | measured pH |
| 4 | predicted pH at +12 h |
| 5 | weekly production indicator |
| 6 | forecast age in minutes |
| 7 | RSSI |
| 8 | SNR |

Real API keys belong only in `*.local.json` files, which are excluded by
`.gitignore`.

## 6. Power BI dashboard

Open `dashboard/LiveGreenHouseMonitoring.pbix` in Microsoft Power BI Desktop.
The dashboard reads ThingSpeak feeds for near-real-time measurement and forecast
visualization. Review Power Query sources and credentials before refreshing or
publishing. See `dashboard/README.md`.

## 7. Data and outputs

The repository contains a synthetic input example and derived manuscript
artifacts only. It does not include the full source dataset. See
`DATA_AVAILABILITY.md`.

## Limitations

- Live use outside the original greenhouse domain requires independent validation.
- Legacy payload conversions are approximations and are logged as such.
- The production model requires many variables absent from the compact live
  payload; imputed live output is an experimental indicator, not a validated
  crop-yield estimate.
- Predictions are decision-support outputs and are not autonomous dosing commands.

## License and citation

Software is released under the MIT License. Dataset terms remain governed by
the original data provider. Citation metadata are provided in `CITATION.cff`.
