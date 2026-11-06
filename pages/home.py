"""Home: what Transept offers, a card per page, and the paths of Java, the jar and the data."""

import streamlit as st

from transept import dataset_check, settings, tutorials, ui
from transept.sections import SECTIONS, Page, Section

CARDS_PER_ROW = 3


def render_card(section: Section, page: Page) -> None:
    """A card with what the page offers and a link to it, or a notice that it is coming."""
    with st.container(border=True, height="stretch"):
        st.caption(section.name.upper())
        st.markdown(f"#### {page.icon} {page.title}")
        st.markdown(page.description)
        if page.is_tutorials:
            for tutorial in tutorials.list_tutorials():
                st.page_link(
                    ui.tutorial_page(tutorial),
                    label=tutorial.title,
                    icon=":material/arrow_forward:",
                )
        elif page.available:
            st.page_link(page.path, label=f"Open {page.title}", icon=":material/arrow_forward:")
        else:
            st.badge("Coming soon", icon=":material/construction:", color="gray")


st.title("Transept")
st.write(
    "Multiobjective alignment of transmembrane proteins, guided by their "
    "topology and AlphaFold2 structures. Launch runs, follow them, and explore the alignments "
    "they find."
)

overview = tutorials.tutorial_named(tutorials.OVERVIEW)
if overview is not None:
    st.page_link(
        ui.tutorial_page(overview), label="New here? Read the overview", icon=":material/school:"
    )

current = settings.load_settings()
problems = settings.problems(current)
if problems:
    for problem in problems:
        st.error(problem)
else:
    entries = dataset_check.catalogue(settings.all_repositories(current))
    noun = "dataset" if len(entries) == 1 else "datasets"
    holders = len({entry.repository.path for entry in entries})
    place = "repository" if holders == 1 else "repositories"
    st.success(f"Ready: {settings.java_version()}, {len(entries)} {noun} in {holders} {place}.")

cards = [(section, page) for section in SECTIONS for page in section.pages]
for start in range(0, len(cards), CARDS_PER_ROW):
    for column, (section, page) in zip(
        st.columns(CARDS_PER_ROW), cards[start : start + CARDS_PER_ROW]
    ):
        with column:
            render_card(section, page)

with st.expander("Settings", expanded=bool(problems)):
    with st.form("settings"):
        jar = st.text_input("Transept core jar (with dependencies)", current.jar)
        if st.form_submit_button("Save"):
            settings.save_settings(settings.Settings(jar.strip(), current.repositories))
            st.rerun()
    st.page_link(ui.DATASETS, label="Add data directories in Datasets", icon=":material/dataset:")
    st.caption(f"Runs are stored in {settings.runs_root()}.")
