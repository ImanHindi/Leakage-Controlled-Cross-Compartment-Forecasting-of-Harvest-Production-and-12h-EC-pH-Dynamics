#!/usr/bin/env python3
"""
Live LoRa-P2P receiver -> Paper-2 models -> two ThingSpeak channels.

This program replaces CSV replay with live RAK3172 LoRa P2P reception.
It:
1) receives greenhouse measurements from the ESP32/RAK3172;
2) logs every accepted packet locally;
3) aggregates measurements to hourly medians;
4) builds the lag/rolling features described in Paper 2;
5) predicts EC and pH 12 hours ahead using trained delta models;
6) optionally predicts the weekly production indicator using the trained
   Extra-Trees model;
7) uploads raw measurements and model outputs to two ThingSpeak channels.

IMPORTANT
---------
The exact serialized models, scalers/imputers and feature names used during
training must be supplied in the JSON configuration. The code never silently
uses CSV forecasts and never replaces missing model inputs with soil moisture.

Recommended LoRa payload
------------------------
CSV:
    Tair,Rhair,CO2air,Tot_PAR,EC_drain_PC,pH_drain_PC,Cum_irr

or JSON:
    {"Tair":25.2,"Rhair":71.0,"CO2air":430,"Tot_PAR":120,
     "EC_drain_PC":2.1,"pH_drain_PC":5.8,"Cum_irr":12.4}

Legacy eight-value payloads from the earlier ESP32 code are also supported:
    moisture,lux,tds,pH,temperature,humidity,nutrientStatus,waterPumpStatus

For that legacy format:
- EC is estimated as TDS / tds_ec_factor;
- PAR is estimated as lux * lux_to_par_factor;
- CO2 must be supplied as a configured fallback;
- cumulative irrigation is integrated from pump status and configured flow.
These substitutions are explicitly flagged in the log and should not be
presented as equivalent to directly measured model inputs.

ThingSpeak channel A
--------------------
field1 Tair
field2 Rhair
field3 CO2air
field4 Tot_PAR
field5 EC_drain_PC
field6 pH_drain_PC
field7 Cum_irr

ThingSpeak channel B
--------------------
field1 EC_measured
field2 EC_predicted_t12
field3 pH_measured
field4 pH_predicted_t12
field5 Weekly_ProdA_prediction
field6 ForecastAgeMinutes
field7 RSSI (when reported by the radio)
field8 SNR  (when reported by the radio)
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
import pandas as pd
import requests

try:
    import serial
except ImportError:  # Model validation can run without Raspberry Pi serial support.
    serial = None


THINGSPEAK_UPDATE_URL = "https://api.thingspeak.com/update.json"
BASE_VARIABLES = [
    "Tair",
    "Rhair",
    "CO2air",
    "Tot_PAR",
    "Tot_PAR_Lamps",
    "HumDef",
    "EC_drain_PC",
    "pH_drain_PC",
    "Cum_irr",
]
LAGS_H = [1, 3, 6, 12, 24, 48]
ROLLING_H = [3, 6, 12, 24, 48]
_STOP = False


def request_stop(signum: int, frame: Any) -> None:
    global _STOP
    _STOP = True
    print("\nStop requested; finishing the current cycle.", flush=True)


def safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def clean_number(value: Any) -> str | None:
    number = safe_float(value)
    return None if number is None else f"{number:.10g}"


def normalize_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def humidity_deficit_kpa(t_c: float, rh_pct: float) -> float:
    """Vapour-pressure/humidity deficit in kPa."""
    saturation = 0.6108 * math.exp((17.27 * t_c) / (t_c + 237.3))
    return saturation * max(0.0, 1.0 - rh_pct / 100.0)


def linear_trend(values: pd.Series) -> float:
    y = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    mask = np.isfinite(y)
    if mask.sum() < 2:
        return float("nan")
    x = np.arange(len(y), dtype=float)[mask]
    return float(np.polyfit(x, y[mask], 1)[0])


@dataclass
class RadioPacket:
    timestamp: pd.Timestamp
    values: dict[str, Any]
    rssi: float | None = None
    snr: float | None = None
    raw_text: str = ""
    approximations: tuple[str, ...] = ()


class ModelArtifact:
    """Loads a scikit-learn model or pipeline plus optional preprocessing."""

    def __init__(self, name: str, spec: dict[str, Any], base_dir: Path):
        self.name = name
        self.spec = spec
        self.kind = str(spec.get("prediction_kind", "direct")).lower()
        self.allow_missing = bool(spec.get("allow_missing", False))

        self.model = joblib.load(self._path(spec["model"], base_dir))
        self.imputer = (
            joblib.load(self._path(spec["imputer"], base_dir))
            if spec.get("imputer")
            else None
        )
        self.scaler = (
            joblib.load(self._path(spec["scaler"], base_dir))
            if spec.get("scaler")
            else None
        )
        self.feature_names = self._load_feature_names(spec, base_dir)

    @staticmethod
    def _path(value: str, base_dir: Path) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else base_dir / path

    def _load_feature_names(
        self, spec: dict[str, Any], base_dir: Path
    ) -> list[str]:
        if spec.get("features"):
            value = spec["features"]
            if isinstance(value, list):
                return [str(item) for item in value]
            feature_path = self._path(str(value), base_dir)
            if feature_path.suffix.lower() == ".json":
                loaded = json.loads(feature_path.read_text(encoding="utf-8"))
            else:
                loaded = joblib.load(feature_path)
            if isinstance(loaded, dict):
                for key in ("features", "feature_names", "columns"):
                    if key in loaded:
                        return [str(item) for item in loaded[key]]
            return [str(item) for item in loaded]

        for obj in (self.model, self.scaler, self.imputer):
            names = getattr(obj, "feature_names_in_", None)
            if names is not None:
                return [str(item) for item in names]

        raise ValueError(
            f"{self.name}: feature names are required. Add a 'features' list "
            "or feature-manifest path to the configuration."
        )

    def predict(self, feature_row: dict[str, float]) -> float:
        aliases = build_normalized_feature_lookup(feature_row)
        missing: list[str] = []
        ordered: dict[str, float] = {}

        for required in self.feature_names:
            if required in feature_row:
                ordered[required] = feature_row[required]
                continue
            normalized = normalize_name(required)
            if normalized in aliases:
                ordered[required] = aliases[normalized]
            else:
                missing.append(required)
                if self.allow_missing:
                    ordered[required] = float("nan")

        if missing and not self.allow_missing:
            preview = ", ".join(missing[:15])
            raise KeyError(
                f"{self.name}: {len(missing)} trained features cannot be "
                f"constructed from live history. First missing: {preview}"
            )

        X: Any = pd.DataFrame([ordered], columns=self.feature_names)
        if self.imputer is not None:
            X = self.imputer.transform(X)
        if self.scaler is not None:
            X = self.scaler.transform(X)

        prediction = np.asarray(self.model.predict(X)).reshape(-1)
        if prediction.size == 0:
            raise RuntimeError(f"{self.name}: model returned no prediction.")
        return float(prediction[0])


def add_alias(store: dict[str, float], key: str, value: float) -> None:
    if math.isfinite(value):
        store[key] = float(value)


def build_normalized_feature_lookup(features: dict[str, float]) -> dict[str, float]:
    """Allow harmless punctuation/case differences in saved feature manifests."""
    return {normalize_name(key): value for key, value in features.items()}


class LiveFeatureEngine:
    """Maintains raw packets and produces hourly features used in Paper 2."""

    def __init__(self, history_hours: int = 24 * 21):
        self.raw = pd.DataFrame()
        self.history_hours = history_hours

    def append(self, packet: RadioPacket) -> None:
        row = {"timestamp": packet.timestamp, **packet.values}
        frame = pd.DataFrame([row]).set_index("timestamp")
        self.raw = pd.concat([self.raw, frame]).sort_index()
        self.raw = self.raw[~self.raw.index.duplicated(keep="last")]
        cutoff = packet.timestamp - pd.Timedelta(hours=self.history_hours)
        self.raw = self.raw.loc[self.raw.index >= cutoff]

    def hourly(self) -> pd.DataFrame:
        if self.raw.empty:
            return pd.DataFrame()
        numeric = self.raw.apply(pd.to_numeric, errors="coerce")
        hourly = numeric.resample("1h").median()
        # The paper interpolated only short internal gaps. Limit=3 prevents
        # bridging longer missing periods.
        hourly = hourly.interpolate(
            method="time", limit=3, limit_area="inside"
        )
        return hourly

    def nutrient_features(self) -> tuple[dict[str, float], pd.Timestamp]:
        hourly = self.hourly()
        if hourly.empty:
            raise RuntimeError("No hourly history is available.")

        latest_time = hourly.dropna(how="all").index[-1]
        h = hourly.loc[:latest_time].copy()

        latest = h.iloc[-1]
        feature: dict[str, float] = {}

        # Current values and common aliases.
        for variable in BASE_VARIABLES:
            if variable in latest and pd.notna(latest[variable]):
                add_alias(feature, variable, float(latest[variable]))

        hour = latest_time.hour + latest_time.minute / 60.0
        doy = latest_time.dayofyear
        for key, value in {
            "hour_sin": math.sin(2 * math.pi * hour / 24.0),
            "hour_cos": math.cos(2 * math.pi * hour / 24.0),
            "dayofyear_sin": math.sin(2 * math.pi * doy / 365.25),
            "dayofyear_cos": math.cos(2 * math.pi * doy / 365.25),
            "doy_sin": math.sin(2 * math.pi * doy / 365.25),
            "doy_cos": math.cos(2 * math.pi * doy / 365.25),
        }.items():
            add_alias(feature, key, value)

        for variable in BASE_VARIABLES:
            if variable not in h:
                continue
            series = h[variable]

            for lag in LAGS_H:
                if len(series) > lag and pd.notna(series.iloc[-1 - lag]):
                    value = float(series.iloc[-1 - lag])
                    for key in (
                        f"{variable}__lag{lag}",
                        f"{variable} (lag {lag} h)",
                        f"{variable}_lag_{lag}h",
                        f"{variable}_lag{lag}",
                    ):
                        add_alias(feature, key, value)

            for window in ROLLING_H:
                values = series.tail(window)
                if values.notna().sum() < window:
                    continue
                mean = float(values.mean())
                sd = float(values.std(ddof=0))
                trend = linear_trend(values)
                variants = {
                    f"{variable}__mean{window}": mean,
                    f"{variable}__std{window}": sd,
                    f"{variable}__trend{window}": trend,
                    f"{variable} (mean {window} h)": mean,
                    f"{variable}_mean_{window}h": mean,
                    f"{variable}_roll_mean_{window}h": mean,
                    f"{variable} (SD {window} h)": sd,
                    f"{variable}_sd_{window}h": sd,
                    f"{variable}_std_{window}h": sd,
                    f"{variable} (trend {window} h)": trend,
                    f"{variable}_trend_{window}h": trend,
                }
                for key, value in variants.items():
                    add_alias(feature, key, value)

        return feature, latest_time

    def production_features(
        self,
        harvest_state: dict[str, Any],
    ) -> tuple[dict[str, float], pd.Timestamp]:
        hourly = self.hourly()
        if hourly.empty:
            raise RuntimeError("No hourly history is available.")

        latest_time = hourly.dropna(how="all").index[-1]
        h = hourly.loc[:latest_time]
        feature: dict[str, float] = {}

        last_harvest_text = harvest_state.get("last_harvest_timestamp")
        last_harvest = (
            pd.Timestamp(last_harvest_text)
            if last_harvest_text
            else latest_time - pd.Timedelta(days=14)
        )
        inter = h.loc[h.index > last_harvest]

        windows: list[tuple[str, pd.DataFrame]] = [
            ("7 d", h.tail(24 * 7)),
            ("14 d", h.tail(24 * 14)),
            ("inter-harvest", inter),
        ]

        for label, frame in windows:
            if frame.empty:
                continue
            for variable in BASE_VARIABLES:
                if variable not in frame:
                    continue
                values = frame[variable].dropna()
                if values.empty:
                    continue
                stats = {
                    "mean": float(values.mean()),
                    "SD": float(values.std(ddof=0)),
                    "min": float(values.min()),
                    "max": float(values.max()),
                    "sum": float(values.sum()),
                    "trend": linear_trend(values),
                }
                token = label.replace(" ", "_").replace("-", "_")
                for stat, value in stats.items():
                    for key in (
                        f"{variable} ({stat} {label})",
                        f"{variable}_{stat.lower()}_{token}",
                    ):
                        add_alias(feature, key, value)

        previous = [
            float(x)
            for x in harvest_state.get("previous_production_values", [])
            if safe_float(x) is not None
        ]
        if previous:
            add_alias(feature, "previous_harvest", previous[-1])
            add_alias(feature, "ProdA_previous", previous[-1])
            add_alias(
                feature,
                "previous_3_harvest_mean",
                float(np.mean(previous[-3:])),
            )
            add_alias(feature, "ProdA_previous3_mean", float(np.mean(previous[-3:])))

        days_since = (latest_time - last_harvest).total_seconds() / 86400.0
        add_alias(feature, "days_since_harvest", days_since)
        add_alias(feature, "inter_harvest_days", days_since)

        return feature, latest_time


class LoRaReceiver:
    def __init__(self, config: dict[str, Any]):
        radio = config["radio"]
        if serial is None:
            raise RuntimeError(
                "pyserial is required for live LoRa reception. Install "
                "requirements-raspberry-pi.txt or use --validate-models."
            )
        self.port = str(radio.get("serial_port", "/dev/serial0"))
        self.baud = int(radio.get("baud_rate", 115200))
        self.frequency = int(radio.get("frequency_hz", 868000000))
        self.sf = int(radio.get("spreading_factor", 7))
        self.bandwidth_code = int(radio.get("bandwidth_code", 0))
        self.coding_rate_code = int(radio.get("coding_rate_code", 0))
        self.preamble = int(radio.get("preamble_symbols", 10))
        self.tx_power = int(radio.get("tx_power_dbm", 14))
        self.serial = serial.Serial(self.port, self.baud, timeout=1)

    def send_at(self, command: str, wait_s: float = 0.2) -> list[str]:
        self.serial.write((command + "\r\n").encode("utf-8"))
        self.serial.flush()
        time.sleep(wait_s)
        lines: list[str] = []
        while self.serial.in_waiting:
            line = self.serial.readline().decode("utf-8", errors="ignore").strip()
            if line:
                lines.append(line)
        return lines

    def setup(self) -> None:
        for command, wait in (
            ("AT", 0.5),
            ("AT+PRECV=0", 0.2),
            ("AT+NWM=0", 0.5),
            (
                "AT+P2P="
                f"{self.frequency}:{self.sf}:{self.bandwidth_code}:"
                f"{self.coding_rate_code}:{self.preamble}:{self.tx_power}",
                0.5,
            ),
            ("AT+PRECV=65535", 0.2),
        ):
            responses = self.send_at(command, wait)
            print(f"{command}: {' | '.join(responses) if responses else 'sent'}")
        print("LoRa P2P receiver ready.", flush=True)

    def read_event(self) -> tuple[str, float | None, float | None] | None:
        if not self.serial.in_waiting:
            return None
        line = self.serial.readline().decode("utf-8", errors="ignore").strip()
        if "+EVT:RXP2P" not in line:
            return None

        # RAK firmware variants may report RSSI/SNR before the final HEX token.
        tokens = [token.strip() for token in line.split(":")]
        hex_payload = tokens[-1]
        if not re.fullmatch(r"[0-9A-Fa-f]+", hex_payload or ""):
            return None

        numbers = [safe_float(token) for token in tokens[1:-1]]
        finite = [x for x in numbers if x is not None]
        rssi = finite[-2] if len(finite) >= 2 else None
        snr = finite[-1] if len(finite) >= 1 else None

        try:
            text = bytes.fromhex(hex_payload).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            print(f"Rejected non-UTF8 payload: {hex_payload}", file=sys.stderr)
            return None
        return text.strip(), rssi, snr

    def close(self) -> None:
        self.serial.close()


class PacketDecoder:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        live = config.get("live_input", {})
        self.tds_ec_factor = float(live.get("tds_ec_factor", 500.0))
        self.lux_to_par = float(live.get("lux_to_par_factor", 0.0185))
        self.co2_fallback = safe_float(live.get("co2_fallback_ppm"))
        self.tot_par_lamps_fallback = float(live.get("tot_par_lamps_fallback", 0.0))
        self.irrigation_flow_lph = float(
            live.get("irrigation_flow_lph", 0.0)
        )
        self.cumulative_irrigation = float(
            live.get("initial_cumulative_irrigation_l", 0.0)
        )
        self.last_packet_time: pd.Timestamp | None = None

    def decode(
        self,
        text: str,
        rssi: float | None,
        snr: float | None,
    ) -> RadioPacket:
        now = pd.Timestamp.now().floor("s")
        approximations: list[str] = []

        if text.lstrip().startswith("{"):
            payload = json.loads(text)
            values = {key: payload.get(key) for key in BASE_VARIABLES if key != "HumDef"}
            if safe_float(values.get("Tot_PAR_Lamps")) is None:
                values["Tot_PAR_Lamps"] = self.tot_par_lamps_fallback
                approximations.append("Tot_PAR_Lamps configured fallback")
            missing = [
                key for key in BASE_VARIABLES
                if key != "HumDef" and safe_float(values.get(key)) is None
            ]
            if missing:
                raise ValueError(f"JSON packet is missing: {', '.join(missing)}")
            values = {key: float(values[key]) for key in values}
        else:
            parts = [item.strip() for item in text.split(",")]
            if len(parts) == 7:
                names = [
                    "Tair",
                    "Rhair",
                    "CO2air",
                    "Tot_PAR",
                    "EC_drain_PC",
                    "pH_drain_PC",
                    "Cum_irr",
                ]
                numbers = [safe_float(value) for value in parts]
                if any(value is None for value in numbers):
                    raise ValueError("The seven-value packet contains non-numeric data.")
                values = dict(zip(names, (float(x) for x in numbers)))
                values["Tot_PAR_Lamps"] = self.tot_par_lamps_fallback
                approximations.append("Tot_PAR_Lamps configured fallback")
            elif len(parts) == 8:
                moisture, lux, tds, ph, temp, rh = [
                    safe_float(x) for x in parts[:6]
                ]
                if any(x is None for x in (moisture, lux, tds, ph, temp, rh)):
                    raise ValueError("Legacy packet has invalid numeric fields.")
                if self.co2_fallback is None:
                    raise ValueError(
                        "Legacy packet does not contain CO2air. Set "
                        "live_input.co2_fallback_ppm or transmit the recommended "
                        "seven model inputs."
                    )

                pump_on = str(parts[7]).strip().lower() in {
                    "1", "on", "true", "running", "pump_on"
                }
                if self.last_packet_time is not None and pump_on:
                    hours = max(
                        0.0,
                        (now - self.last_packet_time).total_seconds() / 3600.0,
                    )
                    self.cumulative_irrigation += self.irrigation_flow_lph * hours

                values = {
                    "Tair": float(temp),
                    "Rhair": float(rh),
                    "CO2air": float(self.co2_fallback),
                    "Tot_PAR": float(lux) * self.lux_to_par,
                    "Tot_PAR_Lamps": self.tot_par_lamps_fallback,
                    "EC_drain_PC": float(tds) / self.tds_ec_factor,
                    "pH_drain_PC": float(ph),
                    "Cum_irr": self.cumulative_irrigation,
                }
                approximations.extend(
                    [
                        "CO2air configured fallback",
                        "PAR converted from lux",
                        "Tot_PAR_Lamps configured fallback",
                        "EC converted from TDS",
                        "Cum_irr integrated from pump status",
                    ]
                )
            else:
                raise ValueError(
                    f"Expected JSON, 7 model values, or legacy 8 values; received "
                    f"{len(parts)} values."
                )

        values["HumDef"] = humidity_deficit_kpa(values["Tair"], values["Rhair"])
        self.last_packet_time = now
        return RadioPacket(
            timestamp=now,
            values=values,
            rssi=rssi,
            snr=snr,
            raw_text=text,
            approximations=tuple(approximations),
        )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def append_csv(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def post_thingspeak(
    session: requests.Session,
    api_key: str,
    fields: dict[str, Any],
    status: str,
    timeout: float,
) -> int:
    payload: dict[str, str] = {"api_key": api_key, "status": status[:255]}
    for field, raw in fields.items():
        value = clean_number(raw)
        if value is not None:
            payload[field] = value
    response = session.post(
        THINGSPEAK_UPDATE_URL, data=payload, timeout=timeout
    )
    response.raise_for_status()
    result = response.json()
    entry_id = int(result.get("entry_id", 0))
    if entry_id <= 0:
        raise RuntimeError(f"ThingSpeak rejected the update: {result}")
    return entry_id


def prediction_status(
    packet: RadioPacket,
    forecast_time: pd.Timestamp | None,
    notes: Iterable[str],
) -> str:
    parts = [
        f"source_timestamp={packet.timestamp.isoformat()}",
        f"forecast_timestamp={forecast_time.isoformat() if forecast_time else ''}",
    ]
    if packet.approximations:
        parts.append("approximations=" + "|".join(packet.approximations))
    parts.extend(notes)
    return ";".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, required=True,
        help="Path to live_lora_model_config.json",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Receive, log and predict without uploading to ThingSpeak.",
    )
    parser.add_argument(
        "--max-packets", type=int, default=None,
        help="Stop after this many accepted packets.",
    )
    parser.add_argument(
        "--validate-models", action="store_true",
        help="Load and validate configured model artifacts, then exit before opening the serial port.",
    )
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = load_json(config_path)
    base_dir = config_path.parent

    models_cfg = config["models"]
    ec_model = ModelArtifact("EC 12-hour delta", models_cfg["ec"], base_dir)
    ph_model = ModelArtifact("pH 12-hour delta", models_cfg["ph"], base_dir)
    production_model = (
        ModelArtifact("weekly production", models_cfg["production"], base_dir)
        if models_cfg.get("production", {}).get("enabled", True)
        else None
    )

    if args.validate_models:
        print("Model artifacts loaded successfully.")
        print(f"EC features: {len(ec_model.feature_names)}")
        print(f"pH features: {len(ph_model.feature_names)}")
        if production_model:
            print(f"Production features: {len(production_model.feature_names)}")
        return 0

    output_cfg = config.get("output", {})
    log_path = Path(output_cfg.get("csv_log", "live_lora_predictions.csv"))
    if not log_path.is_absolute():
        log_path = base_dir / log_path

    state_path = Path(
        output_cfg.get("harvest_state_json", "harvest_state.json")
    )
    if not state_path.is_absolute():
        state_path = base_dir / state_path
    harvest_state = load_json(state_path) if state_path.exists() else {}

    thing = config["thingspeak"]
    min_upload_s = max(15.0, float(thing.get("minimum_interval_seconds", 20)))
    timeout = float(thing.get("timeout_seconds", 30))
    raw_key = str(thing["data_channel_write_api_key"]).strip()
    prediction_key = str(
        thing["prediction_channel_write_api_key"]
    ).strip()

    engine = LiveFeatureEngine(
        history_hours=int(config.get("history_hours", 24 * 21))
    )
    decoder = PacketDecoder(config)
    receiver = LoRaReceiver(config)

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    session = requests.Session()
    last_upload = 0.0
    accepted = 0
    latest_ec12: float | None = None
    latest_ph12: float | None = None
    latest_production: float | None = None
    latest_forecast_time: pd.Timestamp | None = None

    print("Loading live Paper-2 inference pipeline...")
    print(f"EC features: {len(ec_model.feature_names)}")
    print(f"pH features: {len(ph_model.feature_names)}")
    if production_model:
        print(f"Production features: {len(production_model.feature_names)}")
        print(
            "WARNING: the production model was trained on the paper's greenhouse "
            "domain. A live prediction on a different crop/facility is a "
            "decision-support extrapolation, not a validated yield estimate."
        )

    receiver.setup()

    try:
        while not _STOP:
            event = receiver.read_event()
            if event is None:
                time.sleep(0.01)
                continue

            raw_text, rssi, snr = event
            try:
                packet = decoder.decode(raw_text, rssi, snr)
            except Exception as exc:
                print(f"Rejected packet '{raw_text}': {exc}", file=sys.stderr)
                receiver.send_at("AT+PRECV=65535", 0.05)
                continue

            engine.append(packet)
            accepted += 1
            notes: list[str] = []
            forecast_age_minutes: float | None = None

            # The nutrient models require 48 h history because Paper 2 used
            # lags/rolling windows up to 48 h.
            try:
                nutrient_feature, feature_time = engine.nutrient_features()
                ec_delta = ec_model.predict(nutrient_feature)
                ph_delta = ph_model.predict(nutrient_feature)
                current_ec = float(packet.values["EC_drain_PC"])
                current_ph = float(packet.values["pH_drain_PC"])
                latest_ec12 = (
                    current_ec + ec_delta
                    if ec_model.kind == "delta"
                    else ec_delta
                )
                latest_ph12 = (
                    current_ph + ph_delta
                    if ph_model.kind == "delta"
                    else ph_delta
                )
                latest_forecast_time = feature_time
                forecast_age_minutes = (
                    packet.timestamp - feature_time
                ).total_seconds() / 60.0
            except Exception as exc:
                notes.append(f"nutrient_model_wait={type(exc).__name__}")
                print(f"Nutrient forecast not ready: {exc}")

            if production_model is not None:
                try:
                    production_feature, _ = engine.production_features(
                        harvest_state
                    )
                    latest_production = production_model.predict(
                        production_feature
                    )
                except Exception as exc:
                    notes.append(f"production_model_wait={type(exc).__name__}")
                    print(f"Production forecast not ready: {exc}")

            row = {
                "timestamp": packet.timestamp.isoformat(),
                **packet.values,
                "EC_predicted_t12": latest_ec12,
                "pH_predicted_t12": latest_ph12,
                "Weekly_ProdA_prediction": latest_production,
                "forecast_timestamp": (
                    latest_forecast_time.isoformat()
                    if latest_forecast_time is not None else ""
                ),
                "forecast_age_minutes": forecast_age_minutes,
                "rssi": packet.rssi,
                "snr": packet.snr,
                "approximations": "|".join(packet.approximations),
                "raw_payload": packet.raw_text,
            }
            append_csv(log_path, row)

            raw_entry: int | str = "dry-run"
            pred_entry: int | str = "dry-run"
            now_mono = time.monotonic()
            if not args.dry_run and now_mono - last_upload >= min_upload_s:
                status = prediction_status(
                    packet, latest_forecast_time, notes
                )
                try:
                    raw_entry = post_thingspeak(
                        session,
                        raw_key,
                        {
                            "field1": packet.values["Tair"],
                            "field2": packet.values["Rhair"],
                            "field3": packet.values["CO2air"],
                            "field4": packet.values["Tot_PAR"],
                            "field5": packet.values["EC_drain_PC"],
                            "field6": packet.values["pH_drain_PC"],
                            "field7": packet.values["Cum_irr"],
                        },
                        status,
                        timeout,
                    )
                except Exception as exc:
                    raw_entry = "ERROR"
                    print(f"Raw ThingSpeak upload failed: {exc}", file=sys.stderr)

                try:
                    pred_entry = post_thingspeak(
                        session,
                        prediction_key,
                        {
                            "field1": packet.values["EC_drain_PC"],
                            "field2": latest_ec12,
                            "field3": packet.values["pH_drain_PC"],
                            "field4": latest_ph12,
                            "field5": latest_production,
                            "field6": forecast_age_minutes,
                            "field7": packet.rssi,
                            "field8": packet.snr,
                        },
                        status,
                        timeout,
                    )
                except Exception as exc:
                    pred_entry = "ERROR"
                    print(
                        f"Prediction ThingSpeak upload failed: {exc}",
                        file=sys.stderr,
                    )
                last_upload = now_mono

            print(
                f"{packet.timestamp} | EC={packet.values['EC_drain_PC']:.3f} "
                f"EC+12h={latest_ec12 if latest_ec12 is not None else 'WAIT'} "
                f"| pH={packet.values['pH_drain_PC']:.3f} "
                f"pH+12h={latest_ph12 if latest_ph12 is not None else 'WAIT'} "
                f"| weekly ProdA="
                f"{latest_production if latest_production is not None else 'WAIT'} "
                f"| raw entry={raw_entry} prediction entry={pred_entry}",
                flush=True,
            )

            receiver.send_at("AT+PRECV=65535", 0.05)

            if args.max_packets is not None and accepted >= args.max_packets:
                break
    finally:
        receiver.close()

    print(f"Stopped after {accepted} accepted packets. Log: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
