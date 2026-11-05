"""Monitor: follow a run while it is active, cancel it, or see why it failed."""

import streamlit as st

from transept import charts, runner, runs, settings, ui
from transept.runs import RunState

st.title("Monitor")

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
