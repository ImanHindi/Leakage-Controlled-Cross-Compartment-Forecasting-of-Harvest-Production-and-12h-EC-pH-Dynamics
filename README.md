# Towards Smart and Sustainable Agriculture in Jordan — Part I

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21653172.svg)](https://doi.org/10.5281/zenodo.21653172)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-ESP32%20%2B%20Raspberry%20Pi-C51A4A.svg)](#implemented-architecture)
[![Communication](https://img.shields.io/badge/Communication-LoRa%20P2P-2E8B57.svg)](#implemented-architecture)
[![Cloud](https://img.shields.io/badge/Cloud-ThingSpeak-1F77B4.svg)](#thingspeak-field-mapping)
[![Dashboard](https://img.shields.io/badge/Dashboard-Power%20BI-F2C811.svg)](#dashboard)

## Overview

This repository accompanies:

**Towards Smart and Sustainable Agriculture in Water-Scarce Jordan — Part I:
Engineering Design and Functional Validation of a LoRa-Enabled Smart NFT
Hydroponic System**

The repository documents the end-to-end engineering platform developed at
Al Hussein Technical University, including the four-channel NFT structure,
ESP32 sensing and local control, bidirectional RAK3172 LoRa P2P communication,
Raspberry Pi edge processing, ThingSpeak cloud upload, Power BI visualization,
and relay-controlled circulation and dosing pumps.

## Repository contents

```text
Paper1_Smart_NFT_GitHub_Ready/
├── configs/
│   └── raspberry_pi_config.example.json
├── dashboard/
│   ├── LiveGreenHouseMonitoring.pbix
│   └── README.md
├── data/
│   └── sample/
│       └── sample_lora_packets.csv
├── docs/
│   └── Paper_1_manuscript_draft.docx
├── figures/
├── firmware/
│   ├── README.md
│   └── esp32_sensing_control/
│       └── esp32_sensing_control.ino
├── hardware/
│   ├── README.md
│   ├── bom/
│   │   └── bill_of_materials.csv
│   └── cad/
│       └── nft_frame_concept.scad
├── software/
│   └── raspberry_pi/
│       ├── README.md
│       └── receiver_control_thingspeak.py
├── CITATION.cff
├── DATA_AVAILABILITY.md
├── SYSTEM_CARD.md
├── LICENSE
├── requirements.txt
└── requirements-raspberry-pi.txt
```

## Implemented architecture

```text
Sensors
  ↓
ESP32 sensing and local safety node
  ↓  868 MHz LoRa P2P uplink
RAK3172 receiver + Raspberry Pi
  ↓
Local CSV logging and ThingSpeak upload
  ↓
Power BI monitoring dashboard

Raspberry Pi supervisory decision
  ↓  LoRa P2P downlink
ESP32 command handling
  ↓
Relay-controlled circulation and dosing pumps
```

## Prototype design summary

- Four circular PVC NFT channels.
- Six planting positions per channel; 24 positions total.
- Channel length: 1.25 m.
- Nominal channel slope: 4% (50 mm drop over 1.25 m).
- Nominal design flow: 20 L/h per channel; 80 L/h total.
- Nominal reservoir: 40 L, operated with headspace.
- Main circulation pump and three independently switched peristaltic pumps.
- RAK3172 radios configured for 868 MHz LoRa point-to-point operation.

These values document the prototype design. Hydraulic uniformity and control
dynamics were not quantitatively characterized in the reported study.

## Quick start

### 1. ESP32

Open:

```text
firmware/esp32_sensing_control/esp32_sensing_control.ino
```

Verify pins, sensor calibration, relay polarity, and stock-solution mappings
before flashing.

### 2. Raspberry Pi

```bash
python3 -m venv ~/paper1-nft-env
source ~/paper1-nft-env/bin/activate
pip install -r requirements-raspberry-pi.txt

cp configs/raspberry_pi_config.example.json \
   configs/raspberry_pi_config.local.json
```

Insert the ThingSpeak write key into the local ignored configuration.

Test:

```bash
python software/raspberry_pi/receiver_control_thingspeak.py \
  --config configs/raspberry_pi_config.local.json \
  --dry-run
```

Run live:

```bash
python software/raspberry_pi/receiver_control_thingspeak.py \
  --config configs/raspberry_pi_config.local.json
```

## LoRa payload

The ESP32 sends:

```text
moisture,lux,tds,pH,temperature,humidity,nutrientStatus,waterPumpStatus
```

Example:

```text
45.2,1250,850,5.82,24.6,68.1,IDLE,ON
```

## ThingSpeak field mapping

| Field | Value |
|---|---|
| 1 | Air temperature |
| 2 | Relative humidity |
| 3 | Light |
| 4 | TDS |
| 5 | Estimated EC |
| 6 | pH |
| 7 | Auxiliary moisture |

## Reproducibility scope

This repository reproduces the implemented sensing–communication–decision–
actuation pathway. The conclusions are deliberately limited to functional
evidence. See `SYSTEM_CARD.md` for limitations and safety considerations.

## Data availability

See `DATA_AVAILABILITY.md`. The study did not use a large external dataset.
Representative packet examples are provided, while calibrated experimental
logs should be released only when available and institutionally approved.

## Dashboard

Open `dashboard/LiveGreenHouseMonitoring.pbix` using Microsoft Power BI
Desktop. Review the data-source settings and change private read keys or local
paths before.

## Citation

Use `CITATION.cff`. Add the final article DOI after publication.

## License

Software is released under the MIT License. Hardware fabrication, electrical
integration, chemical handling, and agricultural deployment remain the user's
responsibility and require appropriate safety review.
