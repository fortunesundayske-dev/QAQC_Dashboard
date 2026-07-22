"""Persistent activity ledger for QA/QC Dashboard user actions."""

from datetime import datetime, timezone
from functools import lru_cache
import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import threading
import uuid
from urllib.parse import unquote, urlparse

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from pymongo import DESCENDING

from database.activity_workbook import build_activity_workbook
from database.mongo_users import get_database
from database.settings import get_setting


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


MAX_DETAIL_LENGTH = 2_000
SENSITIVE_KEYS = {"password", "salt", "secret", "token", "authorization", "cookie"}
DEFAULT_ACTIVITY_WORKBOOK_PUBLIC_ID = "qaqc-dashboard/activity-logs/QAQC_Activity_Log.xlsx"
_ARCHIVE_LOCK = threading.Lock()
DEFAULT_ACTIVITY_PAGE_SIZE = 25
MAX_ACTIVITY_PAGE_SIZE = 100
CSV_COLUMNS = (
    "occurred_at", "event_id", "username", "name", "email", "role", "action",
    "category", "page", "target", "status", "details", "cloud_archive_status",
)


def _csv_safe(value):
    """Prevent spreadsheet formula execution when an exported CSV is opened."""
    if not isinstance(value, str):
        return value
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


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


def _configure_cloudinary():
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


def _upload_activity_workbook(records):
    """Build and overwrite the single authenticated Cloudinary activity workbook."""
    _configure_cloudinary()
    public_id = str(
        get_setting("QAQC_ACTIVITY_WORKBOOK_PUBLIC_ID", DEFAULT_ACTIVITY_WORKBOOK_PUBLIC_ID)
    ).strip() or DEFAULT_ACTIVITY_WORKBOOK_PUBLIC_ID
    with tempfile.TemporaryDirectory(prefix="qaqc-activity-") as temp_dir:
        workbook_path = Path(temp_dir) / "QAQC_Activity_Log.xlsx"
        workbook_info = build_activity_workbook(records, workbook_path)
        result = cloudinary.uploader.upload(
            str(workbook_path),
            resource_type="raw",
            type="authenticated",
            public_id=public_id,
            overwrite=True,
            invalidate=True,
        )
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "version": int(result["version"]),
        "bytes": int(result.get("bytes") or 0),
        "event_ids": workbook_info["event_ids"],
        "record_count": workbook_info["record_count"],
        "sheet_names": workbook_info["sheet_names"],
    }


def sync_activity_workbook(collection=None):
    """Rebuild the Cloudinary workbook from MongoDB, the authoritative audit ledger."""
    if collection is None:
        collection = ensure_activity_log()
    with _ARCHIVE_LOCK:
        records = list(collection.find({}).sort("occurred_at", 1))
        archive = _upload_activity_workbook(records)
        event_ids = archive["event_ids"]
        if event_ids:
            collection.update_many(
                {"event_id": {"$in": event_ids}},
                {
                    "$set": {
                        "cloud_archive_status": "archived",
                        "cloud_archive_url": archive["url"],
                        "cloud_archive_public_id": archive["public_id"],
                        "cloud_archive_version": archive["version"],
                    },
                    "$unset": {"cloud_archive_error": ""},
                },
            )
        return archive


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
    collection.create_index("event_id", unique=True, name="ux_activity_event_id")
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
            sync_activity_workbook(collection)
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


def _activity_query(start_at=None, end_at=None, username=None, action=None, status=None):
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
    return query


def _serialise_activity(record):
    item = dict(record)
    item["id"] = str(item.pop("_id", ""))
    occurred_at = item.get("occurred_at")
    if isinstance(occurred_at, datetime):
        item["occurred_at"] = occurred_at.astimezone(timezone.utc).isoformat()
    return item


def list_activities(start_at=None, end_at=None, username=None, action=None, status=None, limit=5_000):
    query = _activity_query(start_at, end_at, username, action, status)
    cursor = ensure_activity_log().find(query).sort("occurred_at", DESCENDING).limit(int(limit))
    return [_serialise_activity(record) for record in cursor]


def paginate_activities(
    start_at=None, end_at=None, username=None, action=None, status=None, *, page=1,
    page_size=DEFAULT_ACTIVITY_PAGE_SIZE,
):
    """Return a stable server-side page and pagination metadata."""
    page = max(1, int(page))
    page_size = min(MAX_ACTIVITY_PAGE_SIZE, max(1, int(page_size)))
    query = _activity_query(start_at, end_at, username, action, status)
    collection = ensure_activity_log()
    total = int(collection.count_documents(query))
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    cursor = (
        collection.find(query)
        .sort([("occurred_at", DESCENDING), ("_id", DESCENDING)])
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "items": [_serialise_activity(record) for record in cursor],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "has_previous": page > 1,
        "has_next": page < total_pages,
    }


def activity_csv(start_at=None, end_at=None, username=None, action=None, status=None):
    """Create a UTF-8 CSV for the complete filtered result set."""
    records = list_activities(start_at, end_at, username, action, status, limit=100_000)
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        row = dict(record)
        row["details"] = json.dumps(row.get("details") or {}, ensure_ascii=False, default=str)
        writer.writerow({key: _csv_safe(value) for key, value in row.items()})
    return output.getvalue().encode("utf-8-sig")


def activity_filter_values():
    collection = ensure_activity_log()
    return {
        "usernames": sorted(value for value in collection.distinct("username") if value),
        "actions": sorted(value for value in collection.distinct("action") if value),
        "statuses": sorted(value for value in collection.distinct("status") if value),
    }
