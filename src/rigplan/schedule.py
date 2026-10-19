"""Review schedule with equal-cost factor changes; transition times are unknown."""
import numpy as np
import pandas as pd
from rigplan.data import FACTORS


def sequence(settings: pd.DataFrame) -> pd.DataFrame:
    if settings.empty:
        raise ValueError('Cannot schedule an empty campaign')
    settings = settings.sort_values(FACTORS).reset_index(drop=True)
    values = settings[FACTORS].to_numpy()
    costs = (values[:, None, :] != values[None, :, :]).sum(axis=2)
    route = [0]
    available = set(range(1, len(settings)))
    while available:
        best = min(available, key=lambda j: (costs[route[-1], j], j))
        route.append(best)
        available.remove(best)
    def burden(order):
        return sum(costs[a,b] for a,b in zip(order, order[1:]))
    improved = True
    while improved:
        improved = False
        current = burden(route)
        for i in range(1, len(route)-1):
            for j in range(i+1, len(route)):
                trial = route[:i] + route[i:j+1][::-1] + route[j+1:]
                if burden(trial) < current:
                    route, improved = trial, True
                    break
            if improved:
                break
    out = settings.iloc[route].reset_index(drop=True)
    out.insert(0, 'sequence', np.arange(1, len(out)+1))
    out['factor_changes_from_previous'] = [0] + [int(costs[a,b]) for a,b in zip(route, route[1:])]
    return out
