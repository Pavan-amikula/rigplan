from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not (ROOT/'reports/development_study.csv').exists(), reason='Run rigplan study first')


def test_study_never_uses_original_holdout():
    outer = pd.read_csv(ROOT/'reports/split_manifest.csv')
    inner = pd.read_csv(ROOT/'reports/development_split_manifest.csv')
    final_ids = set(outer.loc[outer.partition.eq('holdout'), 'cycle_id'])
    assert not set(inner.cycle_id) & final_ids
    train_ids = set(outer.loc[outer.partition.eq('train'), 'cycle_id'])
    validation_ids = []
    for _, fold in inner.groupby('fold'):
        fit = set(fold.loc[fold.partition.eq('fit'), 'condition_id'])
        validation = set(fold.loc[fold.partition.eq('validation'), 'condition_id'])
        assert not fit & validation
        assert set(fold.cycle_id) == train_ids
        validation_ids.extend(fold.loc[fold.partition.eq('validation'), 'cycle_id'])
    assert len(validation_ids) == len(set(validation_ids)) == len(train_ids)


def test_study_results_preserve_coverage_and_one_error_per_group():
    folds = pd.read_csv(ROOT/'reports/development_fold_metrics.csv')
    errors = pd.read_parquet(ROOT/'reports/development_oof_errors.parquet')
    assert folds.coverage.all()
    assert not errors[['scenario', 'condition_id']].duplicated().any()
    assert len(folds) == 27
    assert errors.groupby('scenario').size().eq(108).all()
    assert not errors.isna().any().any()
