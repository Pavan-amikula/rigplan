"""Categorical, pairwise requirement cover plus regularised D-optimal augmentation.

Selection consumes settings and availability only, never response measurements.
"""
from __future__ import annotations

from itertools import combinations
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from sklearn.preprocessing import OneHotEncoder, PolynomialFeatures

from rigplan.data import FACTORS, LEVELS


def design_matrix(frame: pd.DataFrame) -> np.ndarray:
    encoder = OneHotEncoder(categories=[LEVELS[x] for x in FACTORS], drop="first", sparse_output=False, handle_unknown="error")
    main = encoder.fit_transform(frame[FACTORS])
    # Products of dummies for a single factor are zero; remove constant columns.
    matrix = PolynomialFeatures(2, interaction_only=True, include_bias=True).fit_transform(main)
    # Fixed mask from the entire categorical universe avoids split-dependent columns.
    from itertools import product
    universe = pd.DataFrame(product(*(LEVELS[x] for x in FACTORS)), columns=FACTORS)
    full = PolynomialFeatures(2, interaction_only=True).fit_transform(encoder.transform(universe))
    return matrix[:, np.any(full != 0, axis=0)]


def requirements(candidates: pd.DataFrame, pairwise: bool = True) -> tuple[np.ndarray, list[str]]:
    columns, names = [], []
    for factor in FACTORS:
        for value in LEVELS[factor]:
            columns.append(candidates[factor].eq(value).to_numpy())
            names.append(f"{factor}={value}")
    if pairwise:
        for a, b in combinations(FACTORS, 2):
            # Only observed pairs are claimed coverable. All absent pairs are exported separately.
            for va, vb in candidates[[a, b]].drop_duplicates().sort_values([a, b]).itertuples(index=False, name=None):
                columns.append((candidates[a].eq(va) & candidates[b].eq(vb)).to_numpy())
                names.append(f"{a}={va} & {b}={vb}")
    return np.array(columns, dtype=float), names


def minimum_cover(candidates: pd.DataFrame, pairwise: bool = True) -> tuple[list[int], dict]:
    cover, _ = requirements(candidates, pairwise)
    if (cover.sum(axis=1) == 0).any():
        raise ValueError("Infeasible coverage: required factor levels have no eligible candidates")
    solved = milp(c=np.ones(len(candidates)), integrality=np.ones(len(candidates)), bounds=Bounds(0, 1), constraints=LinearConstraint(cover, 1, np.inf), options={"time_limit": 30, "mip_rel_gap": 0.0})
    if solved.x is None:
        raise ValueError(f"No feasible requirement cover: {solved.message}")
    selected = np.flatnonzero(solved.x > .5).tolist()
    return selected, {"status": int(solved.status), "message": solved.message, "optimal": bool(solved.status == 0), "mip_gap": float(solved.mip_gap)}


def plan(candidates: pd.DataFrame, budget: int, pairwise: bool = True, ridge: float = 1.0) -> tuple[list[int], pd.DataFrame, dict]:
    if ridge <= 0 or not np.isfinite(ridge):
        raise ValueError("Regularisation must be positive and finite")
    if budget > len(candidates) or budget < 1:
        raise ValueError("Budget must be between one and the number of eligible settings")
    selected, solver = minimum_cover(candidates, pairwise)
    if len(selected) > budget:
        raise ValueError(f"Budget infeasible: coverage needs at least the found cover of {len(selected)} settings; increase budget")
    x = design_matrix(candidates)
    information = ridge * np.eye(x.shape[1]) + x[selected].T @ x[selected]
    remaining = np.ones(len(x), dtype=bool)
    remaining[selected] = False
    while len(selected) < budget:
        # Regularisation can conceal aliased effects. Fill missing directions first.
        _, singular, vectors = np.linalg.svd(x[selected], full_matrices=False)
        rank = int((singular > max(x[selected].shape) * np.finfo(float).eps * singular[0]).sum())
        if rank < x.shape[1]:
            gain = np.maximum(0, np.sum(x*x, axis=1) - np.sum((x @ vectors[:rank].T)**2, axis=1))
        else:
            inverse = np.linalg.inv(information)
            gain = np.einsum("ij,jk,ik->i", x, inverse, x)
        gain[~remaining] = -np.inf
        best = int(np.argmax(gain))
        selected.append(best)
        remaining[best] = False
        information += np.outer(x[best], x[best])
    cover, names = requirements(candidates, pairwise)
    counts = cover[:, selected].sum(axis=1).astype(int)
    trace = pd.DataFrame({"requirement": names, "selected_settings": counts, "covered": counts >= 1})
    if not trace.covered.all():
        raise RuntimeError("Returned solution failed independent coverage verification")
    solver.update({"regularised_logdet": float(np.linalg.slogdet(information)[1]), "model_columns": x.shape[1], "unregularised_rank": int(np.linalg.matrix_rank(x[selected])), "requirements": len(names)})
    return selected, trace, solver


def missing_pairs(candidates: pd.DataFrame) -> pd.DataFrame:
    records = []
    for a, b in combinations(FACTORS, 2):
        for va in LEVELS[a]:
            for vb in LEVELS[b]:
                if not (candidates[a].eq(va) & candidates[b].eq(vb)).any():
                    records.append({"factor_a": a, "level_a": va, "factor_b": b, "level_b": vb})
    return pd.DataFrame(records, columns=["factor_a", "level_a", "factor_b", "level_b"])


def representative_cycles(frame: pd.DataFrame, setting_ids: list[str], replicates: int) -> pd.DataFrame:
    if replicates < 1:
        raise ValueError("At least one repeat is required")
    chosen = []
    for condition in setting_ids:
        group = frame.loc[frame.condition_id.eq(condition)].sort_values("cycle_id")
        if len(group) < replicates:
            raise ValueError(f"Not enough repeats for {condition}")
        positions = np.linspace(0, len(group) - 1, replicates, dtype=int)
        chosen.append(group.iloc[positions])
    return pd.concat(chosen, ignore_index=True)
