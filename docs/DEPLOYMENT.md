# Execution and deployment

## Local

Install from `pyproject.toml` in a virtual environment, then run `python -m streamlit run app.py`. The packaged processed measurements and saved reports support a complete dashboard without network access. To regenerate original features, run `rigplan ingest`; ingestion downloads the source ZIP only if it is absent.

Start `scripts/start.ps1` from PowerShell after installation. The server binds to loopback. The dashboard has no authentication and is intended for local portfolio demonstrations. It reads local artifacts; it does not connect to physical equipment.

## Docker

```sh
docker build -t rigplan .
docker run --rm -p 127.0.0.1:8501:8501 rigplan
```

The image uses shipped processed data and reports. Docker execution was not available/verified here. Regeneration inside a container requires network access and writable storage.

## Azure Databricks

Supplied assets have not been deployed or validated in Azure. They demonstrate an intended integration path, not production readiness. They do not contain credentials.

1. Install and authenticate the Databricks CLI using your organisation's approved profile.
2. Create a Unity Catalog schema and Volume, e.g. `/Volumes/main/rigplan/artifacts`. Use a dedicated development namespace: the notebook overwrites only its named demo tables.
3. Choose a compatible Unity Catalog cluster with Python 3.11+, SciPy MILP and sufficient driver memory. The dependency list includes Streamlit for the local application, though the notebook does not launch it.
4. If outbound UCI downloads are blocked, copy the original ZIP to `<volume_root>/data/raw/hydraulic.zip` before running.
5. Run the bundle commands from the repository root, supplying your own values:

```sh
databricks bundle validate --var="cluster_id=YOUR_CLUSTER_ID,volume_root=/Volumes/main/rigplan/artifacts,catalog=main,schema=rigplan"
databricks bundle deploy --var="cluster_id=YOUR_CLUSTER_ID,volume_root=/Volumes/main/rigplan/artifacts,catalog=main,schema=rigplan"
databricks bundle run rigplan_benchmark --var="cluster_id=YOUR_CLUSTER_ID,volume_root=/Volumes/main/rigplan/artifacts,catalog=main,schema=rigplan"
```

These are instructions for the user's authorised workspace; no cloud commands were executed in this project. Confirm the installed CLI's bundle validation output and runtime compatibility before deployment.

Raw ZIP and derived Parquet files remain in the Volume. Delta tables include bronze parsed cycles with hash lineage, silver stable cycles, and gold selection, requirement and partition tables plus a JSON benchmark summary. Bronze stores parsed per-cycle summaries; the immutable source artifact is the ZIP in the Volume. Full raw waveform tables are not materialised in Delta.

The small-data optimiser runs on the driver. The presence of Spark/Delta does not establish a large-scale benchmark. A real facility integration should ingest partitioned sensor records, maintain schema evolution and calibration metadata, retain unstable observations for a separate analysis, define permissions and lifecycle rules, and write versioned plans rather than overwrite production evidence.

## Data contract and audit

`cycles.parquet` includes a unique `cycle_id`, four validated categorical factors, `condition_id`, contiguous `run_id`, `unstable` in {0,1}, and mean/std features for 17 channels. Cycle IDs preserve source row order; no timestamps are fabricated. The current source has no missing values. Invalid inputs fail rather than silently impute or generate replacement data.

`provenance.json` records the downloaded archive's SHA-256, DOI, license and transformation. The digest fingerprints this exact archive; it is not a publisher-supplied authenticity signature. `split_manifest.csv` lists every cycle's training, holdout or excluded partition. Requirement traces identify evidence rows; held-out predictions allow independent error recomputation. Test the measured artifact integrity with `pytest` after regeneration.
