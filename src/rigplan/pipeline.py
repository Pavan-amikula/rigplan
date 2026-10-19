"""Reproducible, group-held-out retrospective benchmark and audit exports."""
from __future__ import annotations

import json
from pathlib import Path
import platform
import importlib.metadata
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupShuffleSplit

from rigplan.data import FACTORS, OUTCOMES, ingest, validate
from rigplan.design import design_matrix, missing_pairs, plan, representative_cycles, requirements
from rigplan.schedule import sequence


def split_data(frame: pd.DataFrame, seed: int = 42):
    stable = frame.loc[frame.unstable.eq(0)].copy()
    a, b = next(GroupShuffleSplit(n_splits=1, test_size=.25, random_state=seed).split(stable, groups=stable.condition_id))
    train, test = stable.iloc[a].copy(), stable.iloc[b].copy()
    assert not set(train.condition_id) & set(test.condition_id)
    return train, test


def candidate_settings(train: pd.DataFrame, replicates: int):
    candidates = train.groupby(FACTORS + ["condition_id"], as_index=False).size()
    return candidates.loc[candidates["size"].ge(replicates)].reset_index(drop=True)


def predict(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    # Fixed interaction encoding and fixed alpha: never tuned against holdout outcomes.
    model = Ridge(alpha=1.0, fit_intercept=True)
    model.fit(design_matrix(train), train[OUTCOMES])
    return model.predict(design_matrix(test))


def grouped_errors(test: pd.DataFrame, predictions: np.ndarray) -> pd.DataFrame:
    errors = pd.DataFrame(np.abs(test[OUTCOMES].to_numpy() - predictions), columns=OUTCOMES)
    errors["condition_id"] = test.condition_id.to_numpy()
    return errors.groupby("condition_id")[OUTCOMES].mean()


def bootstrap_difference(reduced: pd.DataFrame, full: pd.DataFrame, scale: np.ndarray, seed: int = 42):
    delta = ((reduced - full) / scale).mean(axis=1).to_numpy()
    rng = np.random.default_rng(seed)
    draws = rng.choice(delta, (2000, len(delta)), replace=True).mean(axis=1)
    return {"mean": float(delta.mean()), "lower_95": float(np.quantile(draws, .025)), "upper_95": float(np.quantile(draws, .975)), "groups": len(delta), "bootstrap_draws": 2000}


def run(root: Path, budget: int = 60, replicates: int = 3, random_runs: int = 20) -> dict:
    if random_runs < 2:
        raise ValueError("At least two random baselines are required")
    source = root / "data/processed/cycles.parquet"
    frame = pd.read_parquet(source) if source.exists() else ingest(root)
    validate(frame)
    train, test = split_data(frame)
    candidates = candidate_settings(train, replicates)
    print(f"Planning {budget} settings from {len(candidates)} eligible; {len(test)} holdout cycles", flush=True)
    selected, trace, solver = plan(candidates, budget)
    selected_ids = candidates.iloc[selected].condition_id.tolist()
    reduced = representative_cycles(train, selected_ids, replicates)
    cover, _ = requirements(candidates)
    trace['condition_ids'] = [';'.join(candidates.iloc[selected].loc[cover[i, selected].astype(bool), 'condition_id']) for i in range(len(trace))]
    trace['cycle_ids'] = [';'.join(map(str, reduced.loc[reduced.condition_id.isin(ids.split(';')), 'cycle_id'])) for ids in trace.condition_ids]
    scale = train[OUTCOMES].std(ddof=0).to_numpy()
    if (scale <= 0).any():
        raise ValueError("Constant training response cannot be normalised")
    full_predictions, reduced_predictions = predict(train, test), predict(reduced, test)
    full_error, reduced_error = grouped_errors(test, full_predictions), grouped_errors(test, reduced_predictions)
    interval = bootstrap_difference(reduced_error, full_error, scale)
    rng = np.random.default_rng(2026)
    random_scores, random_coverage, random_outcomes = [], [], []
    for _ in range(random_runs):
        random_indices = rng.choice(len(candidates), budget, replace=False)
        random_ids = candidates.iloc[random_indices].condition_id.tolist()
        baseline = representative_cycles(train, random_ids, replicates)
        errors = grouped_errors(test, predict(baseline, test))
        random_scores.append(float((errors.mean().to_numpy() / scale).mean()))
        random_outcomes.append(errors.mean().to_numpy())
        cover, _ = requirements(candidates)
        random_coverage.append(float((cover[:, random_indices].sum(axis=1) >= 1).mean()))
    metrics = pd.DataFrame({"outcome": OUTCOMES, "full_MAE": full_error.mean().to_numpy(), "optimised_MAE": reduced_error.mean().to_numpy(), "random_mean_MAE": np.mean(random_outcomes, axis=0), "training_std": scale})
    metrics["optimised_normalised_MAE"] = metrics.optimised_MAE / metrics.training_std
    # Near-duplicate flag requires same settings; evidence flag, never a deletion command.
    ordered = train.sort_values("cycle_id").copy()
    normalized = ordered[OUTCOMES].to_numpy() / scale
    ordered["response_distance_to_previous"] = np.r_[np.nan, np.sqrt(np.mean(np.diff(normalized, axis=0) ** 2, axis=1))]
    ordered["review_repeat"] = ordered.condition_id.eq(ordered.condition_id.shift()) & ordered.response_distance_to_previous.lt(.02)
    ordered["selected"] = ordered.cycle_id.isin(reduced.cycle_id)
    removed = train.loc[~train.cycle_id.isin(reduced.cycle_id)]
    summary = {
        "seed": 42, "dataset_rows": len(frame), "stable_rows": int(frame.unstable.eq(0).sum()), "excluded_unstable": int(frame.unstable.eq(1).sum()),
        "historical_training_cycles": len(train), "holdout_cycles": len(test), "training_settings": train.condition_id.nunique(), "holdout_settings": test.condition_id.nunique(),
        "eligible_settings": len(candidates), "selected_settings": budget, "replicates": replicates, "selected_cycles": len(reduced),
        "retrospective_cycle_reduction_pct": 100 * (1 - len(reduced) / len(train)), "covered_requirements": int(trace.covered.sum()), "total_requirements": len(trace),
        "historical_cycle_hours_omitted": len(removed) / 60,
        "historical_motor_kwh_omitted": float(removed.EPS1_mean.sum() * 60 / 3_600_000),
        "full_normalised_MAE": float((full_error.mean().to_numpy() / scale).mean()), "optimised_normalised_MAE": float((reduced_error.mean().to_numpy() / scale).mean()),
        "random_normalised_MAE_mean": float(np.mean(random_scores)), "random_normalised_MAE_std": float(np.std(random_scores)), "random_runs": random_runs,
        "random_coverage_mean": float(np.mean(random_coverage)), "noninferiority_margin": .03, "error_difference_bootstrap": interval,
        "noninferiority_passed": bool(interval["upper_95"] < .03), "near_repeat_review_flags": int(ordered.review_repeat.sum()), "solver": solver,
        "limitations": ["Retrospective evidence on one hydraulic rig; no prospective savings or Volvo validation.", "Requirements represent factor/pair coverage, not legislation or measured product acceptance limits.", "Holdout isolates settings, not rig assets or time; drift and serial dependence remain.", "Outcome means discard transient dynamics; three repeats do not establish reliability.", "Motor energy omits auxiliary loads, warmup and setup. No carbon claim.", "Bootstrap groups are condition combinations; uncertainty is conditional on one split and fixed model."],
        "environment": {"python": platform.python_version(), **{p: importlib.metadata.version(p) for p in ["numpy", "pandas", "scipy", "scikit-learn"]}},
    }
    reports = root / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    metrics.to_csv(reports / "outcome_metrics.csv", index=False)
    trace.to_csv(reports / "requirements_traceability.csv", index=False)
    missing_pairs(candidates).to_csv(reports / "unsupported_pairs.csv", index=False)
    selected_settings = candidates.iloc[selected].copy()
    selected_settings["selection_order"] = np.arange(1, len(selected) + 1)
    selected_settings.to_csv(reports / "selected_settings.csv", index=False)
    sequence(selected_settings).to_csv(reports / "campaign_schedule.csv", index=False)
    reduced[["cycle_id", "condition_id"] + FACTORS + OUTCOMES].to_csv(reports / "selected_cycles.csv", index=False)
    ordered.to_parquet(reports / "redundancy_review.parquet", index=False)
    split = frame[["cycle_id", "condition_id", "run_id", "unstable"]].copy()
    split["partition"] = np.where(split.unstable.eq(1), "excluded_unstable", np.where(split.cycle_id.isin(train.cycle_id), "train", "holdout"))
    split.to_csv(reports / "split_manifest.csv", index=False)
    audit = test[["cycle_id", "condition_id"]].copy()
    for i, outcome in enumerate(OUTCOMES):
        audit[f"{outcome}_observed"] = test[outcome].to_numpy()
        audit[f"{outcome}_full"] = full_predictions[:, i]
        audit[f"{outcome}_optimised"] = reduced_predictions[:, i]
    audit.to_parquet(reports / "holdout_predictions.parquet", index=False)
    pd.DataFrame({"seed_run": range(random_runs), "normalised_MAE": random_scores, "coverage": random_coverage}).to_csv(reports / "random_baselines.csv", index=False)
    report = f"""# RigPlan benchmark\n\nReproduce: `rigplan benchmark --budget {budget} --replicates {replicates}`. Seed 42; no holdout tuning.\n\n- Measured cycles: {len(frame):,}; excluded unstable: {summary['excluded_unstable']:,}.\n- Training/holdout settings: {summary['training_settings']}/{summary['holdout_settings']}; disjoint by all four settings.\n- Selected {len(reduced)} of {len(train)} historical training cycles ({summary['retrospective_cycle_reduction_pct']:.1f}% smaller subset).\n- Declared requirement coverage: {summary['covered_requirements']}/{len(trace)}.\n- Normalised MAE: full {summary['full_normalised_MAE']:.4f}; optimised {summary['optimised_normalised_MAE']:.4f}; random mean {summary['random_normalised_MAE_mean']:.4f}. Lower is better.\n- Paired group-bootstrap difference (optimised minus full): {interval['mean']:.4f}, 95% interval [{interval['lower_95']:.4f}, {interval['upper_95']:.4f}]. Predeclared margin 0.03; {'PASS' if summary['noninferiority_passed'] else 'FAIL'}.\n- D-optimal design rank: {solver['unregularised_rank']}/{solver['model_columns']}.\n\nThe gate measures average error across five responses and does not certify individual-response acceptance. A pass is conditional evidence; a failure means the reduced plan needs more work.\n\n## Limits\n\n""" + "\n".join(f"- {x}" for x in summary["limitations"])
    (reports / "BENCHMARK.md").write_text(report + "\n", encoding="utf-8")
    return summary
