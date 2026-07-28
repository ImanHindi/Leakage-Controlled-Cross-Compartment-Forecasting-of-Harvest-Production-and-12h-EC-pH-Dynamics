# Paper 2 — Smart Greenhouse Forecasting and LoRa Edge Deployment

This repository accompanies Paper 2 and organizes the reproducible workflow for:

- greenhouse data preparation;
- EC and pH 12-hour forecasting;
- weekly production prediction;
- explainability and evaluation;
- CSV replay to two ThingSpeak channels;
- live LoRa P2P reception and inference on Raspberry Pi;
- local logging and cloud visualization.

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
│   │   └── live_packet_example.csv
│   └── README/
├── docs/
│   └── Paper_2_draft.docx
├── models/
│   └── README.md
├── src/
│   ├── raspberry_pi/
│   │   └── live_lora_p2p_models_to_thingspeak.py
│   └── replay/
│       └── stream_one_team_two_thingspeak_channels.py
├── training/
│   ├── Paper_2_Enhanced_AGC2_Reproducible_Analysis_CORRECTED_v3.ipynb
│   └── README.md
├── DATA_AVAILABILITY.md
├── MODEL_CARD.md
├── requirements.txt
└── requirements-raspberry-pi.txt
```

## Two operating modes

### 1. Reproducible CSV replay

`src/replay/stream_one_team_two_thingspeak_channels.py` replays one greenhouse
team from historical files and uploads raw measurements and precomputed
forecasts to two ThingSpeak channels.

This mode is useful for:

- dashboard development;
- cloud-pipeline verification;
- reproducing the paper's visualization flow;
- testing without physical LoRa hardware.

### 2. Live Raspberry Pi + LoRa P2P inference

`src/raspberry_pi/live_lora_p2p_models_to_thingspeak.py` runs on Raspberry Pi
and:

1. configures a RAK3172 receiver in LoRa P2P mode;
2. receives measurements through `/dev/serial0`;
3. decodes and validates packets;
4. logs accepted measurements locally;
5. aggregates measurements into hourly medians;
6. builds the lag and rolling features used by Paper 2;
7. predicts EC and pH 12 hours ahead;
8. predicts the weekly production indicator;
9. uploads raw and predicted values to ThingSpeak.

The radio settings are:

```text
AT+NWM=0
AT+P2P=868000000:7:0:0:10:14
AT+PRECV=65535
```

## Recommended LoRa payload

Transmit the seven model variables in this order:

```text
Tair,Rhair,CO2air,Tot_PAR,EC_drain_PC,pH_drain_PC,Cum_irr
```

Example:

```text
25.4,68.2,430,115.6,2.18,5.82,14.3
```

JSON with the same field names is also accepted.

The earlier eight-value packet is supported for compatibility, but it requires
approximations for missing model variables. Such outputs must be treated as
experimental until validated.


## Power BI dashboard

The repository includes:

```text
dashboard/LiveGreenHouseMonitoring.pbix
```

The dashboard is part of the implemented end-to-end workflow and connects the
ThingSpeak data channels to near-real-time monitoring and forecast
visualizations. It should be opened with Microsoft Power BI Desktop.

Before publishing or refreshing the dashboard, inspect its Power Query data
sources and replace project-specific ThingSpeak channel IDs or read keys.
Do not embed ThingSpeak write keys in the PBIX file.

Detailed dashboard instructions are available in
`dashboard/README.md`.

## Raspberry Pi installation

On Raspberry Pi OS:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
python3 -m venv ~/paper2-live-env
source ~/paper2-live-env/bin/activate
pip install -r requirements-raspberry-pi.txt
```

Give the current user serial-port permission:

```bash
sudo usermod -aG dialout "$USER"
```

Log out and sign in again after changing group membership.

Copy the example configuration:

```bash
cp configs/live_lora_model_config.example.json \
   configs/live_lora_model_config.local.json
```

Edit the local file and provide:

- ThingSpeak write API keys;
- exact model paths;
- exact scaler/imputer paths;
- exact feature-name manifest paths;
- serial and packet-conversion settings.

Test without cloud upload:

```bash
python src/raspberry_pi/live_lora_p2p_models_to_thingspeak.py \
  --config configs/live_lora_model_config.local.json \
  --dry-run
```

Run normally:

```bash
python src/raspberry_pi/live_lora_p2p_models_to_thingspeak.py \
  --config configs/live_lora_model_config.local.json
```

## ThingSpeak channel mapping

### Channel A — live/raw greenhouse data

| Field | Variable |
|---|---|
| 1 | Tair |
| 2 | Rhair |
| 3 | CO2air |
| 4 | Tot_PAR |
| 5 | EC_drain_PC |
| 6 | pH_drain_PC |
| 7 | Cum_irr |

### Channel B — measured and predicted values

| Field | Variable |
|---|---|
| 1 | measured EC |
| 2 | predicted EC at +12 h |
| 3 | measured pH |
| 4 | predicted pH at +12 h |
| 5 | weekly production-indicator prediction |
| 6 | forecast age in minutes |
| 7 | RSSI |
| 8 | SNR |

## Training and model export

Copy the Paper 2 training notebook into `training/`. It should export the exact
trained estimators, preprocessing objects, and feature manifests described in
`training/README.md`.

The repository package does not include the notebook because the notebook file
was not supplied during assembly. It also does not include the full dataset or
trained model binaries.

## Data availability

See [DATA_AVAILABILITY.md](DATA_AVAILABILITY.md).

The repository includes only a synthetic schema example. The full research
dataset should be obtained from its authorized source and must not be committed
unless redistribution is explicitly permitted.

## Reproducibility checklist

Before creating a release:

- [ ] Add the final training notebook or converted scripts.
- [ ] Export and test the EC, pH, and production model artifacts.
- [ ] Add exact environment/version information.
- [ ] Add the official dataset citation and access link.
- [ ] Confirm chronological split and feature-engineering code.
- [ ] Remove all API keys, passwords, tokens, and private URLs.
- [ ] Test CSV replay.
- [ ] Test Raspberry Pi LoRa reception in `--dry-run` mode.
- [ ] Test ThingSpeak uploads.
- [ ] Open and refresh `dashboard/LiveGreenHouseMonitoring.pbix`.
- [ ] Remove private ThingSpeak keys and local paths from the PBIX file.
- [ ] Add a software license compatible with data and institutional terms.
- [ ] Create a tagged release matching the manuscript version.

## GitHub upload

From the repository directory:

```bash
git init
git add .
git commit -m "Initial Paper 2 reproducibility release"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

For files larger than GitHub's normal limit, use Git LFS or publish them as a
separate release/archive rather than committing them directly.

## Citation

Add the final paper citation here after acceptance or publication.

## Research-use notice

The forecasts are intended for research and decision support. They should not
be used as autonomous nutrient-dosing commands without facility-specific
calibration, safety limits, and independent validation.
