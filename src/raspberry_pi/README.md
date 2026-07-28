# Raspberry Pi LoRa P2P inference

The script in this directory runs on Raspberry Pi and connects a RAK3172 LoRa
P2P receiver to the fitted Paper 2 models and two ThingSpeak channels.

## Setup

From the repository root on Raspberry Pi OS:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
python3 -m venv ~/paper2-live-env
source ~/paper2-live-env/bin/activate
pip install -r requirements-raspberry-pi.txt
sudo usermod -aG dialout "$USER"
```

Log out and sign in again after adding serial-port permission.

Create private local configuration files:

```bash
cp configs/live_lora_model_config.example.json configs/live_lora_model_config.local.json
cp configs/harvest_state.example.json configs/harvest_state.local.json
```

Enter real ThingSpeak write keys only in the `.local.json` file. Local configs
are ignored by Git.

Validate the included model files before connecting the radio:

```bash
python src/raspberry_pi/live_lora_p2p_models_to_thingspeak.py \
  --config configs/live_lora_model_config.local.json \
  --validate-models
```

Test live reception without cloud upload:

```bash
python src/raspberry_pi/live_lora_p2p_models_to_thingspeak.py \
  --config configs/live_lora_model_config.local.json \
  --dry-run
```

Run normally by removing `--dry-run`.

## Recommended payload

Transmit:

`Tair,Rhair,CO2air,Tot_PAR,EC_drain_PC,pH_drain_PC,Cum_irr`

The trained nutrient pipelines also use `Tot_PAR_Lamps`; the configuration uses
0.0 as an explicit fallback when supplemental-light PAR is unavailable.
`HumDef` is calculated from air temperature and relative humidity.

The legacy eight-value payload remains supported, but TDS-to-EC, lux-to-PAR,
CO2, lamp-PAR, and cumulative-irrigation substitutions are logged as
approximations.

## Important production-model limitation

The production model was trained with many greenhouse setpoint, pipe,
ventilation, lighting, and harvest-history features that are not present in the
compact LoRa payload. The pipeline can impute unavailable features, but its live
output must be treated as an experimental production indicator rather than a
validated yield forecast.
