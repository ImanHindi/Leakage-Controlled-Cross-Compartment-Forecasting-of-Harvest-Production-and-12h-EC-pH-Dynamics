#!/usr/bin/env python3
"""
Replay one AGC-2 greenhouse team to TWO ThingSpeak channels.

Why two channels?
-----------------
ThingSpeak supports only eight ordinary fields per channel. The workflow has
seven raw model inputs plus two forecasts (EC and pH), so nine numeric values
cannot be represented as separate fields in one channel.

Channel A — raw greenhouse data
    field1 = Tair
    field2 = Rhair
    field3 = CO2air
    field4 = Tot_PAR
    field5 = EC_drain_PC
    field6 = pH_drain_PC
    field7 = Cum_irr

Channel B — measured versus predicted nutrient variables
    field1 = EC_measured
    field2 = EC_predicted_t12
    field3 = pH_measured
    field4 = pH_predicted_t12
    field5 = ForecastAgeMinutes

The status value on both channels stores:
    team=...;source_timestamp=...;forecast_timestamp=...

Example
-------
python stream_one_team_two_thingspeak_channels.py ^
  --data-dir ".\\agc2_data" ^
  --predictions-csv ".\\paper2_outputs_v3\\aicu_ec_ph_predictions.csv" ^
  --config ".\\thingspeak_two_channels.json" ^
  --start-at-first-prediction ^
  --interval 20 ^
  --max-cycles 10
"""

from __future__ import annotations

import argparse
import json
import re
import signal
import sys
import time
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
import requests


VALID_TEAMS = [
    "AICU",
    "TheAutomators",
    "Automatoes",
    "Digilog",
    "IUACAAS",
    "Reference",
]

TEAM_ALIASES = {
    "AICU": ["aicu", "ai_cu"],
    "TheAutomators": ["theautomators", "the_automators", "automators"],
    "Automatoes": ["automatoes"],
    "Digilog": ["digilog"],
    "IUACAAS": ["iuacaas", "iua_caas", "iua.caas"],
    "Reference": ["reference", "grower", "human"],
}

RAW_MODEL_INPUTS = {
    "field1": ["Tair", "air temperature"],
    "field2": ["Rhair", "relative humidity"],
    "field3": ["CO2air", "CO2 air", "carbon dioxide"],
    "field4": ["Tot_PAR", "total PAR"],
    "field5": ["EC_drain_PC", "drain EC", "EC drain"],
    "field6": ["pH_drain_PC", "drain pH", "pH drain"],
    "field7": ["Cum_irr", "cumulative irrigation"],
}

THINGSPEAK_UPDATE_URL = "https://api.thingspeak.com/update.json"
_STOP = False


def stop_handler(signum: int, frame: Any) -> None:
    global _STOP
    _STOP = True
    print("\nStop requested; finishing the current upload cycle.", flush=True)


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def find_team_file(data_dir: Path, team: str, filename: str) -> Path:
    candidates = list(data_dir.rglob(filename))
    aliases = [normalize(alias) for alias in TEAM_ALIASES[team]]
    ranked: list[tuple[int, Path]] = []

    for path in candidates:
        parent_text = normalize(path.parent)
        score = max((len(alias) if alias in parent_text else 0) for alias in aliases)
        if score:
            ranked.append((score, path))

    if not ranked:
        raise FileNotFoundError(
            f"Could not locate {filename} for {team} below {data_dir.resolve()}."
        )

    ranked.sort(key=lambda item: (-item[0], len(str(item[1]))))
    return ranked[0][1]


def find_column(df: pd.DataFrame, candidates: list[str]) -> str:
    normalized_columns = {normalize(column): column for column in df.columns}

    for candidate in candidates:
        key = normalize(candidate)
        if key in normalized_columns:
            return normalized_columns[key]

    for column in df.columns:
        column_key = normalize(column)
        for candidate in candidates:
            candidate_key = normalize(candidate)
            if candidate_key in column_key or column_key in candidate_key:
                return column

    raise KeyError(
        f"Could not find any of {candidates}. Available columns: {df.columns.tolist()}"
    )


