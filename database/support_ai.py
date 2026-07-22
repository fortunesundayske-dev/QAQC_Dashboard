"""Optional AI first-line responder for customer-support conversations."""

import os
from pathlib import Path
import re

from dotenv import load_dotenv

from database.settings import get_setting


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def automatic_reply(ticket, messages):
    api_key = str(get_setting("OPENAI_API_KEY", "")).strip()
    enabled = str(get_setting("QAQC_ENABLE_AI_SUPPORT", "false")).strip().lower() in {"1", "true", "yes"}
    if not api_key or not enabled:
        return (
            "Thanks for contacting QA/QC Support. Your request has been recorded. "
            "Please add any relevant steps, error messages, or screenshots here. "
            "Select ‘Request live admin’ if you need a person to take over."
        ), False

    from openai import OpenAI

    transcript = "\n".join(
        f"{item.get('sender_role', 'user')}: {item.get('message', '')}"
        for item in messages[-12:]
    )
    # Prevent common credentials from being forwarded to the external AI service.
    transcript = re.sub(
        r"(?i)(password|secret|api[_ -]?key|authorization|token)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        transcript,
    )[:12_000]
    response = OpenAI(api_key=api_key).responses.create(
        model=str(get_setting("OPENAI_SUPPORT_MODEL", "gpt-5-mini")),
        instructions=(
            "You are the first-line support assistant for an enterprise QA/QC dashboard. "
            "Give concise, safe troubleshooting steps based only on the conversation. "
            "Never claim to have changed accounts or data. Tell the user to request a live admin "
            "for permissions, approvals, security, data deletion, or anything requiring human action."
        ),
        input=f"Ticket category: {ticket.get('category')}\nSubject: {ticket.get('subject')}\n\n{transcript}",
    )
    text = response.output_text.strip()
    return text or "I could not generate a response. Please request a live admin.", True
