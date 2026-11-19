"""What independent runs give together, without Streamlit: fronts, summaries and exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from transept import (
    alignment,
    datasets,
    ensemble,
    exports,
    front,
    generic_numbers,
    reference_scores,
    runs,
    series,
)

MEDIAN = "median"
IQR = "IQR"


@dataclass(slots=True, frozen=True)
class FinishedRun:
    """A finished run of a series.

    Attributes:
        seed: Its random seed.
        run: The run.
        values: Its objective values, by row of FUN.csv.
        front: Its distinct non-dominated solutions, as `front.summarize` gives them.
    """

    seed: int
    run: runs.Run
    values: pd.DataFrame
    front: pd.DataFrame


def finished_runs(chosen: series.Series) -> list[FinishedRun]:
    """Returns the finished runs of a series."""
    found = []
    for member in series.members(chosen):
        if member.state == runs.RunState.FINISHED.value:
            values = runs.objective_values(member.run)
            found.append(FinishedRun(member.seed, member.run, values, front.summarize(values)))
    return found


def aggregate_front(finished: list[FinishedRun]) -> pd.DataFrame:
    """Returns the distinct non-dominated solutions of all the runs together.

    Only the front of each run can reach the aggregate, so the others are not compared.

    Returns:
        The columns `seed`, `row` (of the FUN.csv of that run), the objectives and `note`
        (`best <objective>`, `knee` or empty), sorted by the first objective, best first. The knee
        is that of the aggregate, not of any run. Of several solutions with the same values, that
        of the first run is kept.
    """
    if not finished:
        return pd.DataFrame(columns=["seed", "row", "note"])
    names = list(finished[0].values.columns)
    pool = pd.concat(
        [
            item.front.assign(seed=item.seed, origin=item.front["row"])[["seed", "origin", *names]]
            for item in finished
        ],
        ignore_index=True,
    )
    summary = front.summarize(pool[names])
    summary = summary.assign(
        seed=pool["seed"].to_numpy()[summary["row"].to_numpy()],
        row=pool["origin"].to_numpy()[summary["row"].to_numpy()],
    )
    return summary[["seed", "row", *names, "note"]]


def alignment_paths(finished: list[FinishedRun], table: pd.DataFrame) -> list[Path]:
    """The file of every alignment of a table with the columns `seed` and `row`, such as the
    aggregate front."""
    by_seed = {item.seed: item.run for item in finished}
    return [
        runs.alignment_file(by_seed[int(seed)], int(row))
        for seed, row in zip(table["seed"], table["row"])
    ]


def knee_position(aggregate: pd.DataFrame, names: list[str]) -> int | None:
    """The position of the knee in the aggregate front (its objectives `names`), if it is not
    empty; as in a run, also when its note says that it is the best in an objective."""
    if aggregate.empty:
        return None
    return front.knee_row(front.summarize(aggregate[names].reset_index(drop=True)))


def aggregate_summary(
    paths: list[Path], knee: int, proteins: dict[str, datasets.Protein]
) -> ensemble.FrontSummary | None:
    """How much the alignments of the aggregate front agree, and its medoid.

    Args:
        paths: The files of its alignments, in its order.
        knee: The position of its knee.
    """
    return ensemble.front_summary([alignment.read_fasta(path) for path in paths], knee, proteins)


def gpcrdb_consistency(
    paths: list[Path], proteins: dict[str, datasets.Protein]
) -> list[float | None] | None:
    """The GPCRdb consistency of every alignment (`generic_numbers.alignment_consistency`), or None
    unless the numbering of every receptor has been fetched. It never goes to GPCRdb."""
    if not paths:
        return None
    receptors = [row.id for row in alignment.read_fasta(paths[0])]
    residues = {receptor: generic_numbers.cached(receptor) for receptor in receptors}
    if any(found is None for found in residues.values()):
        return None
    by_residue = generic_numbers.residue_numbers(proteins, residues)
    return [
        generic_numbers.alignment_consistency(alignment.read_fasta(path), by_residue)
        for path in paths
    ]


def spread(items: list, limit: int) -> list:
    """At most `limit` items, evenly spread over the list and in its order."""
    if len(items) <= limit:
        return list(items)
    step = len(items) / limit
    return [items[int(i * step)] for i in range(limit)]


def other_runs_sample(finished: list[FinishedRun], seed: int, limit: int) -> list[Path]:
    """Alignments of the fronts of the other runs, the same number from each, at most `limit`.

    They measure the support of an alignment of the run with that seed by independent runs. On
    the GPCR benchmark, this support told the right columns from the wrong ones better than the
    support by the alignments of the same run (AUC 0.81 against 0.72, median over 14 datasets).
    """
    others = [item for item in finished if item.seed != seed]
    if not others:
        return []
    each = max(1, limit // len(others))
    found = [
        runs.alignment_file(item.run, int(row))
        for item in others
        for row in spread(list(item.front["row"]), each)
    ]
    return spread(found, limit)


def run_summary(finished: list[FinishedRun]) -> pd.DataFrame:
    """Returns one row per run: its seed, solutions, best value of each objective and runtime."""
    rows = []
    for item in finished:
        runtime = (runs.metadata(item.run) or {}).get("runtimeMs")
        rows.append(
            {
                "seed": item.seed,
                "non-dominated": len(item.front),
                **{f"best {name}": item.values[name].max() for name in item.values.columns},
                "runtime (s)": round(runtime / 1000) if runtime is not None else None,
            }
        )
    return pd.DataFrame(rows)


def with_statistics(table: pd.DataFrame) -> pd.DataFrame:
    """Adds to a table of runs a row with the median and another with the interquartile range."""
    if table.empty:
        return table
    numeric = table.drop(columns="seed").apply(pd.to_numeric, errors="coerce")
    median = {"seed": MEDIAN, **numeric.median().to_dict()}
    spread = numeric.quantile(0.75) - numeric.quantile(0.25)
    rows = [{**row, "seed": str(row["seed"])} for row in table.to_dict("records")]
    return pd.DataFrame([*rows, median, {"seed": IQR, **spread.to_dict()}])


def scores_of_runs(
    jar: str, data_root: str, finished: list[FinishedRun], runs_root
) -> pd.DataFrame | None:
    """Returns the metrics against the reference of every alignment of the runs.

    Returns:
        The columns `seed`, `row` and the metrics; None if the tool could not compare them.
    """
    frames = []
    for item in finished:
        table = reference_scores.run_scores(jar, data_root, item.run, runs_root)
        if table is None:
            return None
        frames.append(table.assign(seed=item.seed))
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)[["seed", "row", *reference_scores.METRICS]]


def summary_with_scores(summary: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    """Adds to the summary of the runs the best and the median Pair F1 of each one."""
    grouped = scores.groupby("seed")[reference_scores.PAIR_F1]
    return summary.assign(
        **{
            f"best {reference_scores.PAIR_F1}": summary["seed"].map(grouped.max()),
            f"median {reference_scores.PAIR_F1}": summary["seed"].map(grouped.median()),
        }
    )


def export_files(
    finished: list[FinishedRun],
    aggregate: pd.DataFrame,
    summary: pd.DataFrame,
    proteins: dict[str, datasets.Protein],
) -> dict[str, str | bytes]:
    """Returns the files of the aggregate front: its alignments, its table and the summary."""
    by_seed = {item.seed: item.run for item in finished}
    files: dict[str, str | bytes] = {
        "aggregate_front.csv": aggregate.to_csv(index=False),
        "runs_summary.csv": summary.to_csv(index=False),
    }
    for row in aggregate.itertuples():
        rows = alignment.read_fasta(runs.alignment_file(by_seed[row.seed], int(row.row)))
        stem = f"seed{row.seed}_MSASol{row.row}"
        files[f"{stem}.fasta"] = exports.to_fasta(rows)
        files[f"{stem}.sto"] = exports.to_stockholm(rows, proteins)
    return files
