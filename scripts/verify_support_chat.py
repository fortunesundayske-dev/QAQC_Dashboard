"""Verify support chat messages and live-admin escalation, then clean up."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.mongo_support import (  # noqa: E402
    add_ticket_message,
    create_ticket,
    ensure_support_schema,
    escalate_ticket,
)
from database.support_ai import automatic_reply  # noqa: E402


def main():
    collection = ensure_support_schema()
    ticket = None
    try:
        ticket = create_ticket(
            "system-chat-test",
            "test@evomec.local",
            "Support chat verification",
            "Technical issue",
            "Verify interactive support chat persistence.",
        )
        reply, used_ai = automatic_reply(ticket, ticket["messages"])
        assert add_ticket_message(ticket["ticket_id"], "Support Assistant", "assistant", reply, is_ai=used_ai)
        assert escalate_ticket(ticket["ticket_id"], "system-chat-test")
        saved = collection.find_one({"ticket_id": ticket["ticket_id"]})
        assert saved["escalated"] is True and saved["status"] == "in_progress"
        assert len(saved["messages"]) == 2
        print("Support chat messages, automatic response, and live-admin escalation verified.")
    finally:
        if ticket:
            collection.delete_one({"ticket_id": ticket["ticket_id"]})


if __name__ == "__main__":
    main()
