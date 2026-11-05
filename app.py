"""Transept: a graphical interface for Transept core.

Each page is a script under pages/; only st.session_state survives between them.
"""

import streamlit as st

from transept import ui

st.set_page_config(page_title="Transept", layout="wide")

navigation = st.navigation(
    [
        st.Page(ui.HOME, title="Home", icon=":material/home:", default=True),
        st.Page(ui.NEW_RUN, title="New run", icon=":material/play_arrow:"),
        st.Page(ui.MONITOR, title="Monitor", icon=":material/monitoring:"),
        st.Page(ui.RESULTS, title="Results", icon=":material/scatter_plot:"),
        st.Page(ui.HISTORY, title="History", icon=":material/history:"),
    ]
)
navigation.run()
