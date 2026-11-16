"""Results: the non-dominated alignments of a finished run, and each alignment."""

import statistics
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from transept import (
    alignment,
    analysis,
    baselines,
    charts,
    datasets,
    exports,
    front,
    generic_numbers,
    reference_scores,
    runs,
    series,
    series_view,
    settings,
    structure_chart,
    structure_export,
    superposition,
    tracks,
    tutorials,
    ui,
)
from transept.runs import RunState

DEFAULT_STRUCTURES = 5
# With this many proteins or fewer, all of them are drawn at first.
ALL_STRUCTURES_UP_TO = 8

st.title("Results")


def show_structures(rows, proteins, data_root, run, alignment_start: str) -> None:
    """Draws the proteins superposed according to the alignment, as traces of their Cα atoms.

    Args:
        alignment_start: The key of the first column shown in the Alignment tab.
    """
    st.caption(
        "The proteins superposed according to this alignment, using their aligned transmembrane "
        "residues: if the columns are right, their residues coincide in space. Each line joins "
        "the Cα atoms of a protein; drag to rotate, scroll to zoom, hover to see a residue."
    )
    available = [
        row.id
        for row in rows
        if row.id in proteins
        and datasets.structure_model_file(data_root, run.dataset, row.id).is_file()
    ]
    if len(available) < 2:
        st.info("This needs the PDB files of at least two proteins of the dataset.")
        return
    chosen = st.multiselect(
        "Proteins (the first one is the fixed one)",
        available,
        default=available
        if len(available) <= ALL_STRUCTURES_UP_TO
        else available[:DEFAULT_STRUCTURES],
        key=f"structures:{run.key}",
    )
    if len(chosen) < 2:
        st.info("Choose at least two proteins.")
        return
    by_id = {row.id: row for row in rows}
    placed, left_out = superposition.superpose(
        [
            superposition.read_structure(
                by_id[name],
                proteins[name],
                datasets.structure_model_file(data_root, run.dataset, name),
            )
            for name in chosen
        ]
    )
    if left_out:
        st.warning(
            "This alignment shares too few transmembrane residues with the first protein to "
            f"place: {', '.join(left_out)}. That is a problem of the alignment, worth looking at."
        )
    spread = superposition.column_spread(placed)
    column = None
    if spread:
        ordered = sorted(spread, key=spread.get, reverse=True)
        column = st.selectbox(
            "Column to mark, in red (the most spread first)",
            ordered,
            format_func=lambda c: f"column {c + 1}: spread {spread[c]:.2f} Å",
            key=f"structures_column:{run.key}",
        )
        values = list(spread.values())
        st.caption(
            f"{len(values)} columns are transmembrane in all these proteins; their residues are a "
            f"median of {statistics.median(values):.2f} Å from their centre."
        )
    show_others = st.toggle(
        "Show the regions outside the membrane",
        value=True,
        key=f"structures_others:{run.key}",
    )
    st.plotly_chart(structure_chart.figure(placed, column, show_others), width="stretch")
    if column is not None:
        st.markdown(f"**Residues of column {column + 1}**, the farthest from the others first")
        st.dataframe(
            [
                {
                    "protein": item.protein,
                    "residue": item.residue,
                    "distance from the centre (Å)": round(item.distance, 2),
                }
                for item in superposition.column_residues(placed, column)
            ],
            hide_index=True,
            width="stretch",
        )

        def show_in_alignment() -> None:
            # A few columns of context on the left
            st.session_state[alignment_start] = max(1, column + 1 - 10)

        st.button(
            f"Show column {column + 1} in the Alignment tab",
            on_click=show_in_alignment,
            help="Moves the Alignment tab to this column; then open that tab.",
        )
    st.dataframe(
        [
            {
                "protein": item.structure.id,
                "pairs with the first": item.pairs,
                "RMSD (Å)": round(item.rmsd, 2),
            }
            for item in placed
        ],
        hide_index=True,
        width="stretch",
    )


finished = [
    run for run in runs.list_runs(settings.runs_root()) if runs.state(run) == RunState.FINISHED
]
opened_run = None if ui.SELECTED_SERIES in st.session_state else ui.selected_run()
chosen = ui.choose_run_or_series(
    "Run",
    finished,
    [
        item
        for item in series.list_series(settings.runs_root())
        if any(
            run.dataset == item.dataset and run.run_id in {r.run_id for r in item.requests}
            for run in finished
        )
    ],
)
if chosen is None:
    st.info("There are no finished runs yet.")
    st.stop()
