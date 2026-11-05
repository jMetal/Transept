"""The non-dominated alignments of a result, with its extremes and knee."""

from __future__ import annotations

import math

import pandas as pd

FIRST, SECOND = "SOPwTP", "lDDT"


def summarize(values: pd.DataFrame) -> pd.DataFrame:
    """Returns the distinct non-dominated solutions, sorted by the first objective, best first.

    Every column of `values` is an objective, and all are maximised. Of several rows with the
    same values, the first one is kept. With one objective, only the best solution is
    non-dominated (see `ranking` for the others). The result has the columns `row` (row of
    FUN.csv), the objectives, `distance` (to the ideal point once every objective is scaled to
    [0, 1] over the front) and `note` (`best <objective>`, `knee` or empty).
    """
    names = list(values.columns)
    points = [tuple(point) for point in values[names].itertuples(index=False)]
    front: dict[tuple[float, ...], int] = {}
    for row, point in enumerate(points):
        dominated = any(
            all(a >= b for a, b in zip(other, point)) and other != point for other in points
        )
        if not dominated:
            front.setdefault(point, row)
    if not front:
        return pd.DataFrame(columns=["row", *names, "distance", "note"])
    best = [max(point[i] for point in front) for i in range(len(names))]
    span = [(best[i] - min(point[i] for point in front)) or 1.0 for i in range(len(names))]
    rows = []
    for point, row in front.items():
        distance = math.sqrt(sum(((best[i] - point[i]) / span[i]) ** 2 for i in range(len(names))))
        rows.append({"row": row, **dict(zip(names, point)), "distance": distance, "note": ""})
    table = pd.DataFrame(rows).sort_values(names[0], ascending=False, ignore_index=True)
    if len(names) > 1:
        table.loc[table["distance"].idxmin(), "note"] = "knee"
    for name in reversed(names):  # the first objective wins when one row is best in several
        table.loc[table[name].idxmax(), "note"] = f"best {name}"
    return table


def ranking(values: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    """Returns the distinct solutions of a single-objective result, best first.

    Args:
        values: FUN.csv with one objective column (maximised).
        limit: Number of distinct values kept.

    Returns:
        The columns `row` (first row of FUN.csv with each value), the objective and `copies`
        (rows with that value: the population of a genetic algorithm fills with copies of its best
        solutions).
    """
    name = values.columns[0]
    grouped = (
        values.reset_index(names="row")
        .groupby(name, sort=False)
        .agg(row=("row", "first"), copies=("row", "size"))
        .reset_index()
        .sort_values(name, ascending=False, ignore_index=True)
    )
    return grouped[["row", name, "copies"]].head(limit)


def knee_row(table: pd.DataFrame) -> int | None:
    """Returns the row of FUN.csv of the knee (or of the only solution), if any."""
    if table.empty:
        return None
    return int(table.loc[table["distance"].idxmin(), "row"])


def weighted_compromise(table: pd.DataFrame, weight: float) -> int | None:
    """Returns the row of FUN.csv closest to the ideal point with weights (weight, 1 - weight).

    Args:
        table: The result of `summarize`.
        weight: Weight of SOPwTP, in [0, 1]; lDDT gets the rest. 0.5 gives the knee.
    """
    if table.empty:
        return None
    firsts, seconds = table[FIRST], table[SECOND]
    span_first = (firsts.max() - firsts.min()) or 1.0
    span_second = (seconds.max() - seconds.min()) or 1.0
    distances = (
        weight * ((firsts.max() - firsts) / span_first) ** 2
        + (1 - weight) * ((seconds.max() - seconds) / span_second) ** 2
    ) ** 0.5
    return int(table.loc[distances.idxmin(), "row"])
