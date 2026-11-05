"""Home: checks that Java, the jar and the data are available, and edits their paths."""

import streamlit as st

from transept import datasets, settings, ui

st.title("Transept")
st.write(
    "Multiobjective alignment of transmembrane proteins, guided by their "
    "topology and AlphaFold2 structures. Launch runs, follow them, and explore the alignments "
    "they find."
)

current = settings.load_settings()
problems = settings.problems(current)
if problems:
    for problem in problems:
        st.error(problem)
else:
    found = datasets.list_datasets(current.data_root)
    noun = "dataset" if len(found) == 1 else "datasets"
    st.success(f"Ready: {settings.java_version()}, {len(found)} {noun} in the data directory.")
    st.page_link(ui.NEW_RUN, label="Launch a run", icon=":material/play_arrow:")
    st.page_link(ui.HISTORY, label="Open a previous run", icon=":material/history:")

with st.expander("Settings", expanded=bool(problems)):
    with st.form("settings"):
        jar = st.text_input("Transept core jar (with dependencies)", current.jar)
        data_root = st.text_input(
            "Data directory (the examples of Transept, the GPCRdb folder of the benchmark "
            "dataset, or your own)",
            current.data_root,
        )
        if st.form_submit_button("Save"):
            settings.save_settings(settings.Settings(jar=jar.strip(), data_root=data_root.strip()))
            st.rerun()
    st.caption(f"Runs are stored in {settings.runs_root()}.")
