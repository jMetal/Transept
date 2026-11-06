"""Transept: a graphical interface for Transept core.

Each page is a script under pages/; only st.session_state survives between them. The pages are
grouped by use case in transept/sections.py.
"""

import streamlit as st

from transept import ui
from transept.sections import SECTIONS

st.set_page_config(page_title="Transept", layout="wide")

navigation = st.navigation(
    {
        "": [st.Page(ui.HOME, title="Home", icon=":material/home:", default=True)],
        **{
            section.name: [
                st.Page(page.path, title=page.title, icon=page.icon)
                for page in section.available_pages
            ]
            for section in SECTIONS
            if section.available_pages
        },
    }
)
navigation.run()
