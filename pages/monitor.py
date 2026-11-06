"""Monitor: follow a run while it is active, cancel it, or see why it failed."""

import pandas as pd
import streamlit as st

from transept import charts, runner, runs, series, settings, ui
from transept.runs import RunState
from transept.series import SeriesState

VIEW = "monitor_view"
A_RUN = "A run"
A_SERIES = "A series"
OPEN_RESULTS = "monitor_open_results"

if st.session_state.pop(OPEN_RESULTS, False):
    st.switch_page(ui.RESULTS)

st.title("Monitor")


def member_table(members: list[series.Member]) -> pd.DataFrame:
    """One row per run of a series, with its progress and its best values."""
    rows = []
    for member in members:
        records = runs.progress(member.run)
        row = {"seed": member.seed, "run": member.run.run_id, "state": member.state}
        if not records.empty:
            last = records.iloc[-1]
            row["evaluations"] = int(last["evaluations"])
            row["seconds"] = round(float(last["seconds"]))
            for name in records.columns:
                if name not in ("evaluations", "seconds"):
                    row[f"best {name}"] = float(last[name])
        rows.append(row)
    return pd.DataFrame(rows)


def follow_run(run: runs.Run, finished: bool) -> None:
    """Switches the page from a series to one of its runs, before the widgets are created."""
    ui.select_run(run)
    st.session_state.pop(ui.SELECTED_SERIES, None)
    st.session_state[VIEW] = A_RUN
    st.session_state[OPEN_RESULTS] = finished


def open_member(members: list[series.Member]) -> None:
    """Goes to the results or the monitor of a run of a series."""
    waiting = (series.QUEUED, series.NOT_STARTED, series.DELETED)
    started = [member for member in members if member.state not in waiting]
    if not started:
        return
    labels = [member.run.run_id for member in started]
    columns = st.columns([3, 1], vertical_alignment="bottom")
    label = columns[0].selectbox("Run of the series", labels, key="monitor_series_member")
    chosen = started[labels.index(label)]
    finished = chosen.state == RunState.FINISHED.value
    if columns[1].button(
        "Open the results" if finished else "Monitor this run",
        on_click=follow_run,
        args=(chosen.run, finished),
    ):
        st.rerun(scope="app")  # inside a fragment, the rest of the page has to change too


def show_series(chosen: series.Series, members: list[series.Member]) -> None:
    current = series.state(chosen)
    done = sum(m.state == RunState.FINISHED.value for m in members)
    st.subheader(f"{chosen.key}: {current.value}")
    st.progress(done / len(members), text=f"{done} of {len(members)} runs finished")
    st.dataframe(member_table(members), hide_index=True, width="stretch")
    if current == SeriesState.RUNNING and st.button("Cancel the series", type="secondary"):
        series.cancel(chosen)
        st.rerun(scope="app")
    if current == SeriesState.FINISHED:
        st.success("Every run of the series has finished.")
    elif current == SeriesState.FINISHED_WITH_PROBLEMS:
        st.warning("Some runs of the series did not finish: open them to see why.")
    elif current == SeriesState.CANCELLED:
        st.warning("The series was cancelled.")
    elif current == SeriesState.STOPPED:
        st.warning("The series stopped before launching all its runs (its process is gone).")
    open_member(members)


@st.fragment(run_every=2)
def live_series(chosen: series.Series) -> None:
    show_series(chosen, series.members(chosen))
    if series.state(chosen) != SeriesState.RUNNING:
        st.rerun(scope="app")  # it has just ended: rerun the page, so that it stops refreshing


all_series = series.list_series(settings.runs_root())
if all_series:
    wanted_series = st.session_state.get(ui.SELECTED_SERIES)
    if VIEW not in st.session_state:
        st.session_state[VIEW] = A_SERIES if wanted_series else A_RUN
    view = st.segmented_control("Follow", [A_RUN, A_SERIES], key=VIEW) or A_RUN
    if view == A_SERIES:
        keys = [item.key for item in all_series]
        index = keys.index(wanted_series) if wanted_series in keys else 0
        chosen_series = all_series[
            st.selectbox("Series", range(len(keys)), index=index, format_func=lambda i: keys[i])
        ]
        st.session_state[ui.SELECTED_SERIES] = chosen_series.key
        if series.state(chosen_series) == SeriesState.RUNNING:
            live_series(chosen_series)
        else:
            show_series(chosen_series, series.members(chosen_series))
        st.stop()

candidates = runs.list_runs(settings.runs_root())
run = ui.choose_run("Run", candidates)
if run is None:
    st.info("There are no runs yet.")
    st.page_link(ui.NEW_RUN, label="Launch a run", icon=":material/play_arrow:")
    st.stop()


def show_progress(run: runs.Run, state: RunState) -> None:
    config = runs.config(run)
    records = runs.progress(run)
    total = int(config.get("maxEvaluations") or 0)
    seconds = float(config.get("maxTimeSeconds") or 0)
    done = int(records["evaluations"].iloc[-1]) if not records.empty else 0
    elapsed = float(records["seconds"].iloc[-1]) if not records.empty else 0.0
    if state == RunState.FINISHED:
        done = total or done
        elapsed = seconds or elapsed
    st.subheader(f"{run.key}: {state.value}")
    seeds = ", ".join(config.get("seedMethods", []))
    st.caption(f"{config.get('algorithmType', '?')}, seeds: {seeds}")
    if seconds:
        st.progress(
            min(elapsed / seconds, 1.0),
            text=f"{elapsed:.0f} of {seconds:.0f} s ({done} evaluations so far)",
        )
    elif total:
        st.progress(min(done / total, 1.0), text=f"{done} of {total} evaluations")
    if not records.empty:
        last = records.iloc[-1]
        names = [name for name in records.columns if name not in ("evaluations", "seconds")]
        columns = st.columns(1 + len(names))
        columns[0].metric("Elapsed", f"{last['seconds']:.0f} s")
        for column, name in zip(columns[1:], names, strict=True):
            column.metric(f"Best {name}", ui.format_objective(name, last[name]))
        st.plotly_chart(charts.progress_figure(records), width="stretch")


def show_outcome(run: runs.Run, state: RunState) -> None:
    if state == RunState.RUNNING:
        if st.button("Cancel the run", type="secondary"):
            runner.cancel(run.job)
            st.rerun(scope="app")
    elif state == RunState.FINISHED:
        st.success("The run has finished.")
        if st.button("Open the results", type="primary"):
            st.switch_page(ui.RESULTS)
    elif state == RunState.FAILED:
        st.error("The run failed.")
        message = runs.error_message(run)
        if message:
            st.code(message, language=None)
    elif state == RunState.CANCELLED:
        st.warning("The run was cancelled.")
    else:
        st.warning("The run stopped before finishing (the process is gone).")


@st.fragment(run_every=2 if runs.state(run) == RunState.RUNNING else None)
def live(run: runs.Run) -> None:
    state = runs.state(run)
    show_progress(run, state)
    show_outcome(run, state)
    if state != RunState.RUNNING and st.session_state.get("monitor_running") == run.key:
        # The run has just ended: rerun the page, so that it stops refreshing.
        st.session_state["monitor_running"] = None
        st.rerun(scope="app")
    if state == RunState.RUNNING:
        st.session_state["monitor_running"] = run.key


live(run)
