"""Transept: a graphical interface for Transept core.

Each page is a script under pages/; only st.session_state survives between them. The pages are
grouped by use case in transept/sections.py.
"""

import streamlit as st

from transept import ui
from transept.sections import SECTIONS, Section

st.set_page_config(page_title="Transept", layout="wide")


def menu_pages(section: Section) -> list[st.Page]:
    """The entries of a section in the menu: its pages, and one per tutorial."""
    entries = []
    for page in section.available_pages:
        if page.is_tutorials:
            entries += ui.tutorial_pages()
        else:
            entries.append(st.Page(page.path, title=page.title, icon=page.icon))
    return entries


menu = {section.name: menu_pages(section) for section in SECTIONS}
navigation = st.navigation(
    {
        "": [st.Page(ui.HOME, title="Home", icon=":material/home:", default=True)],
        **{name: entries for name, entries in menu.items() if entries},
    }
)
navigation.run()