if isinstance(chosen, series.Series):
    run = series_view.choose_view(chosen, opened_run)
    if run is None:
        st.stop()
else:
    run = chosen

config = runs.config(run)
metadata = runs.metadata(run) or {}
if runs.stopped_by_user(run):
    planned = config.get("maxEvaluations")
    st.info(
        f"This run was stopped at your request after {metadata.get('evaluations', '?')} "
        + (f"of {planned} " if planned else "")
        + "evaluations: its alignments are those it had found by then. It cannot be repeated "
        "exactly."
    )
names = list(runs.objective_names(run))
published = runs.has_default_objectives(run)
values = runs.objective_values(run)
table = front.summarize(values)
ranked = front.ranking(values) if len(names) == 1 else None

columns = st.columns(4)
columns[0].metric("Algorithm", config.get("algorithmType", "?"))
columns[1].metric("Evaluations", metadata.get("evaluations", "?"))
columns[2].metric("Runtime", f"{metadata.get('runtimeMs', 0) / 1000:.0f} s")
if ranked is not None:
    best_value = ranked[names[0]].iloc[0] if not ranked.empty else float("nan")
    columns[3].metric(f"Best {names[0]}", ui.format_objective(names[0], best_value))
else:
    columns[3].metric("Non-dominated (distinct)", f"{len(table)} of {len(values)}")
if not published:
    st.caption("Objectives of this run: " + ", ".join(names) + ".")
if metadata.get("configuration"):
    with st.expander("Configuration of the algorithm"):
        st.code(metadata["configuration"], language=None, wrap_lines=True)
        st.caption("Repeat the run with `--configuration` and this string, and the same seed.")
if config.get("maxTimeSeconds"):
    st.caption(
        f"Stopped after {config['maxTimeSeconds']:g} s: the number of evaluations depends on the "
        "machine, so the run does not repeat exactly."
    )

missing = metadata.get("proteinsWithoutStructure") or []
if missing:
    st.warning("Proteins without structure (ignored by the lDDT): " + ", ".join(missing))
unusual = [
    s["protein"] + f" ({s['status']})"
    for s in metadata.get("structures", [])
    if s.get("status") not in ("NUMBERED", "ALIGNED")
]
if unusual:
    st.info("Structures not checked or not used: " + ", ".join(unusual))

SELECTED_ROW = f"row:{run.key}"
SEEN = f"seen:{run.key}"
SELECTOR = f"selector:{run.key}"
if SELECTED_ROW not in st.session_state:
    st.session_state[SELECTED_ROW] = (
        int(ranked["row"].iloc[0]) if ranked is not None and not ranked.empty
        else front.knee_row(table)
    )  # fmt: skip
seen = st.session_state.setdefault(SEEN, {})


def show(row: int | None) -> None:
    """Shows another alignment if a widget has just chosen it."""
    if row is not None and row != st.session_state[SELECTED_ROW]:
        st.session_state[SELECTED_ROW] = row
        st.rerun()


current = settings.load_settings()
data_root = settings.data_root_of_run(current, config.get("dataRoot"), run.dataset)
# Runs of earlier versions used the original lDDT aggregation: their values cannot be compared
# with seeds scored by the current tool.
comparable = config.get("lddtAggregation") in (None, "PAIR_MEAN")
if comparable:
    with st.spinner("Scoring the seed alignments..."):
        scores = baselines.seed_scores(
            current.jar, data_root, run.dataset, settings.runs_root(),
            config.get("mappingPolicy", "VERIFIED"),
        )  # fmt: skip
        internal = baselines.internal_seed_scores(
            current.jar, data_root, run.dataset, metadata, settings.runs_root(),
            config.get("mappingPolicy", "VERIFIED"),
        )  # fmt: skip
else:
    st.info(
        "This run used the original lDDT aggregation of an earlier version, so the seed "
        "alignments are not shown: their values would not be comparable."
    )
    scores = pd.DataFrame(columns=["method", "SOPwTP", "lDDT"])
    internal = scores
seeds = scores[scores["method"].isin(config.get("seedMethods", []))]
# The internal seeds are not in the dataset: they are scored from the files the run recorded.
if not internal.empty:
    seeds = pd.concat([seeds, internal], ignore_index=True)