def detect_timestamp_column(df: pd.DataFrame) -> str:
    for candidates in [["timestamp"], ["datetime", "date time"], ["time"], ["date"]]:
        try:
            return find_column(df, candidates)
        except KeyError:
            continue
    return df.columns[0]


def _force_datetime_ns(series: pd.Series) -> pd.Series:
    converted = pd.to_datetime(series, errors="coerce")
    try:
        converted = converted.dt.as_unit("ns")
    except (AttributeError, TypeError, ValueError):
        converted = converted.astype("datetime64[ns]")
    return converted


def parse_timestamp(series: pd.Series) -> pd.Series:
    stripped = series.astype(str).str.strip()

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Could not infer format.*",
            category=UserWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message="Parsing dates.*dayfirst=True.*",
            category=UserWarning,
        )
        options: list[pd.Series] = [
            pd.to_datetime(stripped, errors="coerce", dayfirst=False),
            pd.to_datetime(stripped, errors="coerce", dayfirst=True),
        ]

    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().any():
        options.extend(
            [
                pd.to_datetime(
                    numeric, unit="D", origin="1899-12-30", errors="coerce"
                ),
                pd.to_datetime(numeric, unit="s", origin="unix", errors="coerce"),
                pd.to_datetime(numeric, unit="ms", origin="unix", errors="coerce"),
            ]
        )

    def score(parsed: pd.Series) -> tuple[int, int]:
        parsed = _force_datetime_ns(parsed)
        plausible = parsed.dt.year.between(2019, 2021)
        return int(plausible.sum()), int(parsed.notna().sum())

    return _force_datetime_ns(max(options, key=score))


def load_climate(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, low_memory=False)
    timestamp_column = detect_timestamp_column(raw)
    output = pd.DataFrame(
        {"source_timestamp": parse_timestamp(raw[timestamp_column])}
    )

    for field, candidates in RAW_MODEL_INPUTS.items():
        source_column = find_column(raw, candidates)
        output[field] = pd.to_numeric(raw[source_column], errors="coerce")

    output = (
        output.dropna(subset=["source_timestamp"])
        .sort_values("source_timestamp")
        .drop_duplicates(subset=["source_timestamp"], keep="first")
        .reset_index(drop=True)
    )
    if output.empty:
        raise ValueError(f"No valid climate records were loaded from {path}.")
    return output


def load_predictions(path: Path) -> pd.DataFrame:
    predictions = pd.read_csv(path, low_memory=False)

    timestamp_column = find_column(
        predictions, ["timestamp", "forecast timestamp", "source timestamp"]
    )
    ec_column = find_column(
        predictions, ["EC_predicted_t12", "predicted EC", "EC prediction"]
    )
    ph_column = find_column(
        predictions, ["pH_predicted_t12", "predicted pH", "pH prediction"]
    )

    output = pd.DataFrame(
        {
            "forecast_timestamp": parse_timestamp(predictions[timestamp_column]),
            "EC_predicted_t12": pd.to_numeric(
                predictions[ec_column], errors="coerce"
            ),
            "pH_predicted_t12": pd.to_numeric(
                predictions[ph_column], errors="coerce"
            ),
        }
    )

    output = (
        output.dropna(
            subset=[
                "forecast_timestamp",
                "EC_predicted_t12",
                "pH_predicted_t12",
            ]
        )
        .sort_values("forecast_timestamp")
        .drop_duplicates(subset=["forecast_timestamp"], keep="last")
        .reset_index(drop=True)
    )

    if output.empty:
        raise ValueError(f"No valid predictions were loaded from {path}.")
    return output


