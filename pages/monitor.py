"""Monitor: follow a run while it is active, cancel it, or see why it failed."""

import pandas as pd
import streamlit as st

from transept import charts, runner, runs, series, settings, ui
from transept.runs import RunState
from transept.series import SeriesState

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


def show_member(members: list[series.Member]) -> None:
    """The results of a run of a series, or why it did not finish."""
    waiting = (series.QUEUED, series.NOT_STARTED, series.DELETED)
    started = [member for member in members if member.state not in waiting]
    if not started:
        return
    labels = [member.run.run_id for member in started]
    label = st.selectbox("Run of the series", labels, key="monitor_series_member")
    chosen = started[labels.index(label)]
    if chosen.state == RunState.FINISHED.value:
        if st.button("Open the results of this run"):
            ui.select_run(chosen.run)
            st.session_state.pop(ui.SELECTED_SERIES, None)
            st.switch_page(ui.RESULTS)
    elif chosen.state == RunState.FAILED.value:
        message = runs.error_message(chosen.run)
        if message:
            st.code(message, language=None)
    else:
        st.caption(f"{chosen.run.run_id}: {chosen.state}.")


def show_series(chosen: series.Series, members: list[series.Member]) -> None:
    current = series.state(chosen)
    finished = [m for m in members if m.state == RunState.FINISHED.value]
    active = [m for m in members if m.state == RunState.RUNNING.value]
    stopped = len(members) - len(finished) - len(active)
    stopped -= sum(m.state == series.QUEUED for m in members)
    st.subheader(f"{chosen.key}: {current.value}")
    st.progress(
        len(finished) / len(members), text=f"{len(finished)} of {len(members)} runs finished"
    )
    st.plotly_chart(
        charts.series_progress_figure(
            [runs.progress(member.run) for member in finished],
            [runs.progress(member.run) for member in active],
        ),
        width="stretch",
    )
    st.caption(
        "In blue, the runs in progress; in grey, those already finished."
        + (f" {stopped} run(s) did not finish and are not shown." if stopped else "")
    )
    if current == SeriesState.RUNNING and st.button("Cancel the runs", type="secondary"):
        series.cancel(chosen)
        st.rerun(scope="app")
    if current == SeriesState.FINISHED:
        st.success("Every run has finished.")
        if st.button("Open the results", type="primary", key="open_series_results"):
            st.session_state[ui.SELECTED_SERIES] = chosen.key
            st.switch_page(ui.RESULTS)
    elif current == SeriesState.FINISHED_WITH_PROBLEMS:
        st.warning("Some runs did not finish: see them below.")
    elif current == SeriesState.CANCELLED:
        st.warning("The runs were cancelled.")
    elif current == SeriesState.STOPPED:
        st.warning("The process that launches the runs stopped before launching them all.")
    with st.expander(f"Runs ({len(members)})"):
        st.dataframe(member_table(members), hide_index=True, width="stretch")
        show_member(members)


@st.fragment(run_every=2)
def live_series(chosen: series.Series) -> None:
    show_series(chosen, series.members(chosen))
    if series.state(chosen) != SeriesState.RUNNING:
        st.rerun(scope="app")  # it has just ended: rerun the page, so that it stops refreshing


root = settings.runs_root()
followed = ui.choose_run_or_series("Run", runs.list_runs(root), series.list_series(root))
if followed is None:
    st.info("There are no runs yet.")
    st.page_link(ui.NEW_RUN, label="Launch a run", icon=":material/play_arrow:")
    st.stop()
if isinstance(followed, series.Series):
    if series.state(followed) == SeriesState.RUNNING:
        live_series(followed)
    else:
        show_series(followed, series.members(followed))
    st.stop()
run = followed


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