# The seeds are scored with SOPwTP and lDDT: compare only the objectives the run optimised.
common = [name for name in names if name in seeds.columns]


def seeds_in_chart() -> pd.DataFrame | None:
    """The seeds to draw in the front chart, unless the user hides them."""
    shown = st.toggle(
        "Show the seed alignments",
        value=True,
        key=f"show_seeds:{run.key}",
        disabled=seeds.empty,
        help="The alignments the search started from, scored with the same objectives."
        if not seeds.empty
        else "There are no seed alignments to show for this run.",
    )
    return seeds if shown and not seeds.empty else None


compromise = None
metrics = None
if reference_scores.has_reference(data_root, run.dataset):
    with st.spinner("Comparing the alignments with the reference..."):
        metrics = reference_scores.run_scores(current.jar, data_root, run, settings.runs_root())
    if metrics is None:
        st.warning(
            "The alignments could not be compared with the reference alignment. A build of "
            "Transept core with the score command is needed: run `make core`."
        )
metric_columns = [] if metrics is None else list(reference_scores.METRICS)


def with_metrics(shown: pd.DataFrame) -> pd.DataFrame:
    """Adds the metrics against the reference to a table of alignments, keeping its order."""
    return shown if metrics is None else shown.merge(metrics, on="row", how="left")


def pick_from_table(shown: pd.DataFrame, columns: list[str], caption: str) -> None:
    """A table of solutions; selecting a row shows its alignment."""
    st.caption(caption)
    picked = st.dataframe(
        with_metrics(shown).assign(file=[f"MSASol{row}.fasta" for row in shown["row"]])[
            ["file", *columns, *metric_columns]
        ],
        hide_index=True,
        width="stretch",
        height=240,
        on_select="rerun",
        selection_mode="single-row",
        key=f"table:{run.key}",
    )
    rows_picked = picked.selection.rows if picked and picked.selection else []
    choice = int(shown["row"].iloc[rows_picked[0]]) if rows_picked else None
    show(ui.new_choice(seen, "table", choice))


if ranked is not None:
    st.subheader(f"Convergence of {names[0]}")
    st.plotly_chart(charts.progress_figure(runs.progress(run)), width="stretch")
    st.subheader("Best distinct alignments")
    pick_from_table(
        ranked,
        [names[0], "copies"],
        "The best alignment is shown first; copies counts the members of the final population "
        "with the same value. Click a row to see its alignment.",
    )
elif len(names) == 3:
    st.subheader("Non-dominated alignments")
    pairs = [(names[0], names[1]), (names[0], names[2]), (names[1], names[2])]
    views = ["3D", *(f"{a} – {b}" for a, b in pairs)]
    view = st.radio(
        "View",
        views,
        horizontal=True,
        key=f"front_view:{run.key}",
        help="The 3D view can be rotated; in a projection, click a point to see its alignment.",
    )
    if view == "3D":
        st.plotly_chart(
            charts.front3d_figure(values, table, st.session_state[SELECTED_ROW]),
            key=f"chart3d:{run.key}",
            width="stretch",
        )
    else:
        first, second = pairs[views.index(view) - 1]
        drawn_seeds = seeds_in_chart()
        event = st.plotly_chart(
            charts.front_figure(
                values,
                table,
                st.session_state[SELECTED_ROW],
                drawn_seeds,
                None,
                first,
                second,
                False,
            ),
            on_select="rerun",
            selection_mode="points",
            key=f"chart:{run.key}:{first}:{second}",
            width="stretch",
        )
        points = event.selection.points if event and event.selection else []
        clicked = points[0].get("customdata") if points else None
        if isinstance(clicked, list):
            clicked = clicked[0]
        show(ui.new_choice(seen, f"chart {view}", None if clicked is None else int(clicked)))
        if first == front.FIRST and second == front.SECOND and drawn_seeds is not None:
            st.caption(
                "The seed alignments are only in this projection: their coverage is not computed."
            )
    pick_from_table(
        table,
        [*names, "note"],
        "Non-dominated in the three objectives. In a projection, some of them can look dominated: "
        "they are better in the third objective. The knee is closest to the ideal point once every "
        "objective is scaled to [0, 1]. Click a row to see its alignment.",
    )
