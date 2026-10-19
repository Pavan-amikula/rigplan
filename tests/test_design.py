from itertools import product
import numpy as np
import pandas as pd
import pytest
from rigplan.data import FACTORS, LEVELS, validate
from rigplan.design import design_matrix, plan, representative_cycles, requirements, missing_pairs
from rigplan.pipeline import split_data


@pytest.fixture
def universe():
    return pd.DataFrame(product(*(LEVELS[f] for f in FACTORS)), columns=FACTORS)


def test_full_factorial_has_estimable_interaction_model(universe):
    x = design_matrix(universe)
    assert x.shape == (144, 48)
    assert np.linalg.matrix_rank(x) == 48


def test_plan_covers_requirements_and_selects_unique_settings(universe):
    chosen, trace, diagnostics = plan(universe, 60)
    assert len(set(chosen)) == 60
    assert trace.covered.all()
    assert diagnostics['unregularised_rank'] == 48
    assert diagnostics['optimal']


def test_responses_cannot_influence_selection(universe):
    a = plan(universe, 50)[0]
    changed = universe.copy()
    changed['PS1_mean'] = np.random.default_rng(0).normal(size=len(changed)) * 1e9
    assert a == plan(changed, 50)[0]


def test_infeasible_budget_is_rejected(universe):
    with pytest.raises(ValueError, match="Budget infeasible"):
        plan(universe, 1)


def test_missing_required_level_is_rejected(universe):
    with pytest.raises(ValueError, match="Infeasible coverage"):
        plan(universe.loc[universe.cooler.ne(3)], 50)


def test_missing_pairs_are_not_silently_claimed(universe):
    reduced = universe.loc[~(universe.cooler.eq(3) & universe.valve.eq(73))]
    absent = missing_pairs(reduced)
    assert len(absent) == 1
    assert absent.iloc[0].factor_a == 'cooler'
    _, names = requirements(reduced)
    assert 'cooler=3 & valve=73' not in names


def test_encoding_does_not_change_with_split(universe):
    assert np.array_equal(design_matrix(universe)[[0, 30, 100]], design_matrix(universe.iloc[[0, 30, 100]]))


def test_replicates_are_distinct_and_outcome_independent():
    frame = pd.DataFrame({'cycle_id': range(1, 11), 'condition_id': ['a']*10})
    out = representative_cycles(frame, ['a'], 3)
    assert out.cycle_id.tolist() == [1, 5, 10]
    with pytest.raises(ValueError, match="Not enough"):
        representative_cycles(frame, ['a'], 11)


def test_group_split_has_no_combination_overlap(universe):
    frame = universe.copy()
    frame['condition_id'] = frame.astype(str).agg('_'.join, axis=1)
    frame['unstable'] = 0
    frame = pd.concat([frame]*3, ignore_index=True)
    train, test = split_data(frame)
    assert not set(train.condition_id) & set(test.condition_id)
    assert len(train) + len(test) == len(frame)


def test_bad_schema_fails_loudly():
    with pytest.raises(ValueError, match="Missing columns"):
        validate(pd.DataFrame({'cycle_id': [1]}))


def test_schedule_keeps_every_setting_and_counts_transitions(universe):
    from rigplan.schedule import sequence
    subset = universe.iloc[::8].copy()
    out = sequence(subset)
    assert len(out) == len(subset)
    assert not out[FACTORS].duplicated().any()
    assert out.sequence.tolist() == list(range(1, len(out)+1))
    expected = out[FACTORS].ne(out[FACTORS].shift()).iloc[1:].to_numpy().sum()
    assert out.factor_changes_from_previous.sum() == expected
