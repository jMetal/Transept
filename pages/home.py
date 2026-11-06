"""Home: what Transept offers, a card per page, and the paths of Java, the jar and the data."""

import streamlit as st

from transept import datasets, settings
from transept.sections import SECTIONS, Page, Section

CARDS_PER_ROW = 3


def render_card(section: Section, page: Page) -> None:
    """A card with what the page offers and a link to it, or a notice that it is coming."""
    with st.container(border=True, height="stretch"):
        st.caption(section.name.upper())
        st.markdown(f"#### {page.icon} {page.title}")
        st.markdown(page.description)
        if page.available:
            st.page_link(page.path, label=f"Open {page.title}", icon=":material/arrow_forward:")
        else:
            st.badge("Coming soon", icon=":material/construction:", color="gray")


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
        data_root = st.text_input(
            "Data directory (the examples of Transept, the GPCRdb folder of the benchmark "
            "dataset, or your own)",
            current.data_root,
        )
        if st.form_submit_button("Save"):
            settings.save_settings(settings.Settings(jar=jar.strip(), data_root=data_root.strip()))
            st.rerun()
    st.caption(f"Runs are stored in {settings.runs_root()}.")
