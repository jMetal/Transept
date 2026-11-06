"""Learn > Tutorials: the tutorials of the repository, read inside Transept."""

import streamlit as st

from transept import tutorials

available = tutorials.list_tutorials()
if not available:
    st.title("Tutorials")
    st.info("The tutorials were not found in this installation.")
    st.stop()
chosen = available[0]
if len(available) > 1:
    index = st.selectbox(
        "Tutorial", range(len(available)), format_func=lambda i: available[i].title
    )
    chosen = available[index]
st.markdown(chosen.text)