elif not published:
    st.subheader("Non-dominated alignments")
    pick_from_table(
        table,
        [*names, "note"],
        "This formulation has no front chart yet: choose an alignment in the table (the knee is "
        "closest to the ideal point once every objective is scaled to [0, 1]).",
    )
else:
    left, right = st.columns([3, 1])
    weight = left.slider(
        "Weight of SOPwTP in the compromise (lDDT gets the rest)",
        0.0,
        1.0,
        0.5,
        0.05,
        key=f"weight:{run.key}",
        help="0.5 gives the knee; move it to prefer sequence (1) or structure (0).",
    )
    compromise = front.weighted_compromise(table, weight)
    if right.button("Show the compromise", disabled=compromise is None):
        show(compromise)

    drawn_seeds = seeds_in_chart()
    event = st.plotly_chart(
        charts.front_figure(values, table, st.session_state[SELECTED_ROW], drawn_seeds, compromise),
        on_select="rerun",
        selection_mode="points",
        key=f"chart:{run.key}",
        width="stretch",
    )
    points = event.selection.points if event and event.selection else []
    clicked = points[0].get("customdata") if points else None
    if isinstance(clicked, list):
        clicked = clicked[0]
    show(ui.new_choice(seen, "chart", None if clicked is None else int(clicked)))

    st.subheader("Non-dominated alignments")
    st.caption("Click a point of the chart or a row of the table to see its alignment.")
    picked = st.dataframe(
        with_metrics(table).assign(file=[f"MSASol{row}.fasta" for row in table["row"]])[
            ["file", front.FIRST, front.SECOND, "note", *metric_columns]
        ],
        hide_index=True,
        width="stretch",
        height=240,
        on_select="rerun",
        selection_mode="single-row",
        key=f"table:{run.key}",
    )
    picked_rows = picked.selection.rows if picked and picked.selection else []
    table_choice = int(table["row"].iloc[picked_rows[0]]) if picked_rows else None
    show(ui.new_choice(seen, "table", table_choice))

rows = list(values.index)
st.session_state[SELECTOR] = st.session_state[SELECTED_ROW]


def follow_selector() -> None:
    st.session_state[SELECTED_ROW] = st.session_state[SELECTOR]


selected = st.selectbox(
    "Alignment",
    rows,
    key=SELECTOR,
    on_change=follow_selector,
    format_func=lambda row: (
        f"MSASol{row}: "
        + ", ".join(f"{name} {ui.format_objective(name, values.loc[row, name])}" for name in names)
    ),
)

if not seeds.empty and common:
    st.subheader(f"MSASol{selected} against the seed alignments")
    deltas = {f"Δ {name}": values.loc[selected, name] - seeds[name] for name in common}
    extra = {}
    if len(common) == len(names) and len(names) > 1:
        better = pd.concat([delta >= 0 for delta in deltas.values()], axis=1).all(axis=1)
        strictly = pd.concat([delta > 0 for delta in deltas.values()], axis=1).any(axis=1)
        extra["dominated by MSASol" + str(selected)] = better & strictly
    st.dataframe(
        seeds[["method", *common]].assign(**deltas, **extra),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Positive differences favour the selected alignment; the objectives of the seeds "
        "are computed with the configuration of the run."
    )


def show_against_the_reference(row: int) -> None:
    """The metrics of an alignment against the reference, beside what they can be compared with."""
    st.subheader(f"MSASol{row} against the reference alignment")
    chosen = metrics[metrics["row"] == row]
    if chosen.empty:
        st.info(f"MSASol{row} could not be compared with the reference alignment.")
        return
    for column, name in zip(st.columns(4), reference_scores.METRICS, strict=True):
        column.metric(name, f"{chosen[name].iloc[0]:.3f}")
    best = metrics.loc[metrics[reference_scores.PAIR_F1].idxmax()]
    seed_table = reference_scores.seed_scores(
        current.jar, data_root, run, settings.runs_root(), config.get("seedMethods", [])
    )
    comparable = seed_table[seed_table["problem"] == ""]
    rows = [
        {"alignment": f"MSASol{row} (selected)", **chosen.iloc[0][metric_columns].to_dict()},
        {
            "alignment": f"MSASol{int(best['row'])} (best of this run)",
            **best[metric_columns].to_dict(),
        },
        *[
            {"alignment": f"seed: {seed['seed']}", **seed[metric_columns].to_dict()}
            for _, seed in comparable.iterrows()
        ],
    ]
    st.dataframe(pd.DataFrame(rows).round(3), hide_index=True, width="stretch")
    st.caption(
        "The reference is only used here, to evaluate: the search does not see it, and the best of "
        "this run can only be known with a reference. Higher is better, except for the TM-gap "
        "rate. Coverage is the number of aligned pairs relative to the reference, so low values "
        "mean that the alignment leaves residues unaligned."
    )
    problems = seed_table[seed_table["problem"] != ""]
    if not problems.empty:
        st.caption("Seeds that could not be compared: " + ", ".join(problems["seed"]) + ".")


