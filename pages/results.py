"""Results: the non-dominated alignments of a finished run, and each alignment."""

import statistics
from pathlib import Path

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
    reference_scores,
    runs,
    series,
    series_view,
    settings,
    structure_chart,
    structure_export,
    superposition,
    ui,
)
from transept.runs import RunState

DEFAULT_STRUCTURES = 5

st.title("Results")


def show_structures(rows, proteins, data_root, run) -> None:
    """Draws the proteins superposed according to the alignment, as traces of their Cα atoms."""
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
        default=available[: min(DEFAULT_STRUCTURES, len(available))],
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
else:
    st.info(
        "This run used the original lDDT aggregation of an earlier version, so the seed "
        "alignments are not shown: their values would not be comparable."
    )
    scores = pd.DataFrame(columns=["method", "SOPwTP", "lDDT"])
seeds = scores[scores["method"].isin(config.get("seedMethods", []))]
# The seeds are scored with SOPwTP and lDDT: compare only the objectives the run optimised.
common = [name for name in names if name in seeds.columns]
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

    event = st.plotly_chart(
        charts.front_figure(values, table, st.session_state[SELECTED_ROW], seeds, compromise),
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
structure_status = {s["protein"]: s.get("status", "") for s in metadata.get("structures", [])}


def viewer(prefix: str, agreement=None, changed=None) -> None:
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
    st.html(alignment.render_html(aligned, proteins, start, width, agreement, changed))


st.subheader(f"Alignment MSASol{selected}")
view, per_protein, per_helix, comparison_tab, structures_tab = st.tabs(
    ["Alignment", "Per protein", "Per helix", "Compare", "3D"]
)

with structures_tab:
    show_structures(aligned, proteins, data_root, run)

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
        st.dataframe(
            analysis.helix_summary(aligned, proteins, helices).round(3),
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

with view:
    st.caption(
        f"{len(aligned)} sequences, {length} columns; gap runs inside transmembrane helices: "
        f"{broken} (in red). Transmembrane residues are shaded; the first line marks the columns "
        "where most residues are transmembrane."
    )
    viewer("start")
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
