"""Helpers shared by the pages: the selected run and the navigation targets."""

from __future__ import annotations

import streamlit as st

from transept import dataset_check, runs, series, settings, tutorials
from transept.dataset_check import Level

HOME = "pages/home.py"
DATASETS = "pages/datasets.py"
ADD_DATASET = "pages/add_dataset.py"
ALGORITHMS = "pages/algorithms.py"
NEW_RUN = "pages/new_run.py"
MONITOR = "pages/monitor.py"
RESULTS = "pages/results.py"
HISTORY = "pages/history.py"

SELECTED_RUN = "selected_run"
SELECTED_SERIES = "selected_series"
DATASET_TO_OPTIMIZE = "dataset_to_optimize"
DATASET_SELECTED = "datasets_selected"
ALGORITHM_TO_USE = "algorithm_to_use"
ALGORITHM_SELECTED = "algorithms_selected"
LEVEL_MARKS = {
    Level.OK: ":green[:material/check_circle:]",
    Level.INFO: ":blue[:material/info:]",
    Level.WARNING: ":orange[:material/warning:]",
    Level.ERROR: ":red[:material/error:]",
}


def show_tutorial(tutorial: tutorials.Tutorial) -> None:
    """Shows a tutorial, with its figures."""
    for part in tutorials.parts(tutorial):
        if isinstance(part, tutorials.Figure):
            st.image(str(part.path), caption=part.caption or None)
        else:
            st.markdown(part)


def tutorial_page(tutorial: tutorials.Tutorial) -> st.Page:
    """Returns the page of a tutorial, for the menu and for links to it."""

    def show() -> None:
        show_tutorial(tutorial)

    return st.Page(
        show, title=tutorial.title, icon=":material/school:", url_path=f"tutorial-{tutorial.name}"
    )


def tutorial_pages() -> list[st.Page]:
    """Returns one page per tutorial: a new file in docs/tutorials is enough to add one."""
    return [tutorial_page(tutorial) for tutorial in tutorials.list_tutorials()]


def render_checks(report: dataset_check.DatasetReport) -> None:
    """Shows the checklist of a dataset."""
    for check in report.checks:
        st.markdown(f"{LEVEL_MARKS[check.level]} **{check.name}.** {check.message}")


def select_run(run: runs.Run) -> None:
    """Remembers a run, so that the next page opens it."""
    st.session_state[SELECTED_RUN] = (run.dataset, run.run_id)


def selected_run() -> runs.Run | None:
    """Returns the remembered run, if any."""
    key = st.session_state.get(SELECTED_RUN)
    return runs.run_of(settings.runs_root(), *key) if key else None


def choose_run(label: str, candidates: list[runs.Run]) -> runs.Run | None:
    """Shows a selector of runs, starting at the remembered one, and remembers the choice."""
    if not candidates:
        return None
    remembered = selected_run()
    keys = [run.key for run in candidates]
    index = keys.index(remembered.key) if remembered and remembered.key in keys else 0
    chosen = candidates[
        st.selectbox(label, range(len(candidates)), index=index, format_func=lambda i: keys[i])
    ]
    select_run(chosen)
    return chosen


def choose_run_or_series(
    label: str, candidates: list[runs.Run], all_series: list[series.Series]
) -> runs.Run | series.Series | None:
    """Shows a selector with one entry per single run or series, and remembers the choice.

    The runs of a series do not have entries of their own: a series counts as one, in the place of
    its newest run, and a series with no run yet comes first.

    Args:
        label: The label of the selector.
        candidates: The runs to offer, newest first.
        all_series: The series to offer.
    """
    by_key = {(item.dataset, item.series_id): item for item in all_series}
    owner = {
        (item.dataset, request.run_id): item for item in all_series for request in item.requests
    }
    entries: list[runs.Run | series.Series] = []
    started = set()
    for run in candidates:
        item = owner.get((run.dataset, run.run_id))
        if item is None:
            entries.append(run)
        elif item.key not in started:
            started.add(item.key)
            entries.append(item)
    waiting = [item for item in by_key.values() if item.key not in started]
    entries = [*waiting, *entries]
    if not entries:
        return None
    remembered_run = selected_run()
    wanted = st.session_state.get(SELECTED_SERIES)
    if remembered_run is not None and not wanted:
        member_of = owner.get((remembered_run.dataset, remembered_run.run_id))
        wanted = member_of.key if member_of else remembered_run.key
    keys = [entry.key for entry in entries]
    index = keys.index(wanted) if wanted in keys else 0
    chosen = entries[
        st.selectbox(
            label,
            range(len(entries)),
            index=index,
            format_func=lambda i: (
                f"{keys[i]} ({len(entries[i].requests)} runs)"
                if isinstance(entries[i], series.Series)
                else keys[i]
            ),
        )
    ]
    if isinstance(chosen, series.Series):
        st.session_state[SELECTED_SERIES] = chosen.key
    else:
        st.session_state.pop(SELECTED_SERIES, None)
        select_run(chosen)
    return chosen


def new_choice(seen: dict, source: str, value: int | None) -> int | None:
    """Returns the value a selection widget has just chosen, or None if it has not changed.

    Charts and tables keep their selection across reruns, so a stale selection must not override
    a newer choice made elsewhere. `seen` remembers the last value of every source.
    """
    if value == seen.get(source):
        return None
    seen[source] = value
    return value


def format_objective(name: str, value: float) -> str:
    """Formats an objective value: SOPwTP as an integer, the others with four decimals."""
    if value != value:  # NaN: the objective was not optimised
        return "-"
    return f"{value:.0f}" if name == "SOPwTP" else f"{value:.4f}"