def attach_latest_prediction(
    climate: pd.DataFrame,
    predictions: pd.DataFrame,
    tolerance_minutes: int,
) -> pd.DataFrame:
    left = climate.copy()
    right = predictions.copy()

    left["source_timestamp"] = _force_datetime_ns(left["source_timestamp"])
    right["forecast_timestamp"] = _force_datetime_ns(
        right["forecast_timestamp"]
    )

    left = left.dropna(subset=["source_timestamp"]).sort_values(
        "source_timestamp"
    )
    right = right.dropna(subset=["forecast_timestamp"]).sort_values(
        "forecast_timestamp"
    )

    merged = pd.merge_asof(
        left,
        right,
        left_on="source_timestamp",
        right_on="forecast_timestamp",
        direction="backward",
        tolerance=pd.Timedelta(minutes=tolerance_minutes),
        allow_exact_matches=True,
    ).reset_index(drop=True)

    merged["forecast_age_minutes"] = (
        merged["source_timestamp"] - merged["forecast_timestamp"]
    ).dt.total_seconds() / 60.0

    return merged


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))

    required = [
        "team",
        "data_channel_write_api_key",
        "prediction_channel_write_api_key",
    ]
    missing = [name for name in required if not str(config.get(name, "")).strip()]
    if missing:
        raise ValueError("Missing configuration values: " + ", ".join(missing))

    if config["team"] not in VALID_TEAMS:
        raise ValueError(
            f"Invalid team '{config['team']}'. Choose one of {VALID_TEAMS}."
        )

    tolerance = int(config.get("prediction_tolerance_minutes", 65))
    if tolerance <= 0:
        raise ValueError("prediction_tolerance_minutes must be positive.")

    config["prediction_tolerance_minutes"] = tolerance
    return config


def clean_number(value: Any) -> str | None:
    if pd.isna(value):
        return None
    return f"{float(value):.10g}"


def compact_timestamp(value: Any) -> str:
    if pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime("%Y-%m-%dT%H:%M:%S")


def build_status(row: pd.Series, team: str) -> str:
    parts = [
        f"team={team}",
        f"source_timestamp={compact_timestamp(row['source_timestamp'])}",
    ]
    if pd.notna(row.get("forecast_timestamp")):
        parts.append(
            f"forecast_timestamp={compact_timestamp(row['forecast_timestamp'])}"
        )
    return ";".join(parts)