if metrics is not None:
    show_against_the_reference(selected)
elif not reference_scores.has_reference(data_root, run.dataset):
    st.caption(
        "This dataset has no reference alignment, so the alignments cannot be evaluated against "
        "one. Add it to the dataset to see Pair F1, TM-pair F1 and coverage here."
    )

path = runs.alignment_file(run, selected)
aligned = alignment.read_fasta(path)
topology = datasets.topology_file(data_root, run.dataset)
proteins = {p.id: p for p in datasets.read_topology(topology)} if topology.is_file() else {}
broken = sum(alignment.helix_gap_runs(row, proteins.get(row.id)) for row in aligned)
length = max((len(row.aligned) for row in aligned), default=0)
helices = alignment.helices(alignment.consensus(aligned, proteins))
order = [row.id for row in aligned]
MAX_SUPPORTING = 60


@st.cache_data(show_spinner=False, max_entries=8)
def cached_support(results: str, chosen: int, others: tuple[int, ...]):
    """The support of an alignment by other alignments of the run, kept between reruns."""
    folder = Path(results)
    rows = alignment.read_fasta(folder / f"MSASol{chosen}.fasta")
    others_rows = [alignment.read_fasta(folder / f"MSASol{row}.fasta") for row in others]
    found = tracks.support(rows, others_rows)
    return None if found is None else (found.column, found.residue, found.alignments)


@st.cache_data(show_spinner=False, max_entries=8)
def cached_plddt(alignment_path: str, root: str, dataset: str):
    """The AlphaFold pLDDT of every cell of an alignment, kept between reruns."""
    rows = alignment.read_fasta(alignment_path)
    models = {row.id: datasets.structure_model_file(root, dataset, row.id) for row in rows}
    return tracks.plddt(rows, proteins, {k: v for k, v in models.items() if v.is_file()})


# The other alignments of the run that support the chosen one: its distinct non-dominated
# alignments, or its best distinct ones with a single objective; at most MAX_SUPPORTING, evenly.
candidates_rows = list(ranked["row"]) if ranked is not None else list(table["row"])
others = [int(row) for row in candidates_rows if int(row) != selected]
if len(others) > MAX_SUPPORTING:
    step = len(others) / MAX_SUPPORTING
    others = [others[int(i * step)] for i in range(MAX_SUPPORTING)]
with st.spinner("Measuring the support of every column..."):
    support = cached_support(str(run.results), selected, tuple(others))
plddt_values = cached_plddt(str(path), str(data_root), run.dataset)
conserved = tracks.conservation(aligned)
column_plddt = (
    np.nanmean(np.where(np.isfinite(plddt_values), plddt_values, np.nan), axis=0)
    if np.isfinite(plddt_values).any()
    else None
)
receptors = [row.id for row in aligned]
known_receptors = tuple(sorted(r for r in receptors if generic_numbers.cached(r) is not None))


@st.cache_data(show_spinner=False, max_entries=8)
def cached_numbering(alignment_path: str, known: tuple[str, ...]):
    """The GPCRdb number of every cell, for the receptors already fetched; kept between reruns."""
    rows = alignment.read_fasta(alignment_path)
    residues = {receptor: generic_numbers.cached(receptor) for receptor in known}
    return generic_numbers.numbering(rows, proteins, residues)


numbers = cached_numbering(str(path), known_receptors) if known_receptors else None
number_cells = generic_numbers.cells_by_number(numbers) if numbers is not None else {}
structure_status = {s["protein"]: s.get("status", "") for s in metadata.get("structures", [])}


