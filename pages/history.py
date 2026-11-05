"""History: every run with its state; open, delete (to the trash) or restore runs."""

import pandas as pd
import streamlit as st

from transept import runs, settings, ui
from transept.runs import RunState

CONFIRM_DELETE = "confirm_delete"
CONFIRM_EMPTY = "confirm_empty"

st.title("History")

root = settings.runs_root()
found = runs.list_runs(root)


def summary_table(candidates: list[runs.Run]) -> pd.DataFrame:
    rows = []
    for run in candidates:
        config = runs.config(run)
        metadata = runs.metadata(run) or {}
        runtime = metadata.get("runtimeMs")
        rows.append(
            {
                "dataset": run.dataset,
                "run": run.run_id,
                "state": runs.state(run).value,
                "algorithm": config.get("algorithmType", ""),
                "evaluations": config.get("maxEvaluations"),
                "population": config.get("populationSize"),
                "started": metadata.get("startedAt", ""),
                "runtime (s)": round(runtime / 1000) if runtime is not None else None,
            }
        )
    return pd.DataFrame(rows)


def delete(chosen: list[runs.Run]) -> None:
    remembered = ui.selected_run()
    for run in chosen:
        runs.move_to_trash(root, run)
        if remembered and remembered.key == run.key:
            st.session_state.pop(ui.SELECTED_RUN, None)
    st.session_state[CONFIRM_DELETE] = None


def show_actions(chosen: list[runs.Run]) -> None:
    if len(chosen) == 1:
        run = chosen[0]
        ui.select_run(run)
        if runs.state(run) == RunState.FINISHED:
            if st.button(f"Open the results of {run.key}", type="primary"):
                st.switch_page(ui.RESULTS)
        elif st.button(f"Monitor {run.key}", type="primary"):
            st.switch_page(ui.MONITOR)
    running = [run for run in chosen if runs.state(run) == RunState.RUNNING]
    deletable = [run for run in chosen if run not in running]
    if running:
        st.caption(
            "Running runs cannot be deleted: cancel them in the monitor first ("
            + ", ".join(run.key for run in running)
            + ")."
        )
    if deletable and st.button(f"Delete {len(deletable)} run(s)…", key="ask_delete"):
        st.session_state[CONFIRM_DELETE] = [run.key for run in deletable]
    pending = st.session_state.get(CONFIRM_DELETE)
    if pending:
        st.warning("Move to the trash: " + ", ".join(pending) + "? They can be restored below.")
        yes, no = st.columns(2)
        if yes.button("Yes, move to the trash", type="primary", key="confirm_delete_yes"):
            delete([run for run in deletable if run.key in pending])
            st.rerun()
        if no.button("Cancel", key="confirm_delete_no"):
            st.session_state[CONFIRM_DELETE] = None
            st.rerun()


if not found:
    st.info("There are no runs yet.")
    st.page_link(ui.NEW_RUN, label="Launch a run", icon=":material/play_arrow:")
else:
    event = st.dataframe(
        summary_table(found),
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="multi-row",
        key="history",
    )
    selection = event.selection.rows if event and event.selection else []
    if selection:
        show_actions([found[index] for index in selection])
    else:
        st.caption("Select one run to open it, or several to delete them.")

trashed = runs.list_trash(root)
with st.expander(f"Trash ({len(trashed)})"):
    if not trashed:
        st.caption("The trash is empty.")
    for item in trashed:
        left, right = st.columns([4, 1])
        left.write(f"{item.key} (deleted {item.deleted_at})")
        if right.button("Restore", key=f"restore:{item.path.name}"):
            try:
                runs.restore(root, item)
            except FileExistsError as error:
                st.error(str(error))
            else:
                st.rerun()
    if trashed:
        if st.button("Empty the trash…", key="ask_empty"):
            st.session_state[CONFIRM_EMPTY] = True
        if st.session_state.get(CONFIRM_EMPTY):
            st.warning(f"Delete {len(trashed)} run(s) for good? This cannot be undone.")
            yes, no = st.columns(2)
            if yes.button("Yes, empty the trash", type="primary", key="confirm_empty_yes"):
                runs.empty_trash(root)
                st.session_state[CONFIRM_EMPTY] = False
                st.rerun()
            if no.button("Cancel", key="confirm_empty_no"):
                st.session_state[CONFIRM_EMPTY] = False
                st.rerun()
