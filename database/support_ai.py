"""Optional AI first-line responder for customer-support conversations."""

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def automatic_reply(ticket, messages):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
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
    response = OpenAI(api_key=api_key).responses.create(
        model=os.getenv("OPENAI_SUPPORT_MODEL", "gpt-5-mini"),
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
