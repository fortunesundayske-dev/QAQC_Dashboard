"""HTTP API for administrator activity-log review and CSV exports."""

from datetime import date, datetime, time, timedelta, timezone
import hashlib
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from database.audit_log import activity_csv, paginate_activities
from database.mongo_users import ensure_user_schema
from database.settings import get_setting
from security import session_is_active, utc_timestamp


ADMIN_ROLE = "admin"
bearer = HTTPBearer(auto_error=False)
PRODUCTION = str(get_setting("QAQC_ENV", "development")).strip().lower() == "production"
allowed_hosts = [
    host.strip()
    for host in str(get_setting("QAQC_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")).split(",")
    if host.strip()
]
app = FastAPI(
    title="QA/QC Dashboard API",
    version="1.1.0",
    docs_url=None if PRODUCTION else "/docs",
    redoc_url=None if PRODUCTION else "/redoc",
    openapi_url=None if PRODUCTION else "/openapi.json",
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or ["localhost"])
if PRODUCTION and str(get_setting("QAQC_FORCE_HTTPS", "true")).strip().lower() in {"1", "true", "yes"}:
    app.add_middleware(HTTPSRedirectMiddleware)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    if PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


def require_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
):
    """Resolve the Streamlit session bearer token and enforce admin-or-above access."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not 32 <= len(credentials.credentials) <= 128:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_hash = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
    collection = ensure_user_schema()
    user = collection.find_one({"session_token_hash": token_hash})
    if not user or not session_is_active(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if str(user.get("role", "")).strip().lower() != ADMIN_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    try:
        collection.update_one(
            {"username": user["username"], "session_token_hash": token_hash},
            {"$set": {"session_last_activity_at": utc_timestamp()}},
        )
    except Exception:
        pass
    return user


def _date_bounds(start_date: date | None, end_date: date | None):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")
    start_at = datetime.combine(start_date, time.min, tzinfo=timezone.utc) if start_date else None
    end_at = (
        datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
        if end_date else None
    )
    return start_at, end_at


@app.get("/api/activity-logs")
def get_activity_logs(
    _admin: Annotated[dict, Depends(require_admin)],
    start_date: date | None = None,
    end_date: date | None = None,
    username: Annotated[str | None, Query(max_length=100)] = None,
    action: Annotated[str | None, Query(max_length=100)] = None,
    result: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    start_at, end_at = _date_bounds(start_date, end_date)
    return paginate_activities(
        start_at, end_at, username, action, result, page=page, page_size=page_size,
    )


@app.get("/api/activity-logs/csv")
def download_activity_logs_csv(
    _admin: Annotated[dict, Depends(require_admin)],
    start_date: date | None = None,
    end_date: date | None = None,
    username: Annotated[str | None, Query(max_length=100)] = None,
    action: Annotated[str | None, Query(max_length=100)] = None,
    result: Annotated[str | None, Query(max_length=100)] = None,
):
    start_at, end_at = _date_bounds(start_date, end_date)
    content = activity_csv(start_at, end_at, username, action, result)
    suffix = f"{start_date or 'all'}_{end_date or 'all'}"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="qaqc_activity_logs_{suffix}.csv"'},
    )
