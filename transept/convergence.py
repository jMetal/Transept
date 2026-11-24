"""Whether a run seems to have stopped improving, from its progress records.

The records hold the best value of each objective, so this only says that the ends of the front have
stopped moving: the rest of the front may still be improving. It is a hint, not a stopping rule.
"""

from __future__ import annotations

import pandas as pd

# Evaluations per generation when the configuration of a run does not say its population size.
DEFAULT_POPULATION = 100


def generations_without_improvement(records: pd.DataFrame, population: int) -> int:
    """Returns the generations since the best value of some objective last improved.

    Args:
        records: The progress of the run: `evaluations`, `seconds` and the best of each objective.
        population: Evaluations of a generation.
    """
    names = [name for name in records.columns if name not in ("evaluations", "seconds")]
    if records.empty or not names:
        return 0
    evaluations = records["evaluations"].to_numpy()
    improved = evaluations[0]
    for name in names:
        rises = records[name].cummax().diff() > 0
        if rises.any():
            improved = max(improved, evaluations[rises.to_numpy()][-1])
    return int(evaluations[-1] - improved) // max(population, 1)
