"""Exploratory budget/repeat sensitivity on training data only.

This study does not replace or repeatedly score the original holdout benchmark.
Its intervals are descriptive after comparing multiple scenarios.
"""
from pathlib import Path
import json
import math
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from rigplan.data import OUTCOMES, validate
from rigplan.design import plan, representative_cycles
from rigplan.pipeline import split_data, candidate_settings, grouped_errors, predict, bootstrap_difference


def development_partitions(frame: pd.DataFrame):
    train, final_holdout = split_data(frame)
    folds = []
    for fold, (a, b) in enumerate(GroupKFold(n_splits=3).split(train, groups=train.condition_id), 1):
        fit, validation = train.iloc[a].copy(), train.iloc[b].copy()
        if set(fit.condition_id) & set(validation.condition_id):
            raise RuntimeError('Inner groups overlap')
        folds.append((fold, fit, validation))
    return train, final_holdout, folds


def run_study(root: Path) -> dict:
    frame = pd.read_parquet(root/'data/processed/cycles.parquet')
    validate(frame)
    train, final_holdout, folds = development_partitions(frame)
    fold_cache, manifest = [], []
    for fold, fit, validation in folds:
        scale = fit[OUTCOMES].std(ddof=0).to_numpy()
        full = grouped_errors(validation, predict(fit, validation)) / scale
        fold_cache.append((fold, fit, validation, scale, full))
        for partition, subset in [('fit', fit), ('validation', validation)]:
            part = subset[['cycle_id', 'condition_id']].copy()
            part['fold'], part['partition'] = fold, partition
            manifest.append(part)
    rows, errors, fold_rows = [], [], []
    for fraction in [.5, .75, 1.0]:
        for repeats in [3, 6, 10]:
            name = f'settings_{int(fraction*100)}pct_repeats_{repeats}'
            reduced_errors, full_errors = [], []
            for fold, fit, validation, scale, full in fold_cache:
                candidates = candidate_settings(fit, repeats)
                budget = math.ceil(fraction * len(candidates))
                selected, trace, diagnostics = plan(candidates, budget)
                reduced = representative_cycles(fit, candidates.iloc[selected].condition_id.tolist(), repeats)
                reduced_error = grouped_errors(validation, predict(reduced, validation)) / scale
                reduced_errors.append(reduced_error)
                full_errors.append(full)
                audit = pd.DataFrame({'condition_id': reduced_error.index, 'reduced_normalised_MAE': reduced_error.mean(axis=1).to_numpy(), 'full_normalised_MAE': full.mean(axis=1).to_numpy()})
                audit['scenario'], audit['fold'] = name, fold
                errors.append(audit)
                fold_rows.append({'scenario': name, 'fold': fold, 'settings': budget, 'cycles': len(reduced), 'coverage': bool(trace.covered.all()), 'rank': diagnostics['unregularised_rank'], 'model_columns': diagnostics['model_columns']})
            reduced_error = pd.concat(reduced_errors).sort_index()
            full = pd.concat(full_errors).sort_index()
            interval = bootstrap_difference(reduced_error, full, np.ones(len(OUTCOMES)))
            candidates = candidate_settings(train, repeats)
            projected_settings = math.ceil(fraction * len(candidates))
            rows.append({'scenario': name, 'setting_fraction': fraction, 'repeats': repeats, 'projected_settings': projected_settings, 'projected_cycles': projected_settings*repeats, 'historical_subset_reduction_pct': 100*(1-projected_settings*repeats/len(train)), 'development_normalised_MAE': float(reduced_error.mean().mean()), 'full_development_normalised_MAE': float(full.mean().mean()), 'delta': interval['mean'], 'lower_95': interval['lower_95'], 'upper_95': interval['upper_95'], 'within_exploratory_margin': interval['upper_95'] < .03})
            print(f'{name}: development difference {interval["mean"]:.4f}, upper {interval["upper_95"]:.4f}', flush=True)
    table = pd.DataFrame(rows).sort_values(['projected_cycles', 'delta']).reset_index(drop=True)
    passing = table.loc[table.within_exploratory_margin]
    result = {'purpose': 'Exploratory training-only budget/repeat study; not independent validation', 'folds': 3, 'training_settings': train.condition_id.nunique(), 'original_holdout_settings_excluded': final_holdout.condition_id.nunique(), 'scenarios': len(table), 'margin': .03, 'candidate': None, 'release_decision': 'Retain the reference campaign. Original reduced plan failed its held-out gate; development candidates require independent prospective validation.', 'caveat': 'Intervals are descriptive and conditional on fixed folds/model. Nine scenarios were compared; no post-selection confirmatory claim.'}
    reports = root/'reports'
    table.to_csv(reports/'development_study.csv', index=False)
    pd.DataFrame(fold_rows).to_csv(reports/'development_fold_metrics.csv', index=False)
    pd.concat(errors, ignore_index=True).to_parquet(reports/'development_oof_errors.parquet', index=False)
    pd.concat(manifest, ignore_index=True).to_csv(reports/'development_split_manifest.csv', index=False)
    if not passing.empty:
        candidate = passing.iloc[0]
        result['candidate'] = {key: candidate[key].item() if isinstance(candidate[key], np.generic) else candidate[key] for key in ['scenario', 'projected_settings', 'repeats', 'projected_cycles', 'historical_subset_reduction_pct', 'delta', 'upper_95']}
        candidates = candidate_settings(train, int(candidate.repeats))
        selected, _, _ = plan(candidates, int(candidate.projected_settings))
        selected_cycles = representative_cycles(train, candidates.iloc[selected].condition_id.tolist(), int(candidate.repeats))
        selected_cycles[['cycle_id', 'condition_id']].to_csv(reports/'development_candidate_cycles.csv', index=False)
    (reports/'development_study.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result
