"""Create the ignored Streamlit development-secrets file without printing values."""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path

from dotenv import dotenv_values


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = BASE_DIR / ".env"
DEFAULT_OUTPUT_PATH = BASE_DIR / ".streamlit" / "secrets.toml"

SECRET_DEFAULTS = {
    "MONGODB_URI": "",
    "MONGODB_DATABASE": "qaqc_dashboard",
    "QAQC_REQUIRE_MONGODB_TLS": "true",
    "QAQC_BOOTSTRAP_ADMIN_USERNAME": "admin",
    "QAQC_BOOTSTRAP_ADMIN_EMAIL": "",
    "QAQC_BOOTSTRAP_ADMIN_PASSWORD": "",
    "CLOUDINARY_URL": "",
    "QAQC_MASTER_WORKBOOK_PUBLIC_ID": "qaqc-dashboard/data/QAQC_Master.xlsx",
    "QAQC_ACTIVITY_WORKBOOK_PUBLIC_ID": "qaqc-dashboard/activity-logs/QAQC_Activity_Log.xlsx",
    "OPENAI_API_KEY": "",
    "OPENAI_SUPPORT_MODEL": "gpt-5-mini",
    "QAQC_ENABLE_AI_SUPPORT": "false",
    "QAQC_ENV": "development",
    "QAQC_ALLOWED_HOSTS": "localhost,127.0.0.1",
    "QAQC_FORCE_HTTPS": "false",
    "QAQC_GMAIL_ADDRESS": "fortunesundayske@gmail.com",
    "QAQC_GMAIL_APP_PASSWORD": "",
    "QAQC_EXCHANGE_TENANT_ID": "",
    "QAQC_EXCHANGE_CLIENT_ID": "",
    "QAQC_EXCHANGE_CLIENT_SECRET": "",
    "QAQC_EXCHANGE_SENDER": "fortune.kpakue@evomeclimited.com",
    "QAQC_APP_URL": "https://qualitydashboard-evomec.streamlit.app/",
    "QAQC_SUPPORT_EMAIL": "fortune.kpakue@evomeclimited.com",
}


def _load_existing(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("rb") as stream:
        values = tomllib.load(stream)
    return {
        key: str(value)
        for key, value in values.items()
        if key in SECRET_DEFAULTS and value not in (None, "")
    }


def create_secrets(env_path: Path = DEFAULT_ENV_PATH, output_path: Path = DEFAULT_OUTPUT_PATH) -> list[str]:
    """Merge defaults, .env, process environment, and existing local values."""
    values = dict(SECRET_DEFAULTS)
    if env_path.exists():
        values.update(
            {
                key: str(value)
                for key, value in dotenv_values(env_path).items()
                if key in values and value not in (None, "")
            }
        )
    values.update(
        {
            key: os.environ[key]
            for key in values
            if os.environ.get(key) not in (None, "")
        }
    )
    # Preserve values entered directly into the ignored Streamlit secrets file.
    values.update(_load_existing(output_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Local Streamlit development secrets. This file is intentionally ignored by Git.",
        "# Run scripts/create_streamlit_secrets.py again to add newly supported keys.",
        "",
    ]
    lines.extend(f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in values.items())
    lines.append("")

    temporary_path = output_path.with_suffix(".toml.tmp")
    temporary_path.write_text("\n".join(lines), encoding="utf-8")
    os.replace(temporary_path, output_path)

    return [key for key, value in values.items() if value == ""]


if __name__ == "__main__":
    missing = create_secrets()
    print(f"Created local Streamlit secrets at {DEFAULT_OUTPUT_PATH}")
    if missing:
        print("Values still requiring local configuration: " + ", ".join(missing))
