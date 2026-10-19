"""UCI ingestion. No fabricated observations or silent synthetic fallback."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

import numpy as np
import pandas as pd

URL = "https://archive.ics.uci.edu/static/public/447/condition+monitoring+of+hydraulic+systems.zip"
FACTORS = ["cooler", "valve", "pump", "accumulator"]
LEVELS = {"cooler": [3, 20, 100], "valve": [73, 80, 90, 100], "pump": [0, 1, 2], "accumulator": [90, 100, 115, 130]}
SENSORS = {"PS1": "bar", "PS2": "bar", "PS3": "bar", "PS4": "bar", "PS5": "bar", "PS6": "bar", "EPS1": "W", "FS1": "L/min", "FS2": "L/min", "TS1": "degC", "TS2": "degC", "TS3": "degC", "TS4": "degC", "VS1": "mm/s", "CE": "%", "CP": "kW", "SE": "%"}
OUTCOMES = ["PS1_mean", "FS1_mean", "TS1_mean", "VS1_mean", "EPS1_mean"]


def ingest(root: Path) -> pd.DataFrame:
    raw = root / "data/raw/hydraulic.zip"
    raw.parent.mkdir(parents=True, exist_ok=True)
    if not raw.exists():
        partial = raw.with_suffix(".part")
        print("Downloading measured UCI hydraulic rig data...", flush=True)
        urllib.request.urlretrieve(URL, partial)
        partial.replace(raw)
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()
    with zipfile.ZipFile(raw) as archive:
        with archive.open("profile.txt") as handle:
            profile = np.loadtxt(handle, dtype=int)
        if profile.shape != (2205, 5):
            raise ValueError(f"Unexpected UCI profile shape: {profile.shape}")
        frame = pd.DataFrame(profile, columns=FACTORS + ["unstable"])
        for sensor in SENSORS:
            print(f"Extracting {sensor} statistics", flush=True)
            with archive.open(f"{sensor}.txt") as handle:
                values = np.loadtxt(handle, dtype=np.float64)
            if len(values) != len(frame) or not np.isfinite(values).all():
                raise ValueError(f"Invalid measurements: {sensor}")
            frame[f"{sensor}_mean"] = values.mean(axis=1)
            frame[f"{sensor}_std"] = values.std(axis=1)
    frame.insert(0, "cycle_id", np.arange(1, len(frame) + 1))
    frame["condition_id"] = frame[FACTORS].astype(str).agg("_".join, axis=1)
    # A run is a contiguous block with unchanged settings, not a real timestamp.
    frame["run_id"] = frame["condition_id"].ne(frame["condition_id"].shift()).cumsum()
    validate(frame)
    dest = root / "data/processed"
    dest.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(dest / "cycles.parquet", index=False)
    provenance = {"url": URL, "doi": "10.24432/C5CW21", "license": "CC BY 4.0", "authors": "Helwig, Pignanelli and Schuetze (2015)", "archive_sha256": digest, "rows": len(frame), "stable_rows": int(frame.unstable.eq(0).sum()), "features": 34, "cycle_seconds": 60, "transform": "Per-cycle mean and population standard deviation; all 17 channels. No imputation."}
    (dest / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return frame


def validate(frame: pd.DataFrame) -> None:
    needed = ["cycle_id", "condition_id", "run_id", "unstable"] + FACTORS + OUTCOMES
    missing = set(needed) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    if frame.empty or frame[needed].isna().any().any():
        raise ValueError("Empty data or missing values")
    if frame.cycle_id.duplicated().any():
        raise ValueError("Cycle IDs must be unique")
    expected_ids = frame[FACTORS].astype(str).agg("_".join, axis=1)
    if not frame.condition_id.eq(expected_ids).all():
        raise ValueError("Condition IDs do not match the factor settings")
    for factor, levels in LEVELS.items():
        if not frame[factor].isin(levels).all():
            raise ValueError(f"Unknown {factor} level")
    if not frame.unstable.isin([0, 1]).all():
        raise ValueError("Unknown stability flag")
    if not np.isfinite(frame[OUTCOMES].to_numpy()).all():
        raise ValueError("Nonfinite response")
