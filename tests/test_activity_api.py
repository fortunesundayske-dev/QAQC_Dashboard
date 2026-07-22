from datetime import date, datetime, timedelta, timezone
import csv
from io import StringIO

from fastapi.testclient import TestClient

import activity_api
from database import audit_log


class FakeCursor:
    def __init__(self, records):
        self.records = list(records)

    def sort(self, *_args):
        self.records.sort(key=lambda item: item["occurred_at"], reverse=True)
        return self

    def skip(self, amount):
        self.records = self.records[amount:]
        return self

    def limit(self, amount):
        self.records = self.records[:amount]
        return self

    def __iter__(self):
        return iter(self.records)


class FakeCollection:
    def __init__(self, records):
        self.records = records

    def find(self, _query):
        return FakeCursor(self.records)

    def count_documents(self, _query):
        return len(self.records)


def test_paginate_activity_uses_server_side_page(monkeypatch):
    records = [
        {"_id": str(index), "occurred_at": datetime(2026, 7, index, tzinfo=timezone.utc)}
        for index in range(1, 6)
    ]
    monkeypatch.setattr(audit_log, "ensure_activity_log", lambda: FakeCollection(records))

    result = audit_log.paginate_activities(page=2, page_size=2)

    assert [item["id"] for item in result["items"]] == ["3", "2"]
    assert result | {"items": []} == {
        "items": [], "page": 2, "page_size": 2, "total": 5, "total_pages": 3,
        "has_previous": True, "has_next": True,
    }


def test_csv_has_excel_bom_and_json_details(monkeypatch):
    record = {
        "_id": "1", "occurred_at": datetime(2026, 7, 21, tzinfo=timezone.utc),
        "username": "admin", "details": {"note": "checked"},
    }
    monkeypatch.setattr(audit_log, "ensure_activity_log", lambda: FakeCollection([record]))

    payload = audit_log.activity_csv()
    rows = list(csv.DictReader(StringIO(payload.decode("utf-8-sig"))))

    assert payload.startswith(b"\xef\xbb\xbf")
    assert rows[0]["username"] == "admin"
    assert rows[0]["details"] == '{"note": "checked"}'


def test_csv_neutralizes_spreadsheet_formulas(monkeypatch):
    record = {
        "_id": "1", "occurred_at": datetime(2026, 7, 21, tzinfo=timezone.utc),
        "username": "=HYPERLINK(\"https://attacker.invalid\")",
        "name": "+cmd", "details": {},
    }
    monkeypatch.setattr(audit_log, "ensure_activity_log", lambda: FakeCollection([record]))

    rows = list(csv.DictReader(StringIO(audit_log.activity_csv().decode("utf-8-sig"))))

    assert rows[0]["username"].startswith("'=")
    assert rows[0]["name"].startswith("'+")


def test_activity_endpoint_forwards_filters_and_pagination(monkeypatch):
    captured = {}

    def fake_page(start_at, end_at, username, action, result, *, page, page_size):
        captured.update(locals())
        return {"items": [], "page": page, "page_size": page_size, "total": 0,
                "total_pages": 1, "has_previous": False, "has_next": False}

    monkeypatch.setattr(activity_api, "paginate_activities", fake_page)
    activity_api.app.dependency_overrides[activity_api.require_admin] = lambda: {"role": "admin"}
    try:
        response = TestClient(activity_api.app).get(
            "/api/activity-logs?start_date=2026-07-01&end_date=2026-07-21&page=3&page_size=50"
            "&username=ada&action=sign_in&result=success"
        )
    finally:
        activity_api.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["start_at"] == datetime(2026, 7, 1, tzinfo=timezone.utc)
    assert captured["end_at"] == datetime(2026, 7, 22, tzinfo=timezone.utc)
    assert captured["page"] == 3 and captured["page_size"] == 50


def test_activity_endpoint_rejects_inverted_date_range():
    activity_api.app.dependency_overrides[activity_api.require_admin] = lambda: {"role": "admin"}
    try:
        response = TestClient(activity_api.app).get(
            "/api/activity-logs?start_date=2026-07-21&end_date=2026-07-01"
        )
    finally:
        activity_api.app.dependency_overrides.clear()

    assert response.status_code == 422
    assert "start_date" in response.json()["detail"]


def test_require_admin_rejects_every_non_admin_role(monkeypatch):
    class Users:
        def find_one(self, _query):
            return {
                "username": "owner", "status": "approved", "role": "owner",
                "session_token_hash": "stored",
                "session_expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            }

    monkeypatch.setattr(activity_api, "ensure_user_schema", lambda: Users())
    monkeypatch.setattr(activity_api, "session_is_active", lambda _user: True)
    credentials = activity_api.HTTPAuthorizationCredentials(scheme="Bearer", credentials="x" * 43)

    try:
        activity_api.require_admin(credentials)
    except activity_api.HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("A non-admin role was allowed to access the activity log")


def test_require_admin_rejects_expired_session(monkeypatch):
    class Users:
        def find_one(self, _query):
            return {
                "username": "admin", "status": "approved", "role": "admin",
                "session_token_hash": "stored",
                "session_expires_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
            }

    monkeypatch.setattr(activity_api, "ensure_user_schema", lambda: Users())
    credentials = activity_api.HTTPAuthorizationCredentials(scheme="Bearer", credentials="x" * 43)

    try:
        activity_api.require_admin(credentials)
    except activity_api.HTTPException as exc:
        assert exc.status_code == 401
        assert exc.headers["WWW-Authenticate"] == "Bearer"
    else:
        raise AssertionError("An expired session was accepted")


def test_api_responses_include_security_headers():
    activity_api.app.dependency_overrides[activity_api.require_admin] = lambda: {"role": "admin"}
    try:
        response = TestClient(activity_api.app).get("/api/activity-logs")
    finally:
        activity_api.app.dependency_overrides.clear()

    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
