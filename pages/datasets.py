"""Explore > Datasets: the repositories, their datasets and whether each one can be used."""

from pathlib import Path

import pandas as pd
import streamlit as st

from transept import dataset_check, datasets, runs, settings, ui
from transept.dataset_check import DatasetEntry, Level, Status

ALL = "All"
SELECTED = "datasets_selected"
LEVEL_MARKS = {
    Level.OK: ":green[:material/check_circle:]",
    Level.INFO: ":blue[:material/info:]",
    Level.WARNING: ":orange[:material/warning:]",
    Level.ERROR: ":red[:material/error:]",
}


def render_repository(repository: settings.Repository, current: settings.Settings) -> None:
    """A line of a repository: its name, path and number of datasets, and how to remove it."""
    columns = st.columns([2, 5, 2, 1], vertical_alignment="center")
    columns[0].markdown(f"**{repository.name}**")
    columns[1].code(repository.path, language=None)
    if settings.is_repository(repository.path):
        found = len(datasets.list_datasets(repository.path))
        columns[2].markdown(f"{found} dataset{'' if found == 1 else 's'}")
    else:
        columns[2].markdown(":red[Directory not found]")
    if repository.name != settings.EXAMPLES_NAME and columns[3].button(
        "Remove",
        key=f"remove:{repository.path}",
        help="Transept forgets this repository; its files are not touched.",
    ):
        settings.save_settings(settings.remove_repository(current, repository.path))
        st.rerun()


def render_repositories(current: settings.Settings) -> None:
    """The repositories, and the form that adds another one."""
    repositories = settings.all_repositories(current)
    with st.expander(f"Repositories ({len(repositories)})", expanded=len(repositories) == 1):
        for repository in repositories:
            render_repository(repository, current)
        with st.form("add_repository", clear_on_submit=True):
            st.markdown("**Add a directory**")
            path_column, name_column = st.columns([3, 1])
            path = path_column.text_input(
                "Path",
                placeholder="/path/to/Dataset_Structural_GPCRs/GPCRdb",
                help="A directory with the layout of the GPCR structural benchmark: its GPCRdb "
                "folder, or your own.",
            )
            name = name_column.text_input("Name (optional)")
            if st.form_submit_button("Add"):
                try:
                    settings.save_settings(settings.add_repository(current, path, name))
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.rerun()


def filter_entries(entries: list[DatasetEntry]) -> list[DatasetEntry]:
    """Shows the filters by repository, status and name, and applies them."""
    columns = st.columns(3)
    names = list(dict.fromkeys(entry.repository.name for entry in entries))
    repository = columns[0].selectbox("Repository", [ALL, *names])
    statuses = [status.value for status in Status]
    status = columns[1].selectbox("Status", [ALL, *statuses])
    text = columns[2].text_input("Filter by name", placeholder="e.g. classA").strip().lower()
    return [
        entry
        for entry in entries
        if repository in (ALL, entry.repository.name)
        and status in (ALL, entry.report.status.value)
        and text in entry.name.lower()
    ]


def entries_table(entries: list[DatasetEntry]) -> pd.DataFrame:
    """One row per dataset."""
    return pd.DataFrame(
        [
            {
                "Dataset": entry.name,
                "Repository": entry.repository.name,
                "Proteins": len(entry.report.proteins),
                "Mean length": round(entry.report.mean_length),
                "Max length": entry.report.max_length,
                "Structures": f"{entry.report.structures}/{len(entry.report.proteins)}",
                "Seed alignments": f"{entry.report.valid_seeds}/{len(entry.report.seeds)}",
                "Reference": entry.report.reference,
                "Status": entry.report.status.value,
            }
            for entry in entries
        ]
    )


def pick_entry(entries: list[DatasetEntry]) -> DatasetEntry:
    """The table of datasets; returns the one selected, or the first."""
    picked = st.dataframe(
        entries_table(entries),
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key="datasets_table:" + ",".join(f"{e.repository.path}/{e.name}" for e in entries),
    )
    rows = picked.selection.rows if picked and picked.selection else []
    if rows and rows[0] < len(entries):
        chosen = entries[rows[0]]
        st.session_state[SELECTED] = (chosen.repository.path, chosen.name)
    remembered = st.session_state.get(SELECTED)
    for entry in entries:
        if (entry.repository.path, entry.name) == remembered:
            return entry
    return entries[0]


def render_detail(entry: DatasetEntry) -> None:
    """The checklist of a dataset, what it holds and where to go from it."""
    report = entry.report
    data_root = entry.repository.path
    st.subheader(f"{entry.name} · {entry.repository.name}")
    finished = runs.finished_runs_of(settings.runs_root(), entry.name, data_root)
    actions = st.columns([2, 2, 4], vertical_alignment="center")
    if actions[0].button(
        "Optimize this dataset",
        type="primary",
        icon=":material/play_arrow:",
        disabled=report.status == Status.NOT_USABLE,
    ):
        st.session_state[ui.DATASET_TO_OPTIMIZE] = (data_root, entry.name)
        st.switch_page(ui.NEW_RUN)
    actions[1].page_link(
        ui.HISTORY, label=f"Finished runs: {len(finished)}", icon=":material/history:"
    )
    for check in report.checks:
        st.markdown(f"{LEVEL_MARKS[check.level]} **{check.name}.** {check.message}")
    proteins, seeds = st.tabs(["Proteins", "Seed alignments"])
    with proteins:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Protein": protein.id,
                        "Length": protein.length,
                        "TM helices": protein.helices,
                        "Distances": protein.structure,
                        "PDB": protein.model,
                    }
                    for protein in report.proteins
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    with seeds:
        st.caption(
            f"The internal seeds of Transept are always available. Files in {Path(data_root)}"
            f"/precomputed/{entry.name}/."
        )
        if report.seeds:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Tool": seed.tool,
                            "Valid": seed.problem is None,
                            "Problem": seed.problem or "",
                            "Known issue": seed.known_issue or "",
                        }
                        for seed in report.seeds
                    ]
                ),
                hide_index=True,
                width="stretch",
            )


st.title("Datasets")
st.write("The datasets you can align, and whether they are ready to use.")

current = settings.load_settings()
render_repositories(current)

entries = dataset_check.catalogue(settings.all_repositories(current))
if not entries:
    st.info("There are no datasets yet: add a directory above.")
    st.stop()

shown = filter_entries(entries)
if not shown:
    st.info("No dataset matches these filters.")
    st.stop()
render_detail(pick_entry(shown))
