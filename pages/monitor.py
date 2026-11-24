"""Monitor: follow a run while it is active, cancel it, or see why it failed."""

import pandas as pd
import streamlit as st

from transept import charts, convergence, runner, runs, series, settings, ui
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


def series_controls(chosen: series.Series) -> None:
    """Stop or cancel a running series."""
    stopping = (chosen.directory / series.STOP_FILE).is_file()
    buttons = st.columns(2)
    if buttons[0].button(
        "Stop and keep the results",
        disabled=stopping,
        help="The runs in progress end at their next generation and keep their results; the "
        "runs not started yet are not launched. Results analyses what there is.",
    ):
        series.stop(chosen)
        st.rerun(scope="app")
    if buttons[1].button(
        "Cancel the runs", type="secondary", help="Stops every run and keeps nothing of them."
    ):
        series.cancel(chosen)
        st.rerun(scope="app")
    if stopping:
        st.info("Stopping: the runs in progress are writing their results.")


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
    if current == SeriesState.RUNNING:
        suggest_stopping_series(active)
        series_controls(chosen)
    if current == SeriesState.FINISHED:
        st.success("Every run has finished.")
        if st.button("Open the results", type="primary", key="open_series_results"):
            st.session_state[ui.SELECTED_SERIES] = chosen.key
            st.switch_page(ui.RESULTS)
    elif current == SeriesState.FINISHED_WITH_PROBLEMS:
        st.warning("Some runs did not finish: see them below.")
    elif current == SeriesState.CANCELLED:
        st.warning("The runs were cancelled.")
    elif current == SeriesState.STOPPED_BY_USER:
        st.info(
            f"Stopped at your request: {len(finished)} of {len(members)} runs have results, some "
            "of them shorter than planned."
        )
        if finished and st.button("Open the results", type="primary", key="open_stopped_series"):
            st.session_state[ui.SELECTED_SERIES] = chosen.key
            st.switch_page(ui.RESULTS)
    elif current == SeriesState.STOPPED:
        st.warning("The process that launches the runs stopped before launching them all.")
    with st.expander(f"Runs ({len(members)})"):
        st.dataframe(member_table(members), hide_index=True, width="stretch")
        show_member(members)


def idle_generations(run: runs.Run) -> int:
    """Generations without improvement of a run, from its files."""
    population = runs.config(run).get("populationSize") or convergence.DEFAULT_POPULATION
    return convergence.generations_without_improvement(runs.progress(run), int(population))


def suggest_stopping_series(active: list[series.Member]) -> None:
    """Says how many of the runs in progress seem to have stopped improving."""
    patience = settings.load_settings().patience
    idle = sum(idle_generations(member.run) >= patience for member in active)
    if idle:
        st.info(
            f"{idle} of the {len(active)} runs in progress have not improved their best values for "
            f"{patience} generations or more.",
            icon=":material/trending_flat:",
        )


def suggest_stopping(run: runs.Run) -> None:
    """Says that a run seems to have stopped improving, without stopping it."""
    patience = settings.load_settings().patience
    idle = idle_generations(run)
    if idle >= patience and not runner.stop_requested(run.results):
        st.info(
            f"The best values have not improved for {idle} generations (notice after {patience}). "
            "You can stop now and keep the results. The rest of the front may still be improving.",
            icon=":material/trending_flat:",
        )


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
        ui.patience_input()
    if series.state(followed) == SeriesState.RUNNING:
        live_series(followed)
    else:
        show_series(followed, series.members(followed))
    st.stop()
run = followed
if runs.state(run) == RunState.RUNNING:
    ui.patience_input()


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


def run_controls(run: runs.Run) -> None:
    """Stop or cancel a running run."""
    stopping = runner.stop_requested(run.results)
    buttons = st.columns(2)
    if buttons[0].button(
        "Stop and keep the results",
        disabled=stopping,
        help="The run ends at its next generation and writes its results as if it had "
        "finished, so that you can analyse them. It cannot be repeated exactly.",
    ):
        if not runner.request_stop(run.results):
            st.warning("The search has not started yet: try again in a moment.")
        else:
            st.rerun(scope="app")
    if buttons[1].button(
        "Cancel the run", type="secondary", help="Stops the run and keeps nothing of it."
    ):
        runner.cancel(run.job)
        st.rerun(scope="app")
    if stopping:
        st.info("Stopping: the run is writing its results.")


def show_outcome(run: runs.Run, state: RunState) -> None:
    if state == RunState.RUNNING:
        suggest_stopping(run)
        run_controls(run)
    elif state == RunState.FINISHED and runs.stopped_by_user(run):
        st.success("The run was stopped at your request and kept its results.")
        if st.button("Open the results", type="primary"):
            st.switch_page(ui.RESULTS)
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
