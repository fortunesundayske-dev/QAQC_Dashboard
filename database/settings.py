"""Secret lookup shared by local and Streamlit Cloud deployments."""

import os
from pathlib import Path


def get_setting(name, default=""):
    value = os.getenv(name)
    if value not in (None, ""):
        return value
    secret_file = os.getenv(f"{name}_FILE")
    if secret_file:
        try:
            path = Path(secret_file).expanduser()
            if path.is_file() and path.stat().st_size <= 64 * 1024:
                value = path.read_text(encoding="utf-8").strip()
                if value:
                    return value
        except OSError:
            pass
    try:
        import streamlit as st

        value = st.secrets.get(name, default)
    except Exception:
        value = default
    return value
