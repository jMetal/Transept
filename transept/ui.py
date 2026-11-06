"""Helpers shared by the pages: the selected run and the navigation targets."""

from __future__ import annotations

import streamlit as st

from transept import dataset_check, runs, settings
from transept.dataset_check import Level

HOME = "pages/home.py"
DATASETS = "pages/datasets.py"
ADD_DATASET = "pages/add_dataset.py"
ALGORITHMS = "pages/algorithms.py"
NEW_RUN = "pages/new_run.py"
MONITOR = "pages/monitor.py"
RESULTS = "pages/results.py"
HISTORY = "pages/history.py"
TUTORIALS = "pages/tutorials.py"

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