def viewer(prefix: str, agreement=None, changed=None, **extra) -> None:
    """Helix navigation, column window and the alignment drawn as HTML."""
    key = f"{prefix}:{run.key}:{selected}"

    def jump(column: int) -> None:
        st.session_state[key] = column

    buttons = st.columns(len(helices) + 1)
    buttons[0].button("Start", on_click=jump, args=(1,), key=f"jump0:{key}")
    for number, (first, _) in enumerate(helices, start=1):
        buttons[number].button(
            f"TM{number}", on_click=jump, args=(first + 1,), key=f"jump{number}:{key}"
        )
    width = st.select_slider("Columns shown", [60, 100, 150, 250], value=100, key=f"width:{key}")
    st.session_state.setdefault(key, 1)
    start = st.slider("First column", 1, max(length, 1), key=key) - 1
    st.html(alignment.render_html(aligned, proteins, start, width, agreement, changed, **extra))


st.subheader(f"Alignment MSASol{selected}")
view, per_protein, per_helix, gpcrdb_tab, comparison_tab, structures_tab = st.tabs(
    ["Alignment", "Per protein", "Per helix", "GPCRdb", "Compare", "3D"]
)

with gpcrdb_tab:
    st.caption(
        "GPCRdb gives every residue of a G protein-coupled receptor a generic number, such as "
        "3.50x50: the helix, and the position relative to the most conserved residue of that "
        "helix in the class (x.50). Residues with the same number play the same role in "
        "different receptors, so a good alignment puts them in the same column. This check does "
        "not need a reference alignment."
    )
    missing = [r for r in receptors if r not in known_receptors]
    if missing:
        st.info(
            f"The numbering of {len(missing)} of the {len(receptors)} receptors has not been "
            "fetched from GPCRdb yet. Transept asks GPCRdb (gpcrdb.org) only when you press the "
            "button, sending only the names of the receptors, and keeps the answers for later."
        )
        if st.button("Get the GPCRdb numbering", icon=":material/download:"):
            bar = st.progress(0.0, text="Asking GPCRdb...")
            fetched = generic_numbers.fetch_all(
                missing,
                lambda done, total: bar.progress(
                    done / total, text=f"Asking GPCRdb: {done} of {total} receptors"
                ),
            )
            unknown = [entry for entry, residues in fetched.items() if not residues]
            if unknown:
                st.session_state[f"gpcrdb_unknown:{run.key}"] = unknown
            st.rerun()
    unknown = st.session_state.get(f"gpcrdb_unknown:{run.key}", [])
    if unknown:
        st.warning(
            "GPCRdb did not answer for, or does not know: " + ", ".join(unknown) + ". They are "
            "left without numbers."
        )
    if number_cells:
        aligned_residues, numbered = generic_numbers.consistency(number_cells, aligned)
        st.metric(
            "Helix residues in the column of their generic number",
            f"{aligned_residues / numbered:.1%}" if numbered else "–",
            help=f"{aligned_residues} of {numbered} residues of the seven helices with a GPCRdb "
            "number are in the column where most residues with that number are.",
        )
        st.markdown("**The most conserved position of every helix (x.50)**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "position": item.generic,
                        "column": item.column + 1,
                        "receptors in that column": f"{item.aligned} of {item.receptors}",
                        "residues": item.residues,
                    }
                    for item in generic_numbers.reference_positions(number_cells, aligned)
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Residues are listed in the order of the proteins of the alignment; - means the "
            "receptor has no residue with that number. The x.50 columns are marked with the "
            "number of their helix in the GPCRdb x.50 line of the alignment."
        )
        motifs = generic_numbers.motif_rows(number_cells, aligned)
        if motifs:
            st.markdown("**Positions of well-known motifs**")
            st.dataframe(pd.DataFrame(motifs), hide_index=True, width="stretch")
            st.caption(
                "The motifs are named as in class A; in other classes the same positions hold "
                "other residues, given by the consensus. A position is in one column when every "
                "receptor with that number has its residue there."
            )

with structures_tab:
    show_structures(aligned, proteins, data_root, run, f"start:{run.key}:{selected}")

with per_protein:
    st.dataframe(
        analysis.protein_summary(aligned, proteins, structure_status).round(3),
        hide_index=True,
        width="stretch",
    )
    identity = analysis.identity_matrix(aligned)
    st.plotly_chart(charts.identity_figure(identity, order), width="stretch")

