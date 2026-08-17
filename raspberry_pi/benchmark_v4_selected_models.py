#!/usr/bin/env python3
"""
Raspberry Pi benchmark for the FINAL Paper 2 v4 selected models.

Final selected artifacts expected from paper2_outputs_v4_CEA/models:
    production_model.joblib  -> Extra Trees
    ec_12h_model.joblib      -> Histogram Gradient Boosting
    ph_12h_model.joblib      -> Ridge (alpha = 0.01)
    metadata.json

Benchmark protocol:
    - 50 warm-up predict() calls
    - 1,000 timed single-sample predict() calls
    - reports median, mean, 95th percentile and max latency
    - reports process RSS before/after each benchmark and RSS delta
    - reports peak Python allocation during inference (tracemalloc)
    - reports raw and CPU-count-normalized process CPU utilization
    - reports total process RSS after all three models/dependencies are loaded

Important:
    This benchmarks estimator/pipeline inference only. It intentionally excludes
    LoRa reception, packet decoding, feature-state maintenance, ThingSpeak upload,
    Power BI refresh, and command transmission, matching the manuscript boundary.
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

import joblib
import numpy as np
import pandas as pd
import sklearn

try:
    import psutil
except ImportError as exc:
    raise SystemExit(
        "psutil is required. Install it in the same Raspberry Pi environment with:\n"
        "    python -m pip install psutil\n"
    ) from exc


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

EXPECTED_MODELS = {
    "Production": "ExtraTreesRegressor",
    "EC": "HistGradientBoostingRegressor",
    "pH": "Ridge",
}


def estimator_class_name(pipeline) -> str:
    """Return the final estimator class name for a scikit-learn Pipeline/model."""
    if hasattr(pipeline, "named_steps") and "model" in pipeline.named_steps:
        return pipeline.named_steps["model"].__class__.__name__
    return pipeline.__class__.__name__


def load_metadata(model_dir: Path) -> dict:
    path = model_dir / "metadata.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing metadata file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_final_models(model_dir: Path):
    paths = {
        "Production": model_dir / "production_model.joblib",
        "EC": model_dir / "ec_12h_model.joblib",
        "pH": model_dir / "ph_12h_model.joblib",
    }

    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "The following final v4 model files are missing:\n  - "
            + "\n  - ".join(missing)
        )

    models = {name: joblib.load(path) for name, path in paths.items()}
    return models, paths


def validate_final_model_families(models: dict, metadata: dict) -> None:
    """Fail loudly if an old model artifact is accidentally benchmarked."""
    print("\n=== FINAL MODEL VERIFICATION ===")

    expected_metadata = {
        "production_model_family": "Extra Trees",
        "ec_model_family": "Histogram Gradient Boosting",
        "ph_model_family": "Ridge",
    }

    for key, expected in expected_metadata.items():
        actual = metadata.get(key, "<missing>")
        print(f"{key}: {actual}")
        if actual != expected:
            raise RuntimeError(
                f"Wrong metadata/model version: {key}={actual!r}, expected {expected!r}. "
                "Do not benchmark the previous v3 artifacts."
            )

    for name, model in models.items():
        actual_class = estimator_class_name(model)
        expected_class = EXPECTED_MODELS[name]
        print(f"{name}: {actual_class}")
        if actual_class != expected_class:
            raise RuntimeError(
                f"{name} artifact is {actual_class}, expected {expected_class}. "
                "Check that you copied the final v4 models."
            )

    # Final pH model should be Ridge alpha=0.01.
    ph_est = models["pH"].named_steps["model"] if hasattr(models["pH"], "named_steps") else models["pH"]
    if hasattr(ph_est, "alpha"):
        print(f"pH Ridge alpha: {ph_est.alpha}")
        if not np.isclose(float(ph_est.alpha), 0.01):
            raise RuntimeError(f"Unexpected pH Ridge alpha={ph_est.alpha}; expected 0.01")

    print("Model verification passed.\n")


def training_median_reference_row(model, feature_names: list[str]) -> pd.DataFrame:
    """
    Build a valid 1-row benchmark input from the fitted imputer's training medians.

    This keeps the standalone Pi benchmark independent of the AGC CSV files while
    preserving the exact expected feature schema and a representative in-distribution
    numeric input for inference timing.
    """
    values = None

    if hasattr(model, "named_steps") and "imputer" in model.named_steps:
        imputer = model.named_steps["imputer"]
        stats = getattr(imputer, "statistics_", None)
        if stats is not None and len(stats) == len(feature_names):
            values = np.asarray(stats, dtype=float)

    if values is None:
        # Safe timing fallback only; normally the fitted SimpleImputer path above is used.
        values = np.zeros(len(feature_names), dtype=float)

    values = np.where(np.isfinite(values), values, 0.0)
    return pd.DataFrame([values], columns=feature_names)


def benchmark_single_sample(
    model,
    X_row: pd.DataFrame,
    repeats: int = 1000,
    warmup: int = 50,
) -> dict:
    """Benchmark one frozen estimator/pipeline on one sample."""

    # Warm-up: exclude import/lazy-initialization effects from reported latency.
    for _ in range(warmup):
        model.predict(X_row)

    process = psutil.Process(os.getpid())
    logical_cpus = psutil.cpu_count(logical=True) or 1

    rss_before = process.memory_info().rss
    cpu_times_before = process.cpu_times()
    wall_before = time.perf_counter()

    tracemalloc.start()
    timings_ms = np.empty(repeats, dtype=float)

    for i in range(repeats):
        t0 = time.perf_counter_ns()
        model.predict(X_row)
        timings_ms[i] = (time.perf_counter_ns() - t0) / 1e6

    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    wall_after = time.perf_counter()
    cpu_times_after = process.cpu_times()
    rss_after = process.memory_info().rss

    wall_seconds = max(wall_after - wall_before, 1e-12)
    cpu_seconds = (
        (cpu_times_after.user - cpu_times_before.user)
        + (cpu_times_after.system - cpu_times_before.system)
    )

    # psutil-style raw process CPU may approach ~100% for one fully occupied core.
    raw_process_cpu_pct = 100.0 * cpu_seconds / wall_seconds
    normalized_cpu_pct = raw_process_cpu_pct / logical_cpus

    return {
        "repeats": int(repeats),
        "warmup": int(warmup),
        "median_ms": float(np.median(timings_ms)),
        "mean_ms": float(np.mean(timings_ms)),
        "p95_ms": float(np.percentile(timings_ms, 95)),
        "max_ms": float(np.max(timings_ms)),
        "rss_before_MB": float(rss_before / 1e6),
        "rss_after_MB": float(rss_after / 1e6),
        "rss_delta_MB": float((rss_after - rss_before) / 1e6),
        "python_peak_alloc_MB": float(peak_bytes / 1e6),
        "process_cpu_percent_raw": float(raw_process_cpu_pct),
        "normalized_cpu_percent": float(normalized_cpu_pct),
        "logical_cpu_count": int(logical_cpus),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark the final Paper 2 v4 models on Raspberry Pi 4."
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=REPO_ROOT / "models",
        help="Folder containing production_model.joblib, ec_12h_model.joblib, ph_12h_model.joblib, metadata.json",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=SCRIPT_DIR / "results",
        help="Folder for benchmark CSV/JSON outputs",
    )
    parser.add_argument("--repeats", type=int, default=1000)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument(
        "--allow-non-pi",
        action="store_true",
        help="Allow running on a non-Raspberry Pi host for debugging only.",
    )
    args = parser.parse_args()

    model_dir = args.model_dir.expanduser().resolve()
    results_dir = args.results_dir.expanduser().resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    process = psutil.Process(os.getpid())

    print("=== PLATFORM ===")
    print("Platform:", platform.platform())
    print("Machine :", platform.machine())
    print("Python  :", platform.python_version())
    print("CPU count (logical):", psutil.cpu_count(logical=True))
    print("Model directory:", model_dir)

    # Aarch64/ARM alone does not prove Raspberry Pi, so this is a warning rather than
    # a brittle /proc-only hard check unless the user did not explicitly allow non-Pi.
    pi_text = ""
    for candidate in [Path("/proc/device-tree/model"), Path("/sys/firmware/devicetree/base/model")]:
        try:
            if candidate.exists():
                pi_text = candidate.read_text(errors="ignore").strip("\x00\n ")
                break
        except Exception:
            pass

    if pi_text:
        print("Device  :", pi_text)
    elif not args.allow_non_pi:
        print(
            "WARNING: Raspberry Pi model string could not be read. "
            "Continue only if this is intentionally the target Raspberry Pi."
        )

    metadata = load_metadata(model_dir)
    models, model_paths = load_final_models(model_dir)
    validate_final_model_families(models, metadata)

    production_features = metadata.get("production_features")
    hourly_features = metadata.get("hourly_features")
    if not production_features or not hourly_features:
        raise RuntimeError(
            "metadata.json must contain production_features and hourly_features from notebook v4."
        )

    print("Production feature count:", len(production_features))
    print("Hourly feature count    :", len(hourly_features))

    # RSS after all final model artifacts + dependencies are loaded.
    total_loaded_rss_MB = process.memory_info().rss / 1e6
    print(f"\nProcess RSS with all final models/dependencies loaded: {total_loaded_rss_MB:.2f} MB")

    reference_rows = {
        "Production": training_median_reference_row(models["Production"], production_features),
        "EC": training_median_reference_row(models["EC"], hourly_features),
        "pH": training_median_reference_row(models["pH"], hourly_features),
    }

    rows = []
    print("\n=== BENCHMARK: 50 WARM-UPS + 1,000 SINGLE-SAMPLE CALLS BY DEFAULT ===")
    for artifact in ["Production", "EC", "pH"]:
        model = models[artifact]
        result = benchmark_single_sample(
            model,
            reference_rows[artifact],
            repeats=args.repeats,
            warmup=args.warmup,
        )
        row = {
            "artifact": artifact,
            "model_family": (
                metadata.get("production_model_family") if artifact == "Production"
                else metadata.get("ec_model_family") if artifact == "EC"
                else metadata.get("ph_model_family")
            ),
            "model_file": model_paths[artifact].name,
            "model_size_MB": model_paths[artifact].stat().st_size / 1e6,
            **result,
        }
        rows.append(row)

        print(
            f"{artifact:10s} | {row['model_family']:<28s} | "
            f"median={row['median_ms']:.2f} ms | "
            f"p95={row['p95_ms']:.2f} ms | "
            f"max={row['max_ms']:.2f} ms | "
            f"peak alloc={row['python_peak_alloc_MB']:.3f} MB | "
            f"norm CPU={row['normalized_cpu_percent']:.2f}%"
        )

    table = pd.DataFrame(rows)

    csv_path = results_dir / "raspberry_pi_benchmark_v4.csv"
    json_path = results_dir / "raspberry_pi_benchmark_v4.json"
    env_path = results_dir / "raspberry_pi_environment_v4.json"

    table.to_csv(csv_path, index=False)

    payload = {
        "benchmark_scope": "single-sample scikit-learn pipeline.predict() only",
        "total_process_rss_with_all_models_loaded_MB": float(total_loaded_rss_MB),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "device_model": pi_text or None,
        "python": platform.python_version(),
        "package_versions": {
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "psutil": psutil.__version__,
        },
        "metadata": {
            "production_model_family": metadata.get("production_model_family"),
            "ec_model_family": metadata.get("ec_model_family"),
            "ph_model_family": metadata.get("ph_model_family"),
            "production_feature_count": len(production_features),
            "hourly_feature_count": len(hourly_features),
            "forecast_horizon_hours": metadata.get("forecast_horizon_hours"),
        },
        "results": rows,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    env_payload = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "device_model": pi_text or None,
        "python": platform.python_version(),
        "package_versions": {
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "psutil": psutil.__version__,
        },
        "logical_cpu_count": psutil.cpu_count(logical=True),
        "physical_cpu_count": psutil.cpu_count(logical=False),
        "total_system_memory_MB": psutil.virtual_memory().total / 1e6,
        "process_rss_all_models_loaded_MB": float(total_loaded_rss_MB),
    }
    env_path.write_text(json.dumps(env_payload, indent=2), encoding="utf-8")

    print("\n=== OUTPUT FILES ===")
    print(csv_path)
    print(json_path)
    print(env_path)

    print("\n=== MANUSCRIPT-READY SUMMARY ===")
    for _, r in table.iterrows():
        print(
            f"{r['artifact']}: median {r['median_ms']:.2f} ms; "
            f"p95 {r['p95_ms']:.2f} ms; max {r['max_ms']:.2f} ms; "
            f"peak Python allocation {r['python_peak_alloc_MB']:.3f} MB."
        )
    print(f"All-model process RSS: {total_loaded_rss_MB:.2f} MB")

    return 0


if __name__ == "__main__":
    sys.exit(main())
