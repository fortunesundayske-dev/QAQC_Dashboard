"""Secret lookup shared by local and Streamlit Cloud deployments."""

import os


def get_setting(name, default=""):
    value = os.getenv(name)
    if value not in (None, ""):
        return value
    try:
        import streamlit as st

        value = st.secrets.get(name, default)
    except Exception:
        value = default
    return value
