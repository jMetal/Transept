"""Results of independent runs: the aggregate of all of them, or one of them."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from transept import (
    charts,
    datasets,
    exports,
    front,
    reference_scores,
    runs,
    series,
    series_analysis,
    settings,
    ui,
)
from transept.series_analysis import FinishedRun

AGGREGATE = "All runs (aggregate)"


def _seed_label(seed: int) -> str:
    return f"seed {seed}"


def _open_alignment(
    chosen: series.Series, seed: int, row: int, finished: list[FinishedRun]
) -> None:
    """Shows an alignment of the aggregate in the view of its run."""
    run = next(item.run for item in finished if item.seed == seed)
    st.session_state[f"row:{run.key}"] = row
    st.session_state[f"show_pending:{chosen.key}"] = _seed_label(seed)
    st.rerun()


def _pick_from_chart(
    aggregate: pd.DataFrame, finished: list[FinishedRun], key: str
) -> tuple | None:
    """The fronts in grey and the aggregate in blue; returns the point just chosen, if any."""
    event = st.plotly_chart(
        charts.series_front_figure([item.front for item in finished], aggregate),
        on_select="rerun",
        selection_mode="points",
        key=f"series_chart:{key}",
        width="stretch",
    )
    points = event.selection.points if event and event.selection else []
    custom = points[0].get("customdata") if points else None
    return tuple(int(value) for value in custom) if isinstance(custom, list) else None


def _pick_from_table(shown: pd.DataFrame, key: str) -> tuple | None:
    """The table of the aggregate; returns the row just chosen, if any."""
    table = shown.assign(file=[f"MSASol{row}.fasta" for row in shown["row"]]).drop(columns="row")
    picked = st.dataframe(
        table[["seed", "file", *[c for c in table.columns if c not in ("seed", "file")]]],
        hide_index=True,
        width="stretch",
        height=280,
        on_select="rerun",
        selection_mode="single-row",
        key=f"series_table:{key}",
    )
    rows = picked.selection.rows if picked and picked.selection else []
    if not rows:
        return None
    chosen = shown.iloc[rows[0]]
    return int(chosen["seed"]), int(chosen["row"])


def _show_against_the_reference(
    chosen: series.Series,
    data_root: str,
    jar: str,
    scores: pd.DataFrame,
    finished: list[FinishedRun],
) -> None:
    """The best alignment of all the runs beside the seed alignments."""
    st.subheader("Against the reference alignment")
    best = scores.loc[scores[reference_scores.PAIR_F1].idxmax()]
    metrics = list(reference_scores.METRICS)
    first = finished[0].run
    seed_table = reference_scores.seed_scores(
        jar, data_root, first, settings.runs_root(), runs.config(first).get("seedMethods", [])
    )
    comparable = seed_table[seed_table["problem"] == ""]
    rows = [
        {
            "alignment": f"seed {int(best['seed'])}, MSASol{int(best['row'])} (best of all runs)",
            **best[metrics].to_dict(),
        },
        *[
            {"alignment": f"seed alignment: {seed['seed']}", **seed[metrics].to_dict()}
            for _, seed in comparable.iterrows()
        ],
    ]
    st.dataframe(pd.DataFrame(rows).round(3), hide_index=True, width="stretch")
    st.caption(
        "The reference is only used here, to evaluate: the search does not see it, and the best of "
        "all runs can only be known with a reference. Higher is better, except for the TM-gap rate."
    )


def _show_downloads(
    chosen: series.Series,
    data_root: str,
    finished: list[FinishedRun],
    aggregate: pd.DataFrame,
    summary: pd.DataFrame,
) -> None:
    """Prepares the files only when asked for, because a front can have many alignments."""
    ready = f"series_zip:{chosen.key}:{len(finished)}"
    if ready in st.session_state:
        st.download_button(
            "Download the aggregate front (zip)",
            st.session_state[ready],
            file_name=f"{chosen.dataset}_{chosen.series_id}_aggregate.zip",
        )
    elif st.button(f"Prepare the {len(aggregate)} alignments of the aggregate front to download"):
        topology = datasets.topology_file(data_root, chosen.dataset)
        proteins = {p.id: p for p in datasets.read_topology(topology)} if topology.is_file() else {}
        st.session_state[ready] = exports.bundle(
            series_analysis.export_files(finished, aggregate, summary, proteins)
        )
        st.rerun()


def _reference_metrics(
    chosen: series.Series, data_root: str, jar: str, finished: list[FinishedRun]
) -> pd.DataFrame | None:
    """The metrics of the runs against the reference, if there is one and the jar can compare."""
    if not reference_scores.has_reference(data_root, chosen.dataset):
        return None
    with st.spinner("Comparing the alignments with the reference..."):
        scores = series_analysis.scores_of_runs(jar, data_root, finished, settings.runs_root())
    if scores is None:
        st.warning(
            "The alignments could not be compared with the reference alignment. A build of "
            "Transept core with the score command is needed: run `make core`."
        )
    return scores


def _show_overview(
    names: list[str], aggregate: pd.DataFrame, finished: list[FinishedRun], key: str
) -> tuple | None:
    """The fronts of the runs or, with one objective, their convergence."""
    if len(names) == 1:
        st.subheader(f"Convergence of {names[0]}")
        st.plotly_chart(
            charts.series_progress_figure([runs.progress(item.run) for item in finished], []),
            width="stretch",
        )
    elif tuple(names) == (front.FIRST, front.SECOND):
        st.subheader("Fronts of the runs and their aggregate")
        point = _pick_from_chart(aggregate, finished, key)
        st.caption(
            "In grey, the front of each run; in blue, the aggregate: the non-dominated alignments "
            "of all the runs together."
        )
        return point
    return None


def _show_aggregate(chosen: series.Series, finished: list[FinishedRun]) -> None:
    current = settings.load_settings()
    names = list(finished[0].values.columns)
    data_root = settings.data_root_of_run(current, chosen.data_root, chosen.dataset)
    aggregate = series_analysis.aggregate_front(finished)
    summary = series_analysis.run_summary(finished)
    scores = _reference_metrics(chosen, data_root, current.jar, finished)
    if scores is not None:
        aggregate = aggregate.merge(scores, on=["seed", "row"], how="left")
        summary = series_analysis.summary_with_scores(summary, scores)

    seen = st.session_state.setdefault(f"series_seen:{chosen.key}", {})
    point = _show_overview(names, aggregate, finished, chosen.key)
    point_key = None if point is None else f"{point[0]}:{point[1]}"
    if ui.new_choice(seen, "chart", point_key) is not None:
        _open_alignment(chosen, point[0], point[1], finished)

    if len(names) == 1:
        st.subheader("Best alignment of all the runs")
    else:
        st.subheader(f"Aggregate front ({len(aggregate)} alignments)")
    st.caption("Select a row or a point to see that alignment in its run.")
    row = _pick_from_table(aggregate.round(4), chosen.key)
    row_key = None if row is None else f"{row[0]}:{row[1]}"
    if ui.new_choice(seen, "table", row_key) is not None:
        _open_alignment(chosen, row[0], row[1], finished)

    with st.expander(f"Summary of the runs ({len(finished)})"):
        st.dataframe(
            series_analysis.with_statistics(summary).round(4), hide_index=True, width="stretch"
        )
    if scores is not None:
        _show_against_the_reference(chosen, data_root, current.jar, scores, finished)
    elif not reference_scores.has_reference(data_root, chosen.dataset):
        st.caption("This dataset has no reference alignment, so the runs cannot be evaluated.")
    _show_downloads(chosen, data_root, finished, aggregate, summary)


def choose_view(chosen: series.Series, remembered: runs.Run | None) -> runs.Run | None:
    """Shows what to see of a series, and the aggregate if that is the choice.

    Args:
        chosen: The series.
        remembered: A run of the series to open at once, if any.

    Returns:
        The run to show in detail; None if the aggregate was shown.
    """
    finished = series_analysis.finished_runs(chosen)
    if len(finished) < len(chosen.requests):
        st.warning(
            f"{len(finished)} of {len(chosen.requests)} runs have finished: the others are not "
            "shown."
        )
    labels = [AGGREGATE, *[_seed_label(item.seed) for item in finished]]
    widget = f"show:{chosen.key}"
    pending = st.session_state.pop(f"show_pending:{chosen.key}", None)
    if remembered is not None:
        for item in finished:
            if item.run.key == remembered.key:
                pending = _seed_label(item.seed)
    if pending in labels:
        st.session_state[widget] = pending
    if st.session_state.get(widget) not in labels:
        st.session_state[widget] = AGGREGATE
    selected = st.selectbox("Show", labels, key=widget)
    if selected == AGGREGATE:
        _show_aggregate(chosen, finished)
        return None
    return finished[labels.index(selected) - 1].run
