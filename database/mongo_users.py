"""MongoDB persistence and schema management for dashboard user accounts."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from pymongo import ASCENDING, MongoClient, ReplaceOne
from pymongo.errors import CollectionInvalid
from dotenv import load_dotenv

from database.settings import get_setting


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


USER_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "username", "email", "name", "role", "status", "password", "salt",
            "created_at", "discipline", "failed_attempts",
        ],
        "properties": {
            "username": {"bsonType": "string", "minLength": 1},
            "email": {"bsonType": "string", "minLength": 3},
            "name": {"bsonType": "string", "minLength": 1},
            "role": {"enum": ["admin", "user", "viewer"]},
            "status": {"enum": ["pending", "approved", "rejected", "restricted"]},
            "password": {"bsonType": "string", "minLength": 1},
            "salt": {"bsonType": "string", "minLength": 1},
            "created_at": {"bsonType": "string", "minLength": 1},
            "discipline": {"bsonType": "string"},
            "failed_attempts": {"bsonType": "int", "minimum": 0},
            "profile_photo": {"bsonType": ["string", "null"]},
            "locked_until": {"bsonType": ["string", "null"]},
            "password_iterations": {"bsonType": ["int", "null"], "minimum": 260000},
            "session_created_at": {"bsonType": ["string", "null"]},
            "session_expires_at": {"bsonType": ["string", "null"]},
            "session_last_activity_at": {"bsonType": ["string", "null"]},
        },
        "additionalProperties": True,
    }
}


def normalize_mongodb_uri(uri):
    """Normalize a common Atlas SRV/seed-list scheme mismatch."""
    value = str(uri or "").strip().strip('"').strip("'")
    if not value.startswith(("mongodb://", "mongodb+srv://")):
        raise ValueError("MONGODB_URI must start with mongodb:// or mongodb+srv://.")

    if value.startswith("mongodb+srv://"):
        authority = value[len("mongodb+srv://"):].split("/", 1)[0]
        hosts = authority.rsplit("@", 1)[-1]
        if "," in hosts:
            value = "mongodb://" + value[len("mongodb+srv://"):]
    require_tls = str(get_setting("QAQC_REQUIRE_MONGODB_TLS", "true")).strip().lower() in {"1", "true", "yes"}
    if require_tls:
        parsed = urlsplit(value)
        hosts = parsed.netloc.rsplit("@", 1)[-1].lower()
        local = all(
            host.partition(":")[0].strip("[]") in {"localhost", "127.0.0.1", "::1"}
            for host in hosts.split(",")
        )
        query = {key.lower(): [item.lower() for item in values] for key, values in parse_qs(parsed.query).items()}
        tls_disabled = query.get("tls") == ["false"] or query.get("ssl") == ["false"]
        tls_enabled = query.get("tls") == ["true"] or query.get("ssl") == ["true"]
        if tls_disabled or (value.startswith("mongodb://") and not local and not tls_enabled):
            raise ValueError("Remote MongoDB connections must explicitly enable TLS.")
    return value


def _settings():
    uri = str(get_setting("MONGODB_URI", "")).strip()
    if not uri:
        raise RuntimeError(
            "MONGODB_URI is not configured. Add it to .env locally or to "
            "Streamlit Cloud → App settings → Secrets."
        )
    database_name = str(get_setting("MONGODB_DATABASE", "qaqc_dashboard")).strip() or "qaqc_dashboard"
    return normalize_mongodb_uri(uri), database_name


@lru_cache(maxsize=1)
def get_database():
    uri, database_name = _settings()
    client = MongoClient(
        uri,
        appname="evomec-qaqc-dashboard",
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=15000,
        maxPoolSize=50,
    )
    client.admin.command("ping")
    return client[database_name]


@lru_cache(maxsize=1)
def ensure_user_schema():
    """Create or update the users collection validator and indexes."""
    database = get_database()
    try:
        database.create_collection("users", validator=USER_VALIDATOR)
    except CollectionInvalid:
        database.command("collMod", "users", validator=USER_VALIDATOR, validationLevel="strict")

    collection = database.users
    collection.create_index([("username", ASCENDING)], unique=True, name="uq_users_username")
    collection.create_index([("email", ASCENDING)], unique=True, name="uq_users_email")
    collection.create_index([("session_token_hash", ASCENDING)], sparse=True, name="ix_users_session_token")
    collection.create_index([("status", ASCENDING)], name="ix_users_status")
    return collection


def load_users():
    collection = ensure_user_schema()
    users = {}
    for document in collection.find({}):
        document.pop("_id", None)
        users[document["username"]] = document
    return users


def touch_user_session(username, token_hash, activity_at):
    """Atomically refresh one validated session without rewriting user records."""
    result = ensure_user_schema().update_one(
        {
            "username": str(username or "").strip().lower(),
            "session_token_hash": str(token_hash or ""),
            "status": "approved",
        },
        {"$set": {"session_last_activity_at": str(activity_at)}},
    )
    return result.matched_count == 1


def save_users(users):
    """Synchronize the supplied user mapping with MongoDB."""
    collection = ensure_user_schema()
    operations = []
    usernames = []
    for key, value in users.items():
        document = dict(value)
        document["username"] = str(document.get("username") or key).strip().lower()
        document["email"] = str(document.get("email", "")).strip().lower()
        document["failed_attempts"] = int(document.get("failed_attempts", 0))
        document.pop("_id", None)
        usernames.append(document["username"])
        operations.append(ReplaceOne({"username": document["username"]}, document, upsert=True))

    if operations:
        collection.bulk_write(operations, ordered=True)
    collection.delete_many({"username": {"$nin": usernames}} if usernames else {})
