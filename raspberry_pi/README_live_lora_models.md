# Live LoRa P2P inference for Paper 2


## Required model files

Copy the exact serialized artifacts exported by the Paper-2 training pipeline
into a `models` folder, then edit `live_lora_model_config.json`.

For each model, the code needs:

1. the trained estimator or sklearn Pipeline;
2. the exact ordered feature-name list;
3. the fitted scaler, when it is not already inside a Pipeline;
4. the fitted imputer, when it is not already inside a Pipeline.

The EC and pH artifacts must predict **12-hour deltas**. The program reconstructs:

- `EC_predicted_t12 = EC_now + predicted_EC_delta`
- `pH_predicted_t12 = pH_now + predicted_pH_delta`

## Recommended transmitter payload

Transmit these seven values in this exact order:

`Tair,Rhair,CO2air,Tot_PAR,EC_drain_PC,pH_drain_PC,Cum_irr`

A JSON payload with the same names is also accepted.

The older eight-value payload is accepted only for compatibility. It needs
configured approximations for CO2, PAR, EC and cumulative irrigation, which are
explicitly recorded in the status/log.

## Installation on Raspberry Pi

```bash
python3 -m venv ~/paper2-live-env
source ~/paper2-live-env/bin/activate
pip install numpy pandas scikit-learn joblib pyserial requests
```

Run first without cloud uploads:

```bash
python live_lora_p2p_models_to_thingspeak.py \
  --config live_lora_model_config.json \
  --dry-run
```

Then run normally:

```bash
python live_lora_p2p_models_to_thingspeak.py \
  --config live_lora_model_config.json
```

On systems where `/dev/serial0` requires elevated permission, add the user to
the `dialout` group rather than running the whole inference process as root:

```bash
sudo usermod -aG dialout "$USER"
```

Log out and back in after that command.

## ThingSpeak mappings

### Channel A
1. Tair
2. Rhair
3. CO2air
4. Tot_PAR
5. EC_drain_PC
6. pH_drain_PC
7. Cum_irr

### Channel B
1. measured EC
2. predicted EC at +12 h
3. measured pH
4. predicted pH at +12 h
5. weekly production-indicator prediction
6. forecast age in minutes
7. RSSI
8. SNR

## Production model warning

Paper trained the production model on measured harvest events from the
greenhouse study. Predictions in a different crop, facility or sensor domain
are extrapolations and reported as decision-support outputs until
independently validated.
