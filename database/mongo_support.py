"""MongoDB repository for customer-support tickets."""

import secrets
from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid

from database.mongo_users import get_database


SUPPORT_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["ticket_id", "username", "email", "subject", "category", "message", "status", "created_at"],
        "properties": {
            "ticket_id": {"bsonType": "string"},
            "username": {"bsonType": "string"},
            "email": {"bsonType": "string"},
            "subject": {"bsonType": "string", "minLength": 3},
            "category": {"enum": ["Account access", "Technical issue", "Data issue", "Feature request", "Other"]},
            "message": {"bsonType": "string", "minLength": 10},
            "status": {"enum": ["open", "in_progress", "resolved", "closed"]},
            "created_at": {"bsonType": "string"},
        },
        "additionalProperties": True,
    }
}


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_support_schema():
    database = get_database()
    try:
        database.create_collection("support_tickets", validator=SUPPORT_VALIDATOR)
    except CollectionInvalid:
        database.command("collMod", "support_tickets", validator=SUPPORT_VALIDATOR, validationLevel="strict")
    collection = database.support_tickets
    collection.create_index([("ticket_id", ASCENDING)], unique=True, name="uq_support_ticket_id")
    collection.create_index([("username", ASCENDING), ("created_at", DESCENDING)], name="ix_support_user_created")
    collection.create_index([("status", ASCENDING), ("created_at", DESCENDING)], name="ix_support_status_created")
    return collection


def create_ticket(username, email, subject, category, message):
    ticket = {
        "ticket_id": f"SUP-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3).upper()}",
        "username": username,
        "email": email.strip().lower(),
        "subject": subject.strip(),
        "category": category,
        "message": message.strip(),
        "status": "open",
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
    }
    ensure_support_schema().insert_one(ticket)
    ticket.pop("_id", None)
    return ticket


def list_tickets(username=None):
    query = {"username": username} if username else {}
    return list(ensure_support_schema().find(query, {"_id": 0}).sort("created_at", DESCENDING))


def update_ticket_status(ticket_id, status, updated_by):
    if status not in {"open", "in_progress", "resolved", "closed"}:
        raise ValueError("Invalid ticket status.")
    result = ensure_support_schema().update_one(
        {"ticket_id": ticket_id},
        {"$set": {"status": status, "updated_at": _utc_now(), "updated_by": updated_by}},
    )
    return result.modified_count == 1
