"""Integration checks over the real generated benchmark, when available."""
import json
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not (ROOT/'reports/summary.json').exists(), reason='Run rigplan benchmark first')


def test_plan_is_stable_training_only_and_matches_report():
    selected = pd.read_csv(ROOT/'reports/selected_cycles.csv')
    split = pd.read_csv(ROOT/'reports/split_manifest.csv')
    summary = json.loads((ROOT/'reports/summary.json').read_text())
    joined = selected.merge(split, on=['cycle_id', 'condition_id'], validate='one_to_one')
    assert joined.partition.eq('train').all()
    assert joined.unstable.eq(0).all()
    assert len(selected) == summary['selected_cycles']
    assert selected.groupby('condition_id').size().eq(summary['replicates']).all()


def test_traceability_and_holdout_are_complete():
    trace = pd.read_csv(ROOT/'reports/requirements_traceability.csv')
    predictions = pd.read_parquet(ROOT/'reports/holdout_predictions.parquet')
    split = pd.read_csv(ROOT/'reports/split_manifest.csv')
    assert trace.covered.all()
    assert set(predictions.cycle_id) == set(split.loc[split.partition.eq('holdout'), 'cycle_id'])
    assert not predictions.isna().any().any()
    selected = pd.read_csv(ROOT/'reports/selected_cycles.csv')
    for row in trace.itertuples():
        ids = set(map(int, str(row.cycle_ids).split(';')))
        evidence = selected.loc[selected.cycle_id.isin(ids)]
        assert len(evidence) == len(ids)
        for clause in row.requirement.split(' & '):
            factor, value = clause.split('=')
            assert evidence[factor].eq(int(value)).all()