def post_payload(
    session: requests.Session,
    payload: dict[str, str],
    timeout: float,
) -> int:
    response = session.post(
        THINGSPEAK_UPDATE_URL,
        data=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    result = response.json()
    entry_id = int(result.get("entry_id", 0))
    if entry_id <= 0:
        raise RuntimeError(f"ThingSpeak returned an invalid response: {result}")
    return entry_id


def upload_raw_channel(
    session: requests.Session,
    row: pd.Series,
    team: str,
    write_api_key: str,
    timeout: float,
) -> int:
    payload: dict[str, str] = {
        "api_key": write_api_key,
        "status": build_status(row, team),
    }
    for field in RAW_MODEL_INPUTS:
        value = clean_number(row.get(field))
        if value is not None:
            payload[field] = value
    return post_payload(session, payload, timeout)


def upload_prediction_channel(
    session: requests.Session,
    row: pd.Series,
    team: str,
    write_api_key: str,
    timeout: float,
) -> int:
    mapping = {
        "field1": row.get("field5"),                  # measured EC
        "field2": row.get("EC_predicted_t12"),       # predicted EC
        "field3": row.get("field6"),                  # measured pH
        "field4": row.get("pH_predicted_t12"),       # predicted pH
        "field5": row.get("forecast_age_minutes"),   # forecast age
    }

    payload: dict[str, str] = {
        "api_key": write_api_key,
        "status": build_status(row, team),
    }
    for field, raw_value in mapping.items():
        value = clean_number(raw_value)
        if value is not None:
            payload[field] = value

    return post_payload(session, payload, timeout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--predictions-csv", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=20.0)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--start-at-first-prediction", action="store_true")
    parser.add_argument("--max-cycles", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    if args.interval < 15:
        raise ValueError(
            "--interval should be at least 15 seconds for ordinary ThingSpeak channels."
        )

    config = load_config(args.config)
    team = config["team"]

    climate_path = find_team_file(args.data_dir, team, "GreenhouseClimate.csv")
    climate = load_climate(climate_path)
    predictions = load_predictions(args.predictions_csv)
    replay = attach_latest_prediction(
        climate,
        predictions,
        config["prediction_tolerance_minutes"],
    )

    prediction_mask = (
        replay["EC_predicted_t12"].notna()
        & replay["pH_predicted_t12"].notna()
    )
    matched_count = int(prediction_mask.sum())
    if matched_count == 0:
        raise ValueError(
            "No climate rows matched the prediction timestamps. Check team, "
            "prediction file, and date ranges."
        )

    first_prediction_index = int(prediction_mask[prediction_mask].index[0])
    if args.start_at_first_prediction:
        args.start_index = first_prediction_index

    if args.start_index < 0 or args.start_index >= len(replay):
        raise ValueError(
            f"--start-index must be between 0 and {len(replay) - 1}."
        )

    print(f"Team: {team}")
    print(f"Climate file: {climate_path}")
    print(f"Prediction file: {args.predictions_csv}")
    print(f"Rows with both forecasts: {matched_count:,}")
    print(f"First forecast row: {first_prediction_index:,}")
    print(f"Starting row: {args.start_index:,}")
    print("\nRaw-data channel mapping:")
    print("  field1 = Tair")
    print("  field2 = Rhair")
    print("  field3 = CO2air")
    print("  field4 = Tot_PAR")
    print("  field5 = EC_drain_PC")
    print("  field6 = pH_drain_PC")
    print("  field7 = Cum_irr")
    print("\nPrediction channel mapping:")
    print("  field1 = EC_measured")
    print("  field2 = EC_predicted_t12")
    print("  field3 = pH_measured")
    print("  field4 = pH_predicted_t12")
    print("  field5 = ForecastAgeMinutes")

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    session = requests.Session()
    row_index = args.start_index
    cycles = 0

    while not _STOP and row_index < len(replay):
        cycle_start = time.monotonic()
        row = replay.iloc[row_index]

        raw_entry: str | int = "ERROR"
        prediction_entry: str | int = "ERROR"

        try:
            raw_entry = upload_raw_channel(
                session,
                row,
                team,
                config["data_channel_write_api_key"],
                args.timeout,
            )
        except Exception as exc:
            print(
                f"Raw-channel upload error at row {row_index}: {exc}",
                file=sys.stderr,
                flush=True,
            )

        try:
            prediction_entry = upload_prediction_channel(
                session,
                row,
                team,
                config["prediction_channel_write_api_key"],
                args.timeout,
            )
        except Exception as exc:
            print(
                f"Prediction-channel upload error at row {row_index}: {exc}",
                file=sys.stderr,
                flush=True,
            )

        print(
            f"{row_index:,} | source={row['source_timestamp']} "
            f"| EC measured={clean_number(row.get('field5')) or 'NA'} "
            f"| EC+12h={clean_number(row.get('EC_predicted_t12')) or 'NA'} "
            f"| pH measured={clean_number(row.get('field6')) or 'NA'} "
            f"| pH+12h={clean_number(row.get('pH_predicted_t12')) or 'NA'} "
            f"| raw entry={raw_entry} | prediction entry={prediction_entry}",
            flush=True,
        )

        row_index += 1
        cycles += 1
        if args.max_cycles is not None and cycles >= args.max_cycles:
            break

        elapsed = time.monotonic() - cycle_start
        time.sleep(max(0.0, args.interval - elapsed))

    print("Replay completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
