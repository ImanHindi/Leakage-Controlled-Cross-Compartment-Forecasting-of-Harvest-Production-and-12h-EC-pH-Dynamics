#!/usr/bin/env python3
"""
Standalone Raspberry Pi prediction and benchmarking utility for Paper 2.

The script loads the model artifacts exported by:
    Paper_2_Enhanced_AGC2_Reproducible_Analysis_CORRECTED_v3.ipynb

Expected model directory contents:
    production_model.joblib
    ec_12h_model.joblib
    ph_12h_model.joblib
    metadata.json

Main uses
---------
1. Benchmark the three exported models on the Raspberry Pi.
2. Run a production-indicator prediction from one CSV row.
3. Run 12-hour EC and pH forecasts from one hourly-feature CSV row.
4. Generate input CSV templates containing the exact feature names.

Examples
--------
Benchmark using synthetic feature rows:
    python prediction_script.py --benchmark

Benchmark using real feature rows:
    python prediction_script.py --benchmark \
        --production-csv production_input.csv \
        --hourly-csv hourly_input.csv

Run predictions:
    python prediction_script.py \
        --production-csv production_input.csv \
        --hourly-csv hourly_input.csv

Create input templates:
    python prediction_script.py --write-templates
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

try:
    import psutil
except ImportError:
    psutil = None


MODEL_FILENAMES = {
    "Production": "production_model.joblib",
    "EC": "ec_12h_model.joblib",
    "pH": "ph_12h_model.joblib",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Paper 2 predictions and Raspberry Pi benchmarks."
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("paper2_outputs_v3/models"),
        help=(
            "Directory containing the three .joblib files and metadata.json. "
            "Default: paper2_outputs_v3/models"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("raspberry_pi_results"),
        help="Directory for benchmark and prediction outputs.",
    )
    parser.add_argument(
        "--production-csv",
        type=Path,
        help="CSV containing production-model features. The selected row is used.",
    )
    parser.add_argument(
        "--hourly-csv",
        type=Path,
        help=(
            "CSV containing hourly model features and, for absolute forecasts, "
            "EC_current and pH_current."
        ),
    )
    parser.add_argument(
        "--row-index",
        type=int,
        default=0,
        help="Zero-based row index to read from input CSV files. Default: 0",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Benchmark all loaded models.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1000,
        help="Number of timed predictions per model. Default: 1000",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=50,
        help="Number of untimed warm-up predictions. Default: 50",
    )
    parser.add_argument(
        "--expected-device",
        default="Raspberry Pi",
        help='Expected device name. Default: "Raspberry Pi"',
    )
    parser.add_argument(
        "--write-templates",
        action="store_true",
        help="Create production_input_template.csv and hourly_input_template.csv.",
    )
    return parser.parse_args()


def read_text_if_exists(path: Path) -> str:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8", errors="ignore").strip("\x00\n ")
    except OSError:
        pass
    return ""


def detect_device() -> dict[str, Any]:
    device_tree_model = read_text_if_exists(Path("/proc/device-tree/model"))
    cpuinfo = read_text_if_exists(Path("/proc/cpuinfo"))

    combined = f"{device_tree_model}\n{cpuinfo}\n{platform.platform()}".lower()
    is_raspberry_pi = "raspberry pi" in combined

    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "device_model": device_tree_model or "Unavailable",
        "is_raspberry_pi": is_raspberry_pi,
        "logical_cpu_count": os.cpu_count(),
    }


def require_file(path: Path, description: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{description} not found: {path.resolve()}")


def load_artifacts(model_dir: Path):
    metadata_path = model_dir / "metadata.json"
    require_file(metadata_path, "Metadata file")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    models = {}
    for label, filename in MODEL_FILENAMES.items():
        model_path = model_dir / filename
        require_file(model_path, f"{label} model")
        try:
            models[label] = joblib.load(model_path)
        except Exception as exc:
            raise RuntimeError(
                f"Could not load {label} model from {model_path}. "
                "The Raspberry Pi should preferably use the same scikit-learn "
                "version that created the artifact."
            ) from exc

    production_features = metadata.get("production_features")
    hourly_features = metadata.get("hourly_features")

    if not isinstance(production_features, list) or not production_features:
        raise ValueError("metadata.json does not contain a valid production_features list.")
    if not isinstance(hourly_features, list) or not hourly_features:
        raise ValueError("metadata.json does not contain a valid hourly_features list.")

    return models, metadata, production_features, hourly_features


def load_selected_row(
    csv_path: Path,
    required_features: list[str],
    row_index: int,
    label: str,
) -> tuple[pd.DataFrame, pd.Series]:
    require_file(csv_path, f"{label} input CSV")
    frame = pd.read_csv(csv_path)

    if frame.empty:
        raise ValueError(f"{label} input CSV is empty: {csv_path}")
    if row_index < 0 or row_index >= len(frame):
        raise IndexError(
            f"{label} row index {row_index} is outside the available range "
            f"0 to {len(frame) - 1}."
        )

    missing = [name for name in required_features if name not in frame.columns]
    if missing:
        preview = ", ".join(missing[:12])
        suffix = " ..." if len(missing) > 12 else ""
        raise ValueError(
            f"{label} input is missing {len(missing)} required feature(s): "
            f"{preview}{suffix}"
        )

    selected = frame.iloc[row_index]
    X_row = frame.loc[[frame.index[row_index]], required_features].copy()

    # Convert all model features to numeric. Non-numeric values become NaN and
    # can be handled by the imputer stored inside the exported sklearn pipeline.
    for column in required_features:
        X_row[column] = pd.to_numeric(X_row[column], errors="coerce")

    return X_row, selected


def synthetic_row(features: list[str]) -> pd.DataFrame:
    """
    Construct a valid one-row DataFrame for timing only.

    A zero-valued row is suitable for measuring software execution time but
    must never be interpreted as a meaningful greenhouse prediction.
    """
    return pd.DataFrame([{name: 0.0 for name in features}], columns=features)


def write_templates(
    output_dir: Path,
    production_features: list[str],
    hourly_features: list[str],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    production_template = pd.DataFrame(
        [{name: np.nan for name in production_features}],
        columns=production_features,
    )
    hourly_columns = hourly_features + ["EC_current", "pH_current"]
    hourly_template = pd.DataFrame(
        [{name: np.nan for name in hourly_columns}],
        columns=hourly_columns,
    )

    production_path = output_dir / "production_input_template.csv"
    hourly_path = output_dir / "hourly_input_template.csv"

    production_template.to_csv(production_path, index=False)
    hourly_template.to_csv(hourly_path, index=False)

    print(f"Created: {production_path.resolve()}")
    print(f"Created: {hourly_path.resolve()}")
    print(
        "Fill the templates with one or more real feature rows before using "
        "them for agronomic predictions."
    )


def benchmark_single_sample(
    model,
    X_row: pd.DataFrame,
    repeats: int = 1000,
    warmup: int = 50,
) -> dict[str, Any]:
    if repeats < 1:
        raise ValueError("repeats must be at least 1.")
    if warmup < 0:
        raise ValueError("warmup cannot be negative.")

    for _ in range(warmup):
        model.predict(X_row)

    process = psutil.Process(os.getpid()) if psutil else None
    rss_before = process.memory_info().rss if process else np.nan

    if process:
        cpu_before = process.cpu_times()
        cpu_seconds_before = cpu_before.user + cpu_before.system
    else:
        cpu_seconds_before = np.nan

    tracemalloc.start()
    timings_ms: list[float] = []
    wall_start = time.perf_counter()

    for _ in range(repeats):
        t0 = time.perf_counter_ns()
        model.predict(X_row)
        timings_ms.append((time.perf_counter_ns() - t0) / 1e6)

    wall_elapsed = time.perf_counter() - wall_start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    if process:
        rss_after = process.memory_info().rss
        cpu_after = process.cpu_times()
        cpu_seconds_after = cpu_after.user + cpu_after.system
        cpu_seconds_used = cpu_seconds_after - cpu_seconds_before
        process_cpu_percent = (
            100.0 * cpu_seconds_used / wall_elapsed if wall_elapsed > 0 else np.nan
        )
        cpu_count = psutil.cpu_count(logical=True) or 1
        normalized_cpu_percent = process_cpu_percent / cpu_count
    else:
        rss_after = np.nan
        process_cpu_percent = np.nan
        normalized_cpu_percent = np.nan

    device = detect_device()

    return {
        **device,
        "repeats": repeats,
        "warmup": warmup,
        "median_ms": float(np.median(timings_ms)),
        "mean_ms": float(np.mean(timings_ms)),
        "p95_ms": float(np.percentile(timings_ms, 95)),
        "max_ms": float(np.max(timings_ms)),
        "total_wall_seconds": float(wall_elapsed),
        "rss_before_MB": (
            float(rss_before / 1e6) if np.isfinite(rss_before) else np.nan
        ),
        "rss_after_MB": (
            float(rss_after / 1e6) if np.isfinite(rss_after) else np.nan
        ),
        "rss_change_MB": (
            float((rss_after - rss_before) / 1e6)
            if np.isfinite(rss_before) and np.isfinite(rss_after)
            else np.nan
        ),
        "python_peak_alloc_MB": float(peak / 1e6),
        "process_cpu_percent_of_one_core": (
            float(process_cpu_percent)
            if np.isfinite(process_cpu_percent)
            else np.nan
        ),
        "process_cpu_percent_normalized": (
            float(normalized_cpu_percent)
            if np.isfinite(normalized_cpu_percent)
            else np.nan
        ),
    }


def run_predictions(
    models: dict[str, Any],
    production_row: pd.DataFrame | None,
    hourly_row: pd.DataFrame | None,
    hourly_source_row: pd.Series | None,
) -> dict[str, Any]:
    results: dict[str, Any] = {}

    if production_row is not None:
        prod_value = float(models["Production"].predict(production_row)[0])
        results["production_indicator_prediction"] = prod_value

    if hourly_row is not None:
        ec_delta = float(models["EC"].predict(hourly_row)[0])
        ph_delta = float(models["pH"].predict(hourly_row)[0])

        results["predicted_EC_change_12h"] = ec_delta
        results["predicted_pH_change_12h"] = ph_delta

        if hourly_source_row is not None and "EC_current" in hourly_source_row.index:
            current_ec = pd.to_numeric(
                pd.Series([hourly_source_row["EC_current"]]), errors="coerce"
            ).iloc[0]
            if pd.notna(current_ec):
                results["EC_current"] = float(current_ec)
                results["predicted_EC_at_t_plus_12h"] = float(current_ec + ec_delta)

        if hourly_source_row is not None and "pH_current" in hourly_source_row.index:
            current_ph = pd.to_numeric(
                pd.Series([hourly_source_row["pH_current"]]), errors="coerce"
            ).iloc[0]
            if pd.notna(current_ph):
                results["pH_current"] = float(current_ph)
                results["predicted_pH_at_t_plus_12h"] = float(current_ph + ph_delta)

    return results


def main() -> int:
    args = parse_args()

    try:
        models, metadata, production_features, hourly_features = load_artifacts(
            args.model_dir
        )

        args.output_dir.mkdir(parents=True, exist_ok=True)

        if args.write_templates:
            write_templates(
                args.output_dir,
                production_features,
                hourly_features,
            )

        production_row = None
        production_source = None
        if args.production_csv:
            production_row, production_source = load_selected_row(
                args.production_csv,
                production_features,
                args.row_index,
                "Production",
            )

        hourly_row = None
        hourly_source = None
        if args.hourly_csv:
            hourly_row, hourly_source = load_selected_row(
                args.hourly_csv,
                hourly_features,
                args.row_index,
                "Hourly",
            )

        # Run predictions when real input rows are provided.
        if production_row is not None or hourly_row is not None:
            predictions = run_predictions(
                models,
                production_row,
                hourly_row,
                hourly_source,
            )
            prediction_path = args.output_dir / "prediction_results.json"
            prediction_path.write_text(
                json.dumps(predictions, indent=2),
                encoding="utf-8",
            )
            print("\nPrediction results")
            print(json.dumps(predictions, indent=2))
            print(f"Saved: {prediction_path.resolve()}")

        if args.benchmark:
            used_synthetic = False

            prod_benchmark_row = production_row
            if prod_benchmark_row is None:
                prod_benchmark_row = synthetic_row(production_features)
                used_synthetic = True

            hourly_benchmark_row = hourly_row
            if hourly_benchmark_row is None:
                hourly_benchmark_row = synthetic_row(hourly_features)
                used_synthetic = True

            if used_synthetic:
                print(
                    "\nWARNING: at least one benchmark uses a synthetic zero-valued "
                    "feature row. This is acceptable for timing, but the resulting "
                    "prediction values are not agronomically meaningful."
                )

            benchmark_rows = [
                {
                    "artifact": "Production",
                    "model_family": metadata.get("production_model_family", "Unknown"),
                    "model_file": MODEL_FILENAMES["Production"],
                    **benchmark_single_sample(
                        models["Production"],
                        prod_benchmark_row,
                        repeats=args.repeats,
                        warmup=args.warmup,
                    ),
                },
                {
                    "artifact": "EC",
                    "model_family": metadata.get("ec_model_family", "Unknown"),
                    "model_file": MODEL_FILENAMES["EC"],
                    **benchmark_single_sample(
                        models["EC"],
                        hourly_benchmark_row,
                        repeats=args.repeats,
                        warmup=args.warmup,
                    ),
                },
                {
                    "artifact": "pH",
                    "model_family": metadata.get("ph_model_family", "Unknown"),
                    "model_file": MODEL_FILENAMES["pH"],
                    **benchmark_single_sample(
                        models["pH"],
                        hourly_benchmark_row,
                        repeats=args.repeats,
                        warmup=args.warmup,
                    ),
                },
            ]

            benchmark_table = pd.DataFrame(benchmark_rows)
            benchmark_csv = args.output_dir / "raspberry_pi_benchmark.csv"
            benchmark_json = args.output_dir / "raspberry_pi_benchmark.json"
            benchmark_table.to_csv(benchmark_csv, index=False)
            benchmark_json.write_text(
                json.dumps(benchmark_rows, indent=2, default=str),
                encoding="utf-8",
            )

            display_columns = [
                "artifact",
                "model_family",
                "median_ms",
                "mean_ms",
                "p95_ms",
                "max_ms",
                "rss_after_MB",
                "python_peak_alloc_MB",
                "process_cpu_percent_normalized",
            ]
            print("\nBenchmark results")
            print(benchmark_table[display_columns].to_string(index=False))
            print(f"\nSaved: {benchmark_csv.resolve()}")
            print(f"Saved: {benchmark_json.resolve()}")

            actual_device = detect_device()
            expected_is_raspberry = args.expected_device.lower().startswith("raspberry")
            if expected_is_raspberry and not actual_device["is_raspberry_pi"]:
                print(
                    "\nWARNING: the operating system information does not identify "
                    "this machine as a Raspberry Pi. Do not report these values as "
                    "Raspberry Pi target-device performance."
                )

        if (
            not args.benchmark
            and not args.write_templates
            and production_row is None
            and hourly_row is None
        ):
            print(
                "No action requested. Use --benchmark, --write-templates, "
                "--production-csv, or --hourly-csv."
            )
            return 2

        return 0

    except (FileNotFoundError, ValueError, IndexError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