with per_helix:
    if helices:
        helix_table = analysis.helix_summary(aligned, proteins, helices)
        if support is not None:
            helix_table["support"] = tracks.helix_means(support[0], helices)
        if column_plddt is not None:
            helix_table["pLDDT"] = tracks.helix_means(column_plddt, helices)
        helix_table["conservation"] = tracks.helix_means(conserved.score, helices)
        if number_cells and len(helices) == 7:
            by_helix = generic_numbers.helix_consistency(number_cells, aligned)
            helix_table["GPCRdb consistency"] = [by_helix.get(n) for n in range(1, 8)]
        st.dataframe(
            helix_table.round(3),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "A helix is broken in a protein when a gap separates two of its transmembrane "
            "residues where most proteins have a residue, and displaced when more than 20 % of "
            "its residues fall outside the block. Insertion columns hold residues of only a "
            "minority of the proteins."
        )
    else:
        st.info("No transmembrane consensus block was found in this alignment.")

with comparison_tab:
    # The seeds as the run used them (metadata.json): internal seeds have no file in the dataset
    candidates = {
        f"seed: {entry['method']}": Path(entry["file"])
        for entry in metadata.get("seeds", [])
        if entry.get("file") and Path(entry["file"]).is_file()
    } or {
        f"seed: {tool}": datasets.seed_file(data_root, run.dataset, tool)
        for tool in config.get("seedMethods", [])
        if tool != "internal"
    }
    candidates.update(
        {f"MSASol{row}": runs.alignment_file(run, row) for row in rows if row != selected}
    )
    other_name = st.selectbox(f"Compare MSASol{selected} with", list(candidates))
    try:
        other = analysis.load_alignment(
            candidates[other_name], list(proteins.values()) if proteins else []
        )
        mine = analysis.load_alignment(path, list(proteins.values()) if proteins else [])
        result = analysis.compare(mine, other)
    except ValueError as error:
        st.error(f"The alignments cannot be compared: {error}")
    else:
        columns = st.columns(3)
        columns[0].metric("Shared residue pairs", f"{result.shared_fraction:.1%}")
        columns[1].metric(f"Pairs only in MSASol{selected}", f"{result.pairs_a - result.shared}")
        columns[2].metric(f"Pairs only in {other_name}", f"{result.pairs_b - result.shared}")
        if helices:
            st.dataframe(
                {
                    "helix": [f"TM{n}" for n in range(1, len(helices) + 1)],
                    "agreement": [round(v, 3) for v in analysis.helix_agreement(result, helices)],
                },
                hide_index=True,
            )
        st.dataframe(
            {
                "protein": [row.id for row in mine],
                "agreement": [round(float(v), 3) for v in result.protein_agreement],
            },
            hide_index=True,
            width="stretch",
            height=200,
        )
        st.caption(
            "Agreement track: green, at least 90 % of the residue pairs of the column are also "
            "aligned in the other alignment; yellow, at least 50 %; red, fewer. Residues that "
            "lost most of their partners are shaded in orange."
        )
        mine_rows = {row.id: index for index, row in enumerate(mine)}
        changed = {(mine_rows[aligned[r].id], c) for r, c in result.changed} if aligned else set()
        viewer("compare", list(result.column_agreement), changed)

COLOURINGS = {
    "Topology": None,
    "Support": "support",
    "AlphaFold confidence": "plddt",
    "Conservation": "conservation",
}

