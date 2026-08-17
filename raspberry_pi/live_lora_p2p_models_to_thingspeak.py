#!/usr/bin/env python3
"""
Final Paper 2 live advisory adapter.

HTU sensors -> ESP32/RAK3172 LoRa P2P -> Raspberry Pi -> frozen v4 models
-> ThingSpeak -> Power BI.

Scientific boundary
-------------------
This script is an engineering integration/advisory-monitoring adapter. The
quantitative paper results come from the untouched AICU evaluation in the
executed v4 notebook, not from this live HTU stream. The AGC-trained models
have not been prospectively validated for lettuce. Missing or non-equivalent
HTU variables are therefore logged as interface adaptations and model outputs
must not be used as autonomous dosing commands.

Final artifacts
---------------
production_model.joblib : Extra Trees (205 predictors; harvest-event ProdA)
ec_12h_model.joblib     : Histogram Gradient Boosting (202 predictors; ΔEC)
ph_12h_model.joblib     : Ridge alpha=0.01 (202 predictors; ΔpH)
metadata.json            : exact feature order and model-family metadata

Recommended direct payload (JSON)
---------------------------------
{
  "Tair": 24.8,
  "Rhair": 67.5,
  "CO2air": 430.0,
  "Tot_PAR": 115.0,
  "Tot_PAR_Lamps": 0.0,
  "HumDef": 4.2,
  "EC_drain_PC": 1.85,
  "pH_drain_PC": 6.10,
  "Cum_irr": 12.4
}

A 9-value CSV payload in the same order is also accepted. The earlier HTU
8-value payload is supported as a compatibility mode:
moisture,lux,tds,pH,temperature,humidity,nutrientStatus,waterPumpStatus
It necessarily uses/omits non-equivalent variables and is always flagged.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import requests

try:
    import serial
except ImportError:
    serial = None


THINGSPEAK_UPDATE_URL = "https://api.thingspeak.com/update.json"
HOURLY_BASE_VARIABLES = [
    "CO2air",
    "Cum_irr",
    "EC_drain_PC",
    "HumDef",
    "Rhair",
    "Tair",
    "Tot_PAR",
    "Tot_PAR_Lamps",
    "pH_drain_PC",
]
DIRECT_CSV_ORDER = [
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
    del signum, frame
    global _STOP
    _STOP = True
    print("\nStop requested; finishing current cycle.", flush=True)


def safe_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if math.isfinite(number) else float("nan")


def is_finite(value: Any) -> bool:
    return math.isfinite(safe_float(value))


def parse_on_off(value: Any) -> bool | None:
    text = str(value).strip().lower()
    if text in {"1", "on", "true", "yes", "running", "active"}:
        return True
    if text in {"0", "off", "false", "no", "stopped", "inactive"}:
        return False
    return None


def rolling_slope(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    mask = np.isfinite(arr)
    if mask.sum() < 2:
        return float("nan")
    x = np.arange(len(arr), dtype=float)[mask]
    y = arr[mask]
    return float(np.polyfit(x, y, 1)[0])


def short_history_slope(values: list[float]) -> float:
    arr = np.asarray([v for v in values if math.isfinite(v)], dtype=float)
    if len(arr) < 2:
        return 0.0
    return float(np.polyfit(np.arange(len(arr), dtype=float), arr, 1)[0])


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_relative(value: str, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base_dir / path).resolve()


def model_class_name(model: Any) -> str:
    if hasattr(model, "named_steps") and "model" in model.named_steps:
        return model.named_steps["model"].__class__.__name__
    return model.__class__.__name__


class FinalModels:
    def __init__(self, config: dict[str, Any], base_dir: Path):
        spec = config["models"]
        metadata_path = resolve_relative(spec["metadata"], base_dir)
        self.metadata = load_json(metadata_path)

        self.production = joblib.load(resolve_relative(spec["production"], base_dir))
        self.ec = joblib.load(resolve_relative(spec["ec_12h"], base_dir))
        self.ph = joblib.load(resolve_relative(spec["ph_12h"], base_dir))

        self.production_features = list(self.metadata["production_features"])
        self.hourly_features = list(self.metadata["hourly_features"])
        self._validate()

    def _validate(self) -> None:
        expected_meta = {
            "production_model_family": "Extra Trees",
            "ec_model_family": "Histogram Gradient Boosting",
            "ph_model_family": "Ridge",
        }
        for key, expected in expected_meta.items():
            actual = self.metadata.get(key)
            if actual != expected:
                raise RuntimeError(f"Wrong final model metadata: {key}={actual!r}; expected {expected!r}")

        expected_classes = {
            "Production": (self.production, "ExtraTreesRegressor"),
            "EC": (self.ec, "HistGradientBoostingRegressor"),
            "pH": (self.ph, "Ridge"),
        }
        for label, (model, expected) in expected_classes.items():
            actual = model_class_name(model)
            if actual != expected:
                raise RuntimeError(f"{label} artifact is {actual}; expected {expected}")

        if len(self.production_features) != 205:
            raise RuntimeError(f"Expected 205 production features; found {len(self.production_features)}")
        if len(self.hourly_features) != 202:
            raise RuntimeError(f"Expected 202 hourly features; found {len(self.hourly_features)}")

        ph_est = self.ph.named_steps["model"] if hasattr(self.ph, "named_steps") else self.ph
        if not np.isclose(float(getattr(ph_est, "alpha", np.nan)), 0.01):
            raise RuntimeError("Final pH artifact is not Ridge(alpha=0.01)")

    @staticmethod
    def _predict(model: Any, features: list[str], row: dict[str, Any]) -> float:
        ordered = {name: safe_float(row.get(name)) for name in features}
        X = pd.DataFrame([ordered], columns=features)
        return float(np.asarray(model.predict(X)).reshape(-1)[0])

    def predict_ec_delta(self, row: dict[str, Any]) -> float:
        return self._predict(self.ec, self.hourly_features, row)

    def predict_ph_delta(self, row: dict[str, Any]) -> float:
        return self._predict(self.ph, self.hourly_features, row)

    def predict_production(self, row: dict[str, Any]) -> float:
        return self._predict(self.production, self.production_features, row)


@dataclass
class RadioPacket:
    timestamp: pd.Timestamp
    values: dict[str, float]
    raw_text: str
    rssi: float | None = None
    snr: float | None = None
    adaptations: tuple[str, ...] = ()


class PacketDecoder:
    def __init__(self, config: dict[str, Any]):
        live = config.get("live_input", {})
        self.tds_ec_factor = float(live.get("tds_ec_factor", 500.0))
        self.lux_to_par_factor = safe_float(live.get("lux_to_par_factor"))
        self.co2_fallback = safe_float(live.get("co2_fallback_ppm"))
        self.humdef_fallback = safe_float(live.get("humdef_fallback"))
        self.lamp_par_fallback = safe_float(live.get("tot_par_lamps_fallback"))
        self.irrigation_flow_lph = max(0.0, safe_float(live.get("irrigation_flow_lph", 0.0)))
        self.cumulative_irrigation = safe_float(live.get("initial_cumulative_irrigation_l", 0.0))
        if not math.isfinite(self.cumulative_irrigation):
            self.cumulative_irrigation = 0.0
        self.last_time: pd.Timestamp | None = None

    def _legacy_packet(self, parts: list[str], now: pd.Timestamp) -> tuple[dict[str, float], list[str]]:
        moisture, lux, tds, ph, temperature, humidity, nutrient_status, water_pump_status = parts
        del moisture, nutrient_status
        adaptations = ["legacy_8_field_packet"]

        tds_v = safe_float(tds)
        lux_v = safe_float(lux)
        ec = tds_v / self.tds_ec_factor if math.isfinite(tds_v) and self.tds_ec_factor > 0 else float("nan")
        if math.isfinite(ec):
            adaptations.append("TDS_to_EC_approximation")

        par = (
            lux_v * self.lux_to_par_factor
            if math.isfinite(lux_v) and math.isfinite(self.lux_to_par_factor)
            else float("nan")
        )
        if math.isfinite(par):
            adaptations.append("lux_to_PAR_approximation")

        # Never substitute the moisture measurement for cumulative irrigation.
        pump_on = parse_on_off(water_pump_status)
        if self.last_time is not None and pump_on is True and self.irrigation_flow_lph > 0:
            elapsed_h = max(0.0, (now - self.last_time).total_seconds() / 3600.0)
            self.cumulative_irrigation += self.irrigation_flow_lph * elapsed_h
            adaptations.append("Cum_irr_integrated_from_pump_state_and_configured_flow")
        elif self.irrigation_flow_lph <= 0:
            adaptations.append("Cum_irr_not_directly_measured")

        values = {
            "CO2air": self.co2_fallback,
            "Cum_irr": self.cumulative_irrigation,
            "EC_drain_PC": ec,
            "HumDef": self.humdef_fallback,
            "Rhair": safe_float(humidity),
            "Tair": safe_float(temperature),
            "Tot_PAR": par,
            "Tot_PAR_Lamps": self.lamp_par_fallback,
            "pH_drain_PC": safe_float(ph),
        }
        for key in ("CO2air", "HumDef", "Tot_PAR_Lamps"):
            if not math.isfinite(values[key]):
                adaptations.append(f"{key}_missing_imputed_by_frozen_pipeline")
            else:
                adaptations.append(f"{key}_configured_fallback")
        return values, adaptations

    def decode(self, text: str, rssi: float | None, snr: float | None) -> RadioPacket:
        now = pd.Timestamp.now(tz="UTC").floor("s")
        adaptations: list[str] = []

        if text.lstrip().startswith("{"):
            payload = json.loads(text)
            values = {name: safe_float(payload.get(name)) for name in HOURLY_BASE_VARIABLES}
            for name, value in values.items():
                if not math.isfinite(value):
                    adaptations.append(f"{name}_missing_imputed_by_frozen_pipeline")
        else:
            parts = [p.strip() for p in text.split(",")]
            if len(parts) == len(DIRECT_CSV_ORDER):
                values = {name: safe_float(value) for name, value in zip(DIRECT_CSV_ORDER, parts)}
                for name, value in values.items():
                    if not math.isfinite(value):
                        adaptations.append(f"{name}_missing_imputed_by_frozen_pipeline")
            elif len(parts) == 8:
                values, adaptations = self._legacy_packet(parts, now)
            else:
                raise ValueError(f"Expected JSON, 9-value direct CSV, or 8-value legacy CSV; received {len(parts)} fields")

        # Same broad QC bounds used in the paper. These are plausibility filters, not crop setpoints.
        ec = values.get("EC_drain_PC", float("nan"))
        ph = values.get("pH_drain_PC", float("nan"))
        if math.isfinite(ec) and not (0.5 <= ec <= 12.0):
            values["EC_drain_PC"] = float("nan")
            adaptations.append("EC_outside_paper_QC_bound")
        if math.isfinite(ph) and not (3.0 <= ph <= 8.5):
            values["pH_drain_PC"] = float("nan")
            adaptations.append("pH_outside_paper_QC_bound")

        self.last_time = now
        return RadioPacket(now, values, text, rssi, snr, tuple(sorted(set(adaptations))))


class LiveFeatureEngine:
    def __init__(self, hourly_features: list[str], production_features: list[str], history_hours: int = 24 * 21):
        self.hourly_features = hourly_features
        self.production_features = production_features
        self.history_hours = max(72, int(history_hours))
        self.raw = pd.DataFrame(columns=HOURLY_BASE_VARIABLES, dtype=float)

    def append(self, packet: RadioPacket) -> None:
        row = pd.DataFrame([packet.values], index=[packet.timestamp])
        self.raw = pd.concat([self.raw, row]).sort_index()
        self.raw = self.raw[~self.raw.index.duplicated(keep="last")]
        cutoff = packet.timestamp - pd.Timedelta(hours=self.history_hours)
        self.raw = self.raw.loc[self.raw.index >= cutoff]

    def hourly_observed(self) -> pd.DataFrame:
        if self.raw.empty:
            return pd.DataFrame(columns=HOURLY_BASE_VARIABLES)
        numeric = self.raw.apply(pd.to_numeric, errors="coerce")
        # Match the paper: hourly median from observed values.
        return numeric.resample("1h").median()

    def nutrient_feature_row(self) -> tuple[dict[str, float], pd.Timestamp, float, float, float]:
        observed = self.hourly_observed()
        if observed.empty:
            raise RuntimeError("No hourly data available")
        valid_rows = observed.dropna(how="all")
        if valid_rows.empty:
            raise RuntimeError("No numeric hourly data available")
        origin = valid_rows.index[-1]
        observed = observed.loc[:origin]

        # Match v4: feature histories use only past-only forward fill, limited to 3 h.
        h = observed.ffill(limit=3)
        feat = h.copy()
        feat["hour_sin"] = np.sin(2 * np.pi * feat.index.hour / 24.0)
        feat["hour_cos"] = np.cos(2 * np.pi * feat.index.hour / 24.0)
        doy = feat.index.dayofyear
        feat["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
        feat["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)

        for col in HOURLY_BASE_VARIABLES:
            for lag in LAGS_H:
                feat[f"{col}__lag{lag}"] = h[col].shift(lag)
            for window in ROLLING_H:
                roll = h[col].rolling(window, min_periods=window)
                feat[f"{col}__mean{window}"] = roll.mean()
                feat[f"{col}__std{window}"] = roll.std(ddof=1)
                feat[f"{col}__trend{window}"] = roll.apply(rolling_slope, raw=True)

        latest = feat.loc[origin]
        row = {name: safe_float(latest.get(name)) for name in self.hourly_features}
        completeness = sum(math.isfinite(v) for v in row.values()) / len(row)

        # Current states must come from unfilled observed hourly medians, as in v4.
        current_ec = safe_float(observed.loc[origin, "EC_drain_PC"])
        current_ph = safe_float(observed.loc[origin, "pH_drain_PC"])
        if not math.isfinite(current_ec) or not math.isfinite(current_ph):
            raise RuntimeError("Current observed EC/pH is unavailable after QC")
        return row, origin, current_ec, current_ph, completeness

    def _daily_live_table(self) -> pd.DataFrame:
        hourly = self.hourly_observed()
        if hourly.empty:
            return pd.DataFrame()
        rows: dict[str, pd.Series] = {}
        for col in ["CO2air", "EC_drain_PC", "HumDef", "Rhair", "Tair", "pH_drain_PC"]:
            rows[f"daily_mean__{col}"] = hourly[col].resample("1D").mean()
        rows["daily_max__Cum_irr"] = hourly["Cum_irr"].resample("1D").max()
        # Approximate DLI from hourly median PAR. Kept explicitly advisory and logged via completeness/adaptation.
        rows["DLI__Tot_PAR"] = (hourly["Tot_PAR"].resample("1D").sum(min_count=1) * 3600.0 / 1e6)
        rows["DLI__Tot_PAR_Lamps"] = (hourly["Tot_PAR_Lamps"].resample("1D").sum(min_count=1) * 3600.0 / 1e6)
        return pd.DataFrame(rows).sort_index()

    def production_feature_row(self, state: dict[str, Any]) -> tuple[dict[str, float], float, list[str]]:
        row = {name: float("nan") for name in self.production_features}
        notes: list[str] = ["live_production_partial_feature_mapping"]
        now = self.raw.index.max() if not self.raw.empty else pd.Timestamp.now(tz="UTC")

        previous = [safe_float(v) for v in state.get("previous_production_values", [])]
        previous = [v for v in previous if math.isfinite(v)]
        last_harvest = pd.to_datetime(state.get("last_harvest_timestamp"), utc=True, errors="coerce")
        crop_start = pd.to_datetime(state.get("crop_start_timestamp"), utc=True, errors="coerce")

        if pd.notna(last_harvest):
            row["days_since_prev"] = (now - last_harvest).total_seconds() / 86400.0
        if pd.notna(crop_start):
            row["crop_day"] = (now - crop_start).total_seconds() / 86400.0
        if state.get("harvest_index") is not None:
            row["harvest_index"] = safe_float(state.get("harvest_index"))
        if previous:
            row["prev_ProdA"] = previous[-1]
            tail = previous[-3:]
            row["prev3_mean"] = float(np.mean(tail))
            row["prev3_std"] = float(np.std(tail, ddof=0))
            row["prev3_trend"] = short_history_slope(tail)

        daily = self._daily_live_table()
        if not daily.empty:
            windows: dict[str, pd.DataFrame] = {
                "w7__": daily.loc[daily.index >= now.floor("D") - pd.Timedelta(days=7)],
                "w14__": daily.loc[daily.index >= now.floor("D") - pd.Timedelta(days=14)],
            }
            if pd.notna(last_harvest):
                windows["int__"] = daily.loc[daily.index >= last_harvest.floor("D")]

            for prefix, frame in windows.items():
                if frame.empty:
                    continue
                for daily_col in frame.columns:
                    s = pd.to_numeric(frame[daily_col], errors="coerce")
                    for stat, value in {
                        "mean": s.mean(),
                        "std": s.std(ddof=0),
                        "min": s.min(),
                        "max": s.max(),
                    }.items():
                        key = f"{prefix}{stat}__{daily_col}"
                        if key in row:
                            row[key] = safe_float(value)

        finite = sum(math.isfinite(safe_float(v)) for v in row.values())
        completeness = finite / len(row)
        notes.append(f"production_feature_completeness={completeness:.3f}")
        notes.append("unmapped_production_features_use_training_median_imputation")
        notes.append("hourly_PAR_to_DLI_is_live_interface_approximation")
        return row, completeness, notes


class LoRaReceiver:
    def __init__(self, config: dict[str, Any]):
        if serial is None:
            raise RuntimeError("pyserial is required for live LoRa use. Install requirements-raspberry-pi.txt first.")
        radio = config["radio"]
        self.port = str(radio.get("serial_port", "/dev/serial0"))
        self.baud = int(radio.get("baud_rate", 115200))
        self.frequency = int(radio.get("frequency_hz", 868000000))
        self.sf = int(radio.get("spreading_factor", 7))
        self.bandwidth = int(radio.get("bandwidth_code", 0))
        self.coding_rate = int(radio.get("coding_rate_code", 0))
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
        commands = [
            ("AT", 0.5),
            ("AT+PRECV=0", 0.2),
            ("AT+NWM=0", 0.5),
            (f"AT+P2P={self.frequency}:{self.sf}:{self.bandwidth}:{self.coding_rate}:{self.preamble}:{self.tx_power}", 0.5),
            ("AT+PRECV=65535", 0.2),
        ]
        for command, wait in commands:
            replies = self.send_at(command, wait)
            print(f"{command}: {' | '.join(replies) if replies else 'sent'}")
        print("LoRa P2P receiver ready.")

    def read_event(self) -> tuple[str, float | None, float | None] | None:
        if not self.serial.in_waiting:
            return None
        line = self.serial.readline().decode("utf-8", errors="ignore").strip()
        if "+EVT:RXP2P" not in line:
            return None
        tokens = [token.strip() for token in line.split(":")]
        hex_payload = tokens[-1]
        if not re.fullmatch(r"[0-9A-Fa-f]+", hex_payload or ""):
            return None
        numeric = [safe_float(token) for token in tokens[1:-1]]
        finite = [v for v in numeric if math.isfinite(v)]
        rssi = finite[-2] if len(finite) >= 2 else None
        snr = finite[-1] if len(finite) >= 1 else None
        try:
            text = bytes.fromhex(hex_payload).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None
        return text.strip(), rssi, snr

    def restart_receive(self) -> None:
        self.send_at("AT+PRECV=65535", 0.05)

    def close(self) -> None:
        self.serial.close()


def append_csv(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def post_thingspeak(session: requests.Session, api_key: str, fields: dict[str, Any], status: str, timeout: float) -> int:
    if not api_key or api_key.startswith("REPLACE_"):
        raise RuntimeError("ThingSpeak write API key is not configured")
    payload: dict[str, str] = {"api_key": api_key, "status": status[:255]}
    for key, value in fields.items():
        number = safe_float(value)
        if math.isfinite(number):
            payload[key] = f"{number:.10g}"
    response = session.post(THINGSPEAK_UPDATE_URL, data=payload, timeout=timeout)
    response.raise_for_status()
    result = response.json()
    entry_id = int(result.get("entry_id", 0))
    if entry_id <= 0:
        raise RuntimeError(f"ThingSpeak rejected update: {result}")
    return entry_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Final Paper 2 live LoRa advisory inference adapter")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true", help="Receive/log/predict without ThingSpeak upload")
    parser.add_argument("--max-packets", type=int, default=None)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = load_json(config_path)
    base_dir = config_path.parent
    models = FinalModels(config, base_dir)
    decoder = PacketDecoder(config)
    engine = LiveFeatureEngine(models.hourly_features, models.production_features, config.get("history_hours", 24 * 21))
    receiver = LoRaReceiver(config)

    output = config.get("output", {})
    log_path = resolve_relative(output.get("csv_log", "../raspberry_pi/live_lora_predictions.csv"), base_dir)
    harvest_path = resolve_relative(output.get("harvest_state_json", "harvest_state.example.json"), base_dir)
    harvest_state = load_json(harvest_path) if harvest_path.exists() else {}
    production_enabled = bool(config.get("production", {}).get("enabled", False))

    thingspeak = config.get("thingspeak", {})
    raw_key = str(thingspeak.get("data_channel_write_api_key", ""))
    pred_key = str(thingspeak.get("prediction_channel_write_api_key", ""))
    min_upload_s = max(15.0, float(thingspeak.get("minimum_interval_seconds", 20)))
    timeout = float(thingspeak.get("timeout_seconds", 30))

    print("Final model verification passed:")
    print(f"  Production: {models.metadata['production_model_family']} ({len(models.production_features)} features)")
    print(f"  EC: {models.metadata['ec_model_family']} ({len(models.hourly_features)} features)")
    print(f"  pH: {models.metadata['ph_model_family']} alpha={models.metadata.get('ph_alpha')} ({len(models.hourly_features)} features)")
    print("ADVISORY MODE: live HTU outputs are not lettuce-specific predictive validation and do not issue dosing commands.")

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    session = requests.Session()
    accepted = 0
    last_upload = 0.0
    receiver.setup()

    try:
        while not _STOP:
            event = receiver.read_event()
            if event is None:
                time.sleep(0.01)
                continue
            text, rssi, snr = event
            try:
                packet = decoder.decode(text, rssi, snr)
            except Exception as exc:
                print(f"Rejected packet: {exc}", file=sys.stderr)
                receiver.restart_receive()
                continue

            engine.append(packet)
            accepted += 1
            ec12 = ph12 = proda = float("nan")
            hourly_completeness = production_completeness = float("nan")
            forecast_origin: pd.Timestamp | None = None
            notes = list(packet.adaptations)

            try:
                feature_row, forecast_origin, current_ec, current_ph, hourly_completeness = engine.nutrient_feature_row()
                ec12 = current_ec + models.predict_ec_delta(feature_row)
                ph12 = current_ph + models.predict_ph_delta(feature_row)
                notes.append(f"hourly_feature_completeness={hourly_completeness:.3f}")
            except Exception as exc:
                notes.append(f"nutrient_forecast_wait={type(exc).__name__}")
                print(f"Nutrient forecast not ready: {exc}")

            if production_enabled:
                try:
                    prod_row, production_completeness, prod_notes = engine.production_feature_row(harvest_state)
                    proda = models.predict_production(prod_row)
                    notes.extend(prod_notes)
                except Exception as exc:
                    notes.append(f"production_forecast_wait={type(exc).__name__}")
                    print(f"Production advisory prediction not ready: {exc}")

            target_time = forecast_origin + pd.Timedelta(hours=12) if forecast_origin is not None else None
            status = ";".join(sorted(set(notes)))
            log_row = {
                "packet_timestamp": packet.timestamp.isoformat(),
                **packet.values,
                "EC_predicted_t12_advisory": ec12,
                "pH_predicted_t12_advisory": ph12,
                "ProdA_advisory_prediction": proda,
                "forecast_origin": forecast_origin.isoformat() if forecast_origin is not None else "",
                "forecast_target_time": target_time.isoformat() if target_time is not None else "",
                "hourly_feature_completeness": hourly_completeness,
                "production_feature_completeness": production_completeness,
                "rssi": rssi,
                "snr": snr,
                "interface_adaptations": status,
                "raw_payload": packet.raw_text,
            }
            append_csv(log_path, log_row)

            raw_entry: int | str = "dry-run"
            pred_entry: int | str = "dry-run"
            now_mono = time.monotonic()
            if not args.dry_run and now_mono - last_upload >= min_upload_s:
                try:
                    raw_entry = post_thingspeak(
                        session,
                        raw_key,
                        {
                            "field1": packet.values.get("Tair"),
                            "field2": packet.values.get("Rhair"),
                            "field3": packet.values.get("CO2air"),
                            "field4": packet.values.get("Tot_PAR"),
                            "field5": packet.values.get("EC_drain_PC"),
                            "field6": packet.values.get("pH_drain_PC"),
                            "field7": packet.values.get("Cum_irr"),
                            "field8": hourly_completeness,
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
                        pred_key,
                        {
                            "field1": packet.values.get("EC_drain_PC"),
                            "field2": ec12,
                            "field3": packet.values.get("pH_drain_PC"),
                            "field4": ph12,
                            "field5": proda,
                            "field6": production_completeness if production_enabled else hourly_completeness,
                            "field7": rssi,
                            "field8": snr,
                        },
                        status,
                        timeout,
                    )
                except Exception as exc:
                    pred_entry = "ERROR"
                    print(f"Prediction ThingSpeak upload failed: {exc}", file=sys.stderr)
                last_upload = now_mono

            print(
                f"{packet.timestamp.isoformat()} | EC+12h={ec12 if math.isfinite(ec12) else 'WAIT'} "
                f"| pH+12h={ph12 if math.isfinite(ph12) else 'WAIT'} "
                f"| ProdA advisory={proda if math.isfinite(proda) else 'OFF/WAIT'} "
                f"| hourly completeness={hourly_completeness if math.isfinite(hourly_completeness) else 0:.3f} "
                f"| raw={raw_entry} pred={pred_entry}",
                flush=True,
            )
            receiver.restart_receive()
            if args.max_packets is not None and accepted >= args.max_packets:
                break
    finally:
        receiver.close()

    print(f"Stopped after {accepted} accepted packets. Log: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
