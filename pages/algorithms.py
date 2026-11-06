"""Explore > Algorithms: what can be optimised with, read from the jar that runs it."""

import zipfile

import pandas as pd
import streamlit as st

from transept import algorithms, options, settings, spaces, ui
from transept.algorithms import Algorithm
from transept.parameter_form import render_parameter_space_table


def pick_algorithm(catalogue: tuple[Algorithm, ...]) -> Algorithm | None:
    """The table of algorithms; returns the one selected, if any."""
    picked = st.dataframe(
        pd.DataFrame(
            [
                {
                    "Algorithm": algorithm.name,
                    "Description": algorithm.description,
                    "Objectives": algorithm.objectives,
                    "Parallel": algorithm.parallel,
                    "Configurable": algorithm.configurable,
                    "Crossover": algorithm.uses_crossover,
                }
                for algorithm in catalogue
            ]
        ),
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key="algorithms_table",
    )
    rows = picked.selection.rows if picked and picked.selection else []
    if rows:
        st.session_state[ui.ALGORITHM_SELECTED] = catalogue[rows[0]].name
    remembered = st.session_state.get(ui.ALGORITHM_SELECTED)
    return next((item for item in catalogue if item.name == remembered), None)


def render_configuration(jar: str, algorithm: Algorithm) -> None:
    """The parameter space of a configurable algorithm and its default configuration."""
    try:
        parameters = spaces.parameter_space(jar, algorithm.name)
        default = spaces.default_configuration(jar, algorithm.name)
    except (KeyError, OSError, zipfile.BadZipFile):
        st.warning("This build of Transept core has no parameter space for this algorithm.")
        return
    st.markdown("**Parameter space**")
    render_parameter_space_table(parameters, key=f"space_{algorithm.name}")
    with st.expander("Default configuration"):
        st.code(" ".join(f"--{k} {v}" for k, v in default.items()), language=None, wrap_lines=True)


def render_algorithm(jar: str, algorithm: Algorithm) -> None:
    """What is worth knowing about an algorithm, and how to use it."""
    st.subheader(f"{algorithm.name}: {algorithm.description}")
    if st.button(
        "Use this algorithm",
        type="primary",
        icon=":material/play_arrow:",
        disabled=algorithm.name not in options.ALGORITHMS,
    ):
        st.session_state[ui.ALGORITHM_TO_USE] = algorithm.name
        st.switch_page(ui.NEW_RUN)
    labels = [options.OBJECTIVES[name][0] for name in algorithm.formulations]
    st.markdown("**Objectives:** " + "; ".join(labels) + ".")
    for note in algorithm.notes:
        st.markdown(f"- {note}")
    if algorithm.configurable:
        render_configuration(jar, algorithm)


st.title("Algorithms")
st.write(
    "What you can optimise with. The list and the parameters come from Transept core, so they are "
    "those of the version that runs your alignments."
)

current = settings.load_settings()
algorithms_tab, objectives_tab, operators_tab = st.tabs(["Algorithms", "Objectives", "Operators"])

with algorithms_tab:
    try:
        catalogue = algorithms.catalogue(current.jar)
    except algorithms.CatalogueError as error:
        st.error(f"Transept core did not give its algorithms: {error}")
        st.page_link(ui.HOME, label="Go to the settings", icon=":material/home:")
    else:
        st.caption("Select a row to see the details of an algorithm.")
        chosen = pick_algorithm(catalogue)
        if chosen is not None:
            render_algorithm(current.jar, chosen)

with objectives_tab:
    st.write("What the search maximises. None of them uses a reference alignment.")
    for name, (label, count) in options.OBJECTIVES.items():
        noun = "objective" if count == 1 else "objectives"
        st.markdown(f"**{label}** ({count} {noun})")
        st.markdown(algorithms.FORMULATION_DETAILS[name])

with operators_tab:
    st.write(
        "How the search changes alignments. No operator creates a gap inside a transmembrane "
        "helix; the seeds may have them, and **Repair the seeds** in **New run** moves them out."
    )
    st.markdown(f"**Crossover.** {algorithms.CROSSOVER}")
    st.markdown("**Mutation**")
    st.dataframe(
        pd.DataFrame(
            [
                {"Mutation": mutation, "What it does": options.DESCRIPTIONS[mutation]}
                for mutation in options.MUTATIONS
            ]
        ),
        hide_index=True,
        width="stretch",
    )
