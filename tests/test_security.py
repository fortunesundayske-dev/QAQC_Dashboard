from datetime import timedelta
import inspect
from io import BytesIO
from types import SimpleNamespace

from PIL import Image
import pytest

import auth
import utils
from database import cloudinary_storage
from security import (
    MIN_PASSWORD_LENGTH,
    account_is_locked,
    hash_password,
    inactivity_expired,
    password_needs_upgrade,
    session_is_active,
    utc_now,
    utc_timestamp,
    valid_email,
    valid_password,
    valid_username,
    verify_password,
)


class Upload:
    def __init__(self, name, data, content_type="application/octet-stream"):
        self.name = name
        self._data = data
        self.size = len(data)
        self.type = content_type

    def getvalue(self):
        return self._data


class SessionState(dict):
    __getattr__ = dict.get

    def __setattr__(self, key, value):
        self[key] = value


def test_password_policy_and_legacy_hash_upgrade():
    password = "Unique!Project9" + "x" * max(0, MIN_PASSWORD_LENGTH - 15)
    salt = "a" * 32
    user = {"salt": salt, "password": hash_password(password, salt, 260_000)}

    assert valid_password(password)
    assert verify_password(password, user)
    assert password_needs_upgrade(user)
    assert not valid_password("short")
    assert not verify_password("x" * 257, user)


def test_identity_validation_and_time_controls():
    assert valid_username("qa.admin-1")
    assert not valid_username("../admin")
    assert valid_email("quality@example.com")
    assert not valid_email("quality@example")

    now = utc_now()
    assert account_is_locked({"locked_until": utc_timestamp(now + timedelta(minutes=1))}, now)
    assert not account_is_locked({"locked_until": utc_timestamp(now - timedelta(seconds=1))}, now)
    assert session_is_active(
        {
            "status": "approved",
            "session_token_hash": "hash",
            "session_expires_at": utc_timestamp(now + timedelta(minutes=1)),
        },
        now,
    )
    assert not session_is_active(
        {
            "status": "approved",
            "session_token_hash": "hash",
            "session_expires_at": utc_timestamp(now - timedelta(seconds=1)),
        },
        now,
    )
    assert not inactivity_expired(1_000, 1_119)
    assert inactivity_expired(1_000, 1_120)


def test_page_transition_keeps_existing_session_token(monkeypatch):
    session_state = SessionState(
        auth={"auth_token": "existing-secure-token"},
        auth_last_activity=1_000,
    )
    monkeypatch.setattr(auth.st, "session_state", session_state)

    auth._set_logged_in(
        "quality.user",
        {
            "name": "Quality User",
            "role": "user",
            "email": "quality@example.com",
            "discipline": "Quality Management",
        },
    )

    assert session_state.auth["auth_token"] == "existing-secure-token"
    assert session_state.logged_in is True


def test_primary_navigation_uses_session_preserving_page_links():
    source = inspect.getsource(utils.render_navigation)

    assert "st.page_link" in source
    assert "href=" not in source


def test_upload_validation_rejects_extension_spoofing():
    with pytest.raises(ValueError, match="complete PDF"):
        cloudinary_storage.validate_upload(Upload("report.pdf", b"MZ executable"))
    with pytest.raises(ValueError, match="spreadsheet formulas"):
        cloudinary_storage.validate_upload(
            Upload("records.csv", b"name,value\nitem,=1+1\n", "text/csv")
        )


def test_profile_upload_is_validated_and_private(monkeypatch):
    stream = BytesIO()
    Image.new("RGB", (20, 20), "blue").save(stream, format="PNG")
    uploaded = Upload("../avatar.png", stream.getvalue(), "image/png")
    captured = {}

    def fake_upload(data, **kwargs):
        captured.update(kwargs)
        return {
            "public_id": "qaqc-dashboard/profiles/user-random",
            "resource_type": "image",
            "format": "png",
            "bytes": len(data),
            "created_at": "2026-01-01T00:00:00Z",
        }

    monkeypatch.setattr(cloudinary_storage.cloudinary.uploader, "upload", fake_upload)
    result = cloudinary_storage.upload_profile_photo(uploaded, "user")

    assert captured["type"] == "authenticated"
    assert captured["public_id"].startswith("user-")
    assert result["delivery_type"] == "authenticated"
    assert "url" not in result
