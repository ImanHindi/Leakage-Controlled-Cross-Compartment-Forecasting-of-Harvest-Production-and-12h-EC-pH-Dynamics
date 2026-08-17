# Raspberry Pi live advisory execution — final Paper 2 models

This folder contains two distinct forms of edge evidence:

1. `benchmark_v4_selected_models.py` — the reproducible target-device timing benchmark.
2. `live_lora_p2p_models_to_thingspeak.py` — the HTU LoRa–Raspberry Pi–ThingSpeak–Power BI advisory integration adapter.

The second script **does not perform model training and does not issue model-driven actuator commands**.

## Final frozen models loaded

The configuration points directly to the complete pipelines under `../models/`:

- Production: Extra Trees, 205 predictors.
- EC +12 h: Histogram Gradient Boosting, 202 predictors.
- pH +12 h: Ridge α=0.01, 202 predictors.

`metadata.json` is checked at startup so an old Ridge-EC or pre-v4 artifact fails loudly.

## Final 12-h feature construction

The live adapter mirrors the final v4 feature naming and causal direction:

- hourly **median** aggregation;
- broad EC/pH QC bounds used by the paper;
- past-only `ffill(limit=3)` for feature histories;
- lags at 1, 3, 6, 12, 24, and 48 h;
- rolling mean, sample SD, and trend at 3, 6, 12, 24, and 48 h;
- hour/day-of-year sine and cosine;
- current EC/pH taken from the **unfilled observed hourly median**;
- model outputs interpreted as 12-h changes and reconstructed as current + predicted change.

The final source variables are:

`CO2air, Cum_irr, EC_drain_PC, HumDef, Rhair, Tair, Tot_PAR, Tot_PAR_Lamps, pH_drain_PC`

## HTU input mismatch and advisory boundary

The current HTU sensing schema does not provide perfectly equivalent measurements for every AGC variable. The compatibility decoder therefore logs each missing/fallback/converted field. The old eight-value ESP32 payload is accepted, but:

- TDS→EC is an approximate interface conversion;
- lux→PAR is an approximate interface conversion if a factor is configured;
- moisture is **not** substituted for cumulative irrigation;
- missing CO2/HumDef/lamp-PAR values are left missing unless an explicit configuration fallback is supplied;
- missing predictor values are handled by the frozen training-fitted pipeline imputer.

These live outputs are suitable for engineering demonstration/advisory visualization only. They do not establish lettuce-specific prediction accuracy.

## Production advisory output

The scientific production task predicts **recorded harvest-event ProdA**, not a weekly target. Production execution is disabled by default because the 205-feature AGC model contains source variables not all present on the HTU platform.

When production is enabled and `harvest_state.example.json` is replaced with current crop/harvest state, the adapter fills the subset of production features that can be constructed from the live stream and leaves unmapped features missing for the frozen model's training-median imputer. Feature completeness is logged with every prediction.

## Setup

```bash
python3 -m venv ~/paper2-live-env
source ~/paper2-live-env/bin/activate
pip install -r requirements-raspberry-pi.txt
cp configs/live_lora_model_config.example.json configs/live_lora_model_config.local.json
```

Add the Raspberry Pi user to the serial-access group if needed:

```bash
sudo usermod -aG dialout "$USER"
```

Log out and back in after changing group membership.

## Dry-run first

From the repository root:

```bash
python raspberry_pi/live_lora_p2p_models_to_thingspeak.py \
  --config configs/live_lora_model_config.local.json \
  --dry-run
```

Only after the local log and predictions are checked should ThingSpeak write keys be added to the local configuration.

## ThingSpeak mapping

### Channel A — measured/interface fields

1. Tair
2. Rhair
3. CO2air
4. Tot_PAR
5. measured EC
6. measured pH
7. Cum_irr
8. hourly feature completeness

### Channel B — advisory predictions

1. measured EC
2. EC +12 h advisory forecast
3. measured pH
4. pH +12 h advisory forecast
5. ProdA advisory prediction (when enabled)
6. feature completeness
7. RSSI
8. SNR

## Final target-device benchmark

Run from the repository root:

```bash
python raspberry_pi/benchmark_v4_selected_models.py
```

Default paths now point to `models/` and `raspberry_pi/results/`. The script verifies the final model families before timing and records package versions on new runs.

The manuscript-reported benchmark files already in `raspberry_pi/results/` are the definitive original target-device evidence; do not overwrite them merely to change package metadata without documenting a new benchmark run.
