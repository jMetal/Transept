"""How well the alignment recommended from a front, and the support of its columns, agree with
the reference alignment of the dataset.

For every finished run whose dataset has a reference, it reports:

- the pair F1 against the reference of the best seed, of the knee, of the medoid of the front
  (the alignment that agrees most with the others), of the best alignment of the front (known
  only with the reference) and the mean over the front, as a user choosing at random would get;
- how much the alignments of the front agree, overall and inside and outside the helices;
- whether the support of a column predicts that it is right: the mean fraction of its pairs that
  the reference also aligns, for columns of high, medium and low support, and the area under the
  ROC curve of support for telling right columns (at least half of their pairs in the reference)
  from wrong ones.

The pair F1 of the alignments of a run comes from Transept core (the same numbers as Results).

Usage: python scripts/evaluate_recommendations.py [--dataset NAME] [--output FILE.csv]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from transept import (
    alignment,
    analysis,
    datasets,
    ensemble,
    front,
    reference_scores,
    runs,
    settings,
    tracks,
)

HIGH_SUPPORT = 0.9
LOW_SUPPORT = 0.5
RIGHT_COLUMN = 0.5


def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """The area under the ROC curve of scores for labels (Mann-Whitney), NaN with one class."""
    positives, negatives = int(labels.sum()), int((~labels).sum())
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = pd.Series(scores).rank().to_numpy()
    return float((ranks[labels].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def evaluate(run: runs.Run, jar: str) -> dict | None:
    config = runs.config(run)
    root = config.get("dataRoot", "")
    if not reference_scores.has_reference(root, run.dataset):
        return None
    values = runs.objective_values(run)
    if len(values.columns) < 2:
        return None
    table = front.summarize(values)
    scores = reference_scores.run_scores(jar, root, run, settings.runs_root())
    if scores is None or table.empty:
        return None
    f1 = scores.set_index("row")[reference_scores.PAIR_F1]
    rows = [int(row) for row in table["row"] if int(row) in f1.index]
    proteins = datasets.read_topology(datasets.topology_file(root, run.dataset))
    by_id = {protein.id: protein for protein in proteins}
    alignments = [analysis.load_alignment(runs.alignment_file(run, row), proteins) for row in rows]
    matrix = ensemble.agreement_matrix(alignments)
    found = ensemble.consensus(matrix)
    medoid = rows[found.medoid]
    knee = front.knee_row(table)
    seeds = reference_scores.seed_scores(
        jar, root, run, settings.runs_root(), config.get("seedMethods", [])
    )
    best_seed = seeds.loc[seeds[reference_scores.PAIR_F1].idxmax()] if not seeds.empty else None

    # Support of the columns of the medoid, and how right they are according to the reference.
    chosen = alignments[found.medoid]
    others = [rows_ for position, rows_ in enumerate(alignments) if position != found.medoid]
    support = tracks.support(chosen, others)
    reference = analysis.load_alignment(datasets.reference_file(root, run.dataset), proteins)
    right = analysis.compare(chosen, reference).column_agreement
    comparable = np.isfinite(right) & np.isfinite(support.column) if support else np.isfinite(right)
    column_support = support.column[comparable] if support else np.ones(int(comparable.sum()))
    right_here = right[comparable]
    helices = alignment.helices(alignment.consensus(chosen, by_id))
    in_helix = np.zeros(len(right), dtype=bool)
    for first, last in helices:
        in_helix[first : last + 1] = True

    def mean_where(mask: np.ndarray) -> float:
        return float(right_here[mask].mean()) if mask.any() else float("nan")

    return {
        "dataset": run.dataset,
        "run": run.run_id,
        "algorithm": config.get("algorithmType"),
        "front": len(rows),
        "best seed": None if best_seed is None else best_seed["seed"],
        "F1 best seed": None if best_seed is None else float(best_seed[reference_scores.PAIR_F1]),
        "F1 knee": float(f1[knee]),
        "F1 medoid": float(f1[medoid]),
        "F1 best of front": float(f1[rows].max()),
        "F1 mean of front": float(f1[rows].mean()),
        "F1 worst of front": float(f1[rows].min()),
        "medoid is knee": medoid == knee,
        "agreement in front": found.overall,
        "support in helices": float(np.nanmean(support.column[in_helix])) if support else 1.0,
        "support outside": float(np.nanmean(support.column[~in_helix])) if support else 1.0,
        f"right | support>={HIGH_SUPPORT}": mean_where(column_support >= HIGH_SUPPORT),
        f"right | {LOW_SUPPORT}-{HIGH_SUPPORT}": mean_where(
            (column_support >= LOW_SUPPORT) & (column_support < HIGH_SUPPORT)
        ),
        f"right | support<{LOW_SUPPORT}": mean_where(column_support < LOW_SUPPORT),
        f"columns support<{HIGH_SUPPORT}": float((column_support < HIGH_SUPPORT).mean()),
        "AUC support": auc(column_support, right_here >= RIGHT_COLUMN),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", help="Only the runs of this dataset.")
    parser.add_argument("--output", type=Path, help="Write the table to this CSV file.")
    arguments = parser.parse_args()
    jar = settings.load_settings().jar
    found = []
    for run in runs.list_runs(settings.runs_root()):
        if runs.state(run) != runs.RunState.FINISHED:
            continue
        if arguments.dataset and run.dataset != arguments.dataset:
            continue
        result = evaluate(run, jar)
        if result is not None:
            found.append(result)
            print(f"{run.dataset} {run.run_id}: done", file=sys.stderr)
    table = pd.DataFrame(found)
    if arguments.output:
        table.to_csv(arguments.output, index=False)
    with pd.option_context("display.width", 250, "display.max_columns", None):
        print(table.round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