with view:
    st.caption(
        f"{len(aligned)} sequences, {length} columns; gap runs inside transmembrane helices: "
        f"{broken} (in red)."
    )
    shown_tracks = []
    if support is not None:
        shown_tracks.append(alignment.Track("Support", support[0]))
    if column_plddt is not None:
        shown_tracks.append(alignment.Track("pLDDT", column_plddt, "plddt"))
    shown_tracks.append(alignment.Track("Conservation", conserved.score))
    available = [
        name
        for name, kind in COLOURINGS.items()
        if kind is None
        or (kind == "support" and support is not None)
        or (kind == "plddt" and column_plddt is not None)
        or kind == "conservation"
    ]
    colour_by = st.segmented_control(
        "Colour residues by",
        available,
        default="Topology",
        key=f"colour_by:{run.key}",
        help="Topology shades the transmembrane residues. Support: how often the other "
        "alignments of the run keep each residue with the same partners. AlphaFold "
        "confidence: the pLDDT of each residue in its model. Conservation: of its column.",
    )
    kind = COLOURINGS.get(colour_by or "Topology")
    colour = None
    if kind == "support":
        colour = (support[1], "fraction")
    elif kind == "plddt":
        colour = (plddt_values, "plddt")
    elif kind == "conservation":
        colour = (np.tile(conserved.score, (len(aligned), 1)), "fraction")
    viewer(
        "start",
        tracks=shown_tracks,
        consensus_line=conserved.consensus,
        colour=colour,
        x50_line=generic_numbers.x50_line(number_cells, aligned, length) if number_cells else None,
    )
    guide = tutorials.tutorial_named(tutorials.RELIABILITY)
    if guide is not None:
        # Here and not on its own page, so that the alignment and the choices stay in view
        with st.expander("How to read the tracks", icon=":material/school:"):
            st.markdown(guide.text)
    st.caption(
        "Tracks: **TM consensus** marks the columns where most residues are transmembrane. "
        + (
            f"**Support**: fraction of the residue pairs of each column kept by {support[2]} "
            "other alignments of the run, from light (below 25 %) to dark blue (75 % or "
            "more). "
            if support is not None
            else "**Support** needs other alignments in the run. "
        )
        + (
            "**pLDDT**: mean AlphaFold confidence of the column, in AlphaFold's colours "
            "(orange below 50, yellow 50–70, light blue 70–90, dark blue above 90). "
            if column_plddt is not None
            else ""
        )
        + "**Conservation**: one minus the normalised entropy of the column, times its "
        "occupancy. **Consensus**: the residue of more than half of the proteins."
    )
    stem = f"{run.dataset}_{run.run_id}_MSASol{selected}"
    downloads = st.columns(4)
    downloads[0].download_button("FASTA", exports.to_fasta(aligned), file_name=f"{stem}.fasta")
    downloads[1].download_button("Clustal", exports.to_clustal(aligned), file_name=f"{stem}.aln")
    downloads[2].download_button(
        "Stockholm with topology", exports.to_stockholm(aligned, proteins), file_name=f"{stem}.sto"
    )
    downloads[3].download_button(
        "Jalview features (TM helices)",
        exports.jalview_features(proteins),
        file_name=f"{run.dataset}_tm_features.txt",
    )
    models = {
        row.id: model
        for row in aligned
        if (model := datasets.structure_model_file(data_root, run.dataset, row.id)).is_file()
    }
    if len(models) >= 2:
        st.download_button(
            "Structures for ChimeraX and PyMOL (zip)",
            lambda: exports.bundle(structure_export.files(aligned, proteins, models, stem)),
            file_name=f"{stem}_structures.zip",
            help="The structure models superposed according to this alignment, with the alignment "
            "and scripts that open them in ChimeraX (linked to the alignment) or PyMOL, with the "
            "transmembrane helices coloured. See README.txt inside.",
        )
    else:
        st.caption(
            "Structures for ChimeraX and PyMOL: this dataset needs the structure models of at "
            "least two of these proteins."
        )

    highlighted = {"selected": selected}
    if len(names) > 1:
        highlighted["knee"] = front.knee_row(table)
    if compromise is not None:
        highlighted["compromise"] = compromise
    for name in names:
        match = table[table["note"] == f"best {name}"]
        if not match.empty:
            highlighted[f"best_{name.lower()}"] = int(match["row"].iloc[0])
    files: dict[str, str | bytes] = {
        "FUN.csv": (run.results / "FUN.csv").read_bytes(),
        "tm_features.txt": exports.jalview_features(proteins),
    }
    summary = ["role,file," + ",".join(names)]
    for role, row in highlighted.items():
        if row is None:
            continue
        rows_of = alignment.read_fasta(runs.alignment_file(run, row))
        files[f"{role}_MSASol{row}.fasta"] = exports.to_fasta(rows_of)
        files[f"{role}_MSASol{row}.sto"] = exports.to_stockholm(rows_of, proteins)
        objective_values = ",".join(str(values.loc[row, name]) for name in names)
        summary.append(f"{role},MSASol{row}.fasta,{objective_values}")
    files["summary.csv"] = "\n".join(summary) + "\n"
    st.download_button(
        "Download the highlighted alignments (zip)",
        exports.bundle(files),
        file_name=f"{run.dataset}_{run.run_id}_highlighted.zip",
        help="The best alignment of each objective, the knee, the weighted compromise (when they "
        "apply) and the selected alignment, in FASTA and Stockholm, with FUN.csv, the Jalview "
        "features and a summary.",
    )
