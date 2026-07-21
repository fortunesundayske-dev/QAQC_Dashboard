"""Persistent activity ledger for QA/QC Dashboard user actions."""

from datetime import datetime, timezone
from functools import lru_cache
import json
from pathlib import Path
import uuid
from urllib.parse import unquote, urlparse

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from pymongo import DESCENDING

from database.mongo_users import get_database
from database.settings import get_setting


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


MAX_DETAIL_LENGTH = 2_000
SENSITIVE_KEYS = {"password", "salt", "secret", "token", "authorization", "cookie"}


def _utc_now():
    return datetime.now(timezone.utc)


def _safe_details(details):
    if not details:
        return {}
    if not isinstance(details, dict):
        details = {"message": str(details)}
    safe = {}
    for key, value in details.items():
        normalized = str(key).strip().lower()
        if any(secret in normalized for secret in SENSITIVE_KEYS):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            safe[str(key)] = value
        else:
            safe[str(key)] = json.dumps(value, default=str)
    encoded = json.dumps(safe, default=str)
    if len(encoded) > MAX_DETAIL_LENGTH:
        return {"summary": encoded[:MAX_DETAIL_LENGTH] + "..."}
    return safe


def _upload_activity_record(record):
    """Archive an event without depending on another application module's import state."""
    cloudinary_url = str(get_setting("CLOUDINARY_URL", "")).strip()
    if not cloudinary_url:
        raise RuntimeError("CLOUDINARY_URL is not configured.")
    parsed_url = urlparse(cloudinary_url)
    if parsed_url.scheme != "cloudinary" or not all(
        [parsed_url.hostname, parsed_url.username, parsed_url.password]
    ):
        raise RuntimeError("CLOUDINARY_URL is invalid.")
    cloudinary.config(
        cloud_name=parsed_url.hostname,
        api_key=unquote(parsed_url.username),
        api_secret=unquote(parsed_url.password),
        secure=True,
    )
    occurred_at = record["occurred_at"]
    event_id = str(record.get("event_id") or uuid.uuid4().hex)
    payload = dict(record)
    payload.pop("_id", None)
    payload["occurred_at"] = occurred_at.isoformat()
    content = json.dumps(payload, default=str, sort_keys=True, indent=2).encode("utf-8")
    public_id = (
        f"qaqc-dashboard/activity-logs/{occurred_at:%Y/%m/%d}/{event_id}.json"
    )
    result = cloudinary.uploader.upload(
        content,
        resource_type="raw",
        type="authenticated",
        public_id=public_id,
        overwrite=False,
    )
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
    }


@lru_cache(maxsize=1)
def ensure_activity_log():
    collection = get_database().activity_log
    collection.create_index([("occurred_at", DESCENDING)], name="ix_activity_occurred_at")
    collection.create_index(
        [("username", DESCENDING), ("occurred_at", DESCENDING)],
        name="ix_activity_user_time",
    )
    collection.create_index(
        [("action", DESCENDING), ("occurred_at", DESCENDING)],
        name="ix_activity_action_time",
    )
    return collection


def record_activity(
    action,
    *,
    category="general",
    page="",
    target="",
    status="success",
    details=None,
    actor=None,
):
    """Append an audit event. Logging failures never interrupt the user action."""
    try:
        if actor is None:
            import streamlit as st

            actor = st.session_state.get("auth") or {}
        document = {
            "event_id": uuid.uuid4().hex,
            "occurred_at": _utc_now(),
            "username": str(actor.get("username") or "anonymous"),
            "name": str(actor.get("name") or "Anonymous"),
            "email": str(actor.get("email") or ""),
            "role": str(actor.get("role") or "anonymous"),
            "action": str(action or "activity"),
            "category": str(category or "general"),
            "page": str(page or ""),
            "target": str(target or ""),
            "status": str(status or "success"),
            "details": _safe_details(details),
            "cloud_archive_status": "pending",
        }
        collection = ensure_activity_log()
        result = collection.insert_one(document)
        try:
            archive = _upload_activity_record(document)
            collection.update_one(
                {"_id": result.inserted_id},
                {"$set": {
                    "cloud_archive_status": "archived",
                    "cloud_archive_url": archive["url"],
                    "cloud_archive_public_id": archive["public_id"],
                }},
            )
        except Exception as exc:
            collection.update_one(
                {"_id": result.inserted_id},
                {"$set": {
                    "cloud_archive_status": "failed",
                    "cloud_archive_error": f"{type(exc).__name__}: {exc}",
                }},
            )
        return True
    except Exception:
        return False


def list_activities(start_at=None, end_at=None, username=None, action=None, status=None, limit=5_000):
    query = {}
    if start_at or end_at:
        query["occurred_at"] = {}
        if start_at:
            query["occurred_at"]["$gte"] = start_at
        if end_at:
            query["occurred_at"]["$lt"] = end_at
    if username:
        query["username"] = username
    if action:
        query["action"] = action
    if status:
        query["status"] = status
    cursor = ensure_activity_log().find(query).sort("occurred_at", DESCENDING).limit(int(limit))
    records = []
    for record in cursor:
        record["id"] = str(record.pop("_id"))
        records.append(record)
    return records


def activity_filter_values():
    collection = ensure_activity_log()
    return {
        "usernames": sorted(value for value in collection.distinct("username") if value),
        "actions": sorted(value for value in collection.distinct("action") if value),
        "statuses": sorted(value for value in collection.distinct("status") if value),
    }
