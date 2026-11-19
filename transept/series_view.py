"""Results of independent runs: the aggregate of all of them, or one of them."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

from transept import (
    charts,
    datasets,
    ensemble,
    exports,
    front,
    generic_numbers,
    reference_scores,
    runs,
    series,
    series_analysis,
    settings,
    ui,
)
from transept.series_analysis import FinishedRun

AGGREGATE = "All runs (aggregate)"
GPCRDB = "GPCRdb consistency"


@dataclass(slots=True, frozen=True)
class View:
    """What Results shows of a series.

    Attributes:
        run: The run to show.
        seed: Its random seed.
        row: In the aggregate, the alignment of the run to analyse; None to show the whole run.
    """

    run: runs.Run
    seed: int
    row: int | None = None


def _pick_key(chosen: series.Series) -> str:
    return f"aggregate_pick:{chosen.key}"


def _pick(chosen: series.Series, seed: int, row: int) -> None:
    """Chooses an alignment of the aggregate to analyse below it."""
    if st.session_state.get(_pick_key(chosen)) != (seed, row):
        st.session_state[_pick_key(chosen)] = (seed, row)
        st.rerun()


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


@st.cache_data(show_spinner=False, max_entries=4)
def _cached_summary(paths: tuple[str, ...], knee: int, topology: str):
    """How much the alignments of the aggregate front agree, kept between reruns."""
    return series_analysis.aggregate_summary(
        [Path(path) for path in paths], knee, _proteins(topology)
    )


@st.cache_data(show_spinner=False, max_entries=4)
def _cached_consistency(paths: tuple[str, ...], topology: str, known: tuple[str, ...]):
    """The GPCRdb consistency of the alignments, kept while the receptors fetched do not change."""
    return series_analysis.gpcrdb_consistency([Path(path) for path in paths], _proteins(topology))


def _proteins(topology: str) -> dict[str, datasets.Protein]:
    path = Path(topology)
    return {p.id: p for p in datasets.read_topology(path)} if path.is_file() else {}


def _gpcrdb_consistency(paths: list[Path], topology: Path) -> list[float | None] | None:
    """The GPCRdb consistency of every alignment, once the numbering of every receptor is kept."""
    receptors = list(_proteins(str(topology)))
    known = tuple(sorted(r for r in receptors if generic_numbers.cached(r) is not None))
    if not receptors or len(known) < len(receptors):
        return None
    return _cached_consistency(tuple(str(path) for path in paths), str(topology), known)


def _compare_knee_and_medoid(
    chosen: series.Series,
    aggregate: pd.DataFrame,
    summary: ensemble.FrontSummary,
    knee: int,
    finished: list[FinishedRun],
) -> None:
    """The knee and the medoid of the aggregate side by side; a button opens each in its run."""
    names = [c for c in (front.FIRST, front.SECOND) if c in aggregate.columns]
    extra = [c for c in (GPCRDB, reference_scores.PAIR_F1) if c in aggregate.columns]
    rows = []
    for label, position in (("knee", knee), ("medoid", summary.medoid)):
        entry = aggregate.iloc[position]
        rows.append(
            {
                "alignment": label,
                "seed": int(entry["seed"]),
                "file": f"MSASol{int(entry['row'])}.fasta",
                **{name: entry[name] for name in names},
                "agreement with the front": summary.mean_agreement[position],
                "support in the helices": summary.helix_support.get(position),
                **{name: entry[name] for name in extra},
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(
        "The **knee** of the aggregate is the balanced point of the trade-off over all the runs; "
        "the **medoid** is the alignment that agrees most with all the others of the aggregate "
        "front, a consensus of the runs that is still an alignment found by the search. Compare "
        "them with what does not need a reference (GPCRdb consistency appears once the numbering "
        "has been fetched in the GPCRdb tab of any alignment)"
        + (
            "; the Pair F1 against the reference is only for information."
            if reference_scores.PAIR_F1 in extra
            else "."
        )
    )
    buttons = st.columns(2)
    for column, (label, position) in zip(buttons, (("knee", knee), ("medoid", summary.medoid))):
        if column.button(f"Show the {label}", key=f"series_{label}:{chosen.key}"):
            entry = aggregate.iloc[position]
            _pick(chosen, int(entry["seed"]), int(entry["row"]))


def _show_agreement(
    chosen: series.Series, aggregate: pd.DataFrame, finished: list[FinishedRun], topology: Path
) -> pd.DataFrame:
    """How much the aggregate front agrees, and its knee and medoid; returns the aggregate with
    the medoid marked."""
    knee = series_analysis.knee_position(aggregate, [front.FIRST, front.SECOND])
    if knee is None or len(aggregate) < 2:
        return aggregate
    paths = series_analysis.alignment_paths(finished, aggregate)
    with st.spinner(f"Comparing the {len(aggregate)} alignments of the aggregate front..."):
        summary = _cached_summary(tuple(str(path) for path in paths), knee, str(topology))
    if summary is None:
        return aggregate
    contributing = aggregate["seed"].nunique()
    st.info(
        ensemble.describe(
            summary,
            f"the aggregate front (from {contributing} of the {len(finished)} runs)",
        ),
        icon=":material/join:",
    )
    if summary.medoid == knee:
        st.caption("The knee is also the medoid: the alignment that agrees most with the others.")
        return aggregate
    aggregate = aggregate.copy()
    if aggregate.iloc[summary.medoid]["note"] == "":
        aggregate.iloc[summary.medoid, aggregate.columns.get_loc("note")] = "medoid"
    with st.expander("Knee or medoid?", icon=":material/compare_arrows:"):
        _compare_knee_and_medoid(chosen, aggregate, summary, knee, finished)
    return aggregate


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
            "of all the runs together. The knee, closest to the ideal point once both objectives "
            "are scaled, is a place to start, not a validated recommendation."
        )
        return point
    return None


def _show_aggregate(chosen: series.Series, finished: list[FinishedRun]) -> View | None:
    """Shows the aggregate and returns the alignment of it to analyse: the one picked, else its
    knee (or its best, with one objective); None if it is empty."""
    current = settings.load_settings()
    names = list(finished[0].values.columns)
    data_root = settings.data_root_of_run(current, chosen.data_root, chosen.dataset)
    aggregate = series_analysis.aggregate_front(finished)
    summary = series_analysis.run_summary(finished)
    scores = _reference_metrics(chosen, data_root, current.jar, finished)
    if scores is not None:
        aggregate = aggregate.merge(scores, on=["seed", "row"], how="left")
        summary = series_analysis.summary_with_scores(summary, scores)

    topology = datasets.topology_file(data_root, chosen.dataset)
    consistency = _gpcrdb_consistency(
        series_analysis.alignment_paths(finished, aggregate), topology
    )
    if consistency is not None:
        aggregate = aggregate.assign(**{GPCRDB: consistency})

    seen = st.session_state.setdefault(f"series_seen:{chosen.key}", {})
    point = _show_overview(names, aggregate, finished, chosen.key)
    point_key = None if point is None else f"{point[0]}:{point[1]}"
    if ui.new_choice(seen, "chart", point_key) is not None:
        _pick(chosen, point[0], point[1])
    if tuple(names) == (front.FIRST, front.SECOND):
        aggregate = _show_agreement(chosen, aggregate, finished, topology)

    if len(names) == 1:
        st.subheader("Best alignment of all the runs")
    else:
        st.subheader(f"Aggregate front ({len(aggregate)} alignments)")
    st.caption("Select a row or a point to analyse that alignment below the summary of the runs.")
    row = _pick_from_table(aggregate.round(4), chosen.key)
    row_key = None if row is None else f"{row[0]}:{row[1]}"
    if ui.new_choice(seen, "table", row_key) is not None:
        _pick(chosen, row[0], row[1])

    with st.expander(f"Summary of the runs ({len(finished)})"):
        st.dataframe(
            series_analysis.with_statistics(summary).round(4), hide_index=True, width="stretch"
        )
    if scores is not None:
        _show_against_the_reference(chosen, data_root, current.jar, scores, finished)
    elif not reference_scores.has_reference(data_root, chosen.dataset):
        st.caption("This dataset has no reference alignment, so the runs cannot be evaluated.")
    _show_downloads(chosen, data_root, finished, aggregate, summary)
    return _analysed(chosen, aggregate, names, finished)


def _analysed(
    chosen: series.Series, aggregate: pd.DataFrame, names: list[str], finished: list[FinishedRun]
) -> View | None:
    """The alignment of the aggregate to analyse, with a way to open it in its run."""
    if aggregate.empty:
        return None
    pairs = list(zip(aggregate["seed"].astype(int), aggregate["row"].astype(int)))
    picked = st.session_state.get(_pick_key(chosen))
    if picked not in pairs:
        knee = series_analysis.knee_position(aggregate, names) if len(names) > 1 else 0
        picked = pairs[knee if knee is not None else 0]
    seed, row = picked
    st.divider()
    left, right = st.columns([3, 1], vertical_alignment="bottom")
    note = aggregate.iloc[pairs.index(picked)]["note"]
    left.markdown(
        f"**Analysing MSASol{row} of seed {seed}**"
        + (f" ({note} of the aggregate)" if note else "")
        + ": choose another one in the chart or the table above."
    )
    if right.button("Open it in its run", key=f"open_in_run:{chosen.key}"):
        _open_alignment(chosen, seed, row, finished)
    run = next(item.run for item in finished if item.seed == seed)
    return View(run, seed, row)


def choose_view(chosen: series.Series, remembered: runs.Run | None) -> View | None:
    """Shows what to see of a series, and the aggregate if that is the choice.

    Args:
        chosen: The series.
        remembered: A run of the series to open at once, if any.

    Returns:
        The run to show; in the aggregate, with the alignment of it to analyse. None if there is
        nothing to show.
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
        return _show_aggregate(chosen, finished)
    item = finished[labels.index(selected) - 1]
    return View(item.run, item.seed)
