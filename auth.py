import base64
import hashlib
import hmac
import json
import secrets
import smtplib
import time
from datetime import timedelta
from email.message import EmailMessage
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import streamlit as st
import streamlit.components.v1 as components

from database.mongo_users import get_database, load_users, save_users, touch_user_session
from database.cloudinary_storage import delete_attachment, upload_profile_photo
from database.settings import get_setting
from database.audit_log import record_activity
from security import (
    ACCOUNT_LOCK_MINUTES,
    INACTIVITY_TIMEOUT_SECONDS,
    MAX_FAILED_ATTEMPTS,
    MIN_PASSWORD_LENGTH,
    PBKDF2_ITERATIONS,
    SESSION_TTL_HOURS,
    SecurityConfigurationError,
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


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROFILE_DIR = DATA_DIR / "profile_photos"
LOGO_FILE = BASE_DIR / "assets" / "evomec_logo.png"
SESSION_TOKEN_PARAM = "auth_token"
SESSION_COOKIE_NAME = "__Host-qaqc_session"
SESSION_TOUCH_INTERVAL_SECONDS = 15
DISCIPLINES = ["Civil", "Mechanical", "Piping", "Welding", "Electrical", "Instrumentation", "NDT", "Quality Management"]
DEFAULT_ADMIN_EMAIL = "fortune.kpakue@evomeclimited.com"
MICROSOFT_GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


def _utc_now():
    return utc_timestamp()


def _image_data_uri(path):
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:image/png;base64,{encoded}"


def _ensure_auth_store():
    DATA_DIR.mkdir(exist_ok=True)
    try:
        PROFILE_DIR.mkdir(exist_ok=True)
    except OSError:
        # Some hosted deployments mount the app directory read-only.
        # Profile upload can fail gracefully later; sign-in should still work.
        pass
    users = load_users()
    if users:
        legacy_admin = users.get("admin")
        if legacy_admin and verify_password("admin123", legacy_admin):
            bootstrap_password = str(get_setting("QAQC_BOOTSTRAP_ADMIN_PASSWORD", ""))
            if not valid_password(bootstrap_password):
                raise SecurityConfigurationError(
                    "The legacy default administrator credential is disabled. Set "
                    "QAQC_BOOTSTRAP_ADMIN_PASSWORD to a unique strong password, restart once, "
                    "then remove that bootstrap secret."
                )
            salt = secrets.token_hex(16)
            legacy_admin.update(
                {
                    "password": hash_password(bootstrap_password, salt),
                    "salt": salt,
                    "password_iterations": PBKDF2_ITERATIONS,
                    "password_changed_at": _utc_now(),
                    "failed_attempts": 0,
                    "locked_until": None,
                }
            )
            _save_users(users)
        return users

    bootstrap_password = str(get_setting("QAQC_BOOTSTRAP_ADMIN_PASSWORD", ""))
    bootstrap_email = str(get_setting("QAQC_BOOTSTRAP_ADMIN_EMAIL", "")).strip().lower()
    bootstrap_username = str(get_setting("QAQC_BOOTSTRAP_ADMIN_USERNAME", "admin")).strip().lower()
    if not valid_username(bootstrap_username) or not valid_email(bootstrap_email) or not valid_password(bootstrap_password):
        raise SecurityConfigurationError(
            "No accounts exist. Configure QAQC_BOOTSTRAP_ADMIN_EMAIL and a unique "
            f"QAQC_BOOTSTRAP_ADMIN_PASSWORD of at least {MIN_PASSWORD_LENGTH} characters."
        )
    salt = secrets.token_hex(16)
    admin = {
        "username": bootstrap_username,
        "email": bootstrap_email,
        "name": "System Administrator",
        "role": "admin",
        "status": "approved",
        "password": hash_password(bootstrap_password, salt),
        "salt": salt,
        "password_iterations": PBKDF2_ITERATIONS,
        "password_changed_at": _utc_now(),
        "created_at": _utc_now(),
        "approved_at": _utc_now(),
        "approved_by": "system",
        "profile_photo": None,
        "discipline": "Quality Management",
        "failed_attempts": 0,
        "locked_until": None,
    }
    users = {bootstrap_username: admin}
    _save_users(users)
    return users


def _load_users():
    try:
        return _ensure_auth_store()
    except Exception as exc:
        error_name = type(exc).__name__
        if isinstance(exc, SecurityConfigurationError):
            st.error("Secure administrator setup is required.")
            st.info(str(exc))
        elif error_name in {"InvalidURI", "ConfigurationError", "ValueError"}:
            st.error("The MongoDB connection string is invalid.")
            st.info(
                "Use one Atlas hostname with mongodb+srv://, or use mongodb:// "
                "for a comma-separated seed list. Check MONGODB_URI in Streamlit Secrets."
            )
        elif error_name == "OperationFailure":
            st.error("MongoDB rejected the database username or password.")
            st.info("Reset the Atlas database-user password and update MONGODB_URI in Streamlit Secrets.")
        else:
            st.error("The dashboard cannot currently reach MongoDB Atlas.")
            st.info(
                "Confirm the cluster is running and its Atlas Network Access list permits "
                "the deployed app, then reboot the Streamlit app."
            )
        st.caption(f"Connection error type: {error_name}")
        if st.button("Retry database connection", width="stretch"):
            get_database.cache_clear()
            st.rerun()
        st.stop()


def _save_users(users):
    save_users(users)


def _try_save_users(users):
    try:
        _save_users(users)
        return True
    except Exception:
        return False


def _hash_password(password, salt):
    return hash_password(password, salt)


def _hash_session_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _secure_cookie_enabled():
    return str(get_setting("QAQC_COOKIE_SECURE", "true")).strip().lower() in {"1", "true", "yes"}


def _session_cookie_name():
    return SESSION_COOKIE_NAME if _secure_cookie_enabled() else "qaqc_session_dev"


def _browser_session_token():
    try:
        return str(st.context.cookies.get(_session_cookie_name()) or "").strip()
    except Exception:
        return ""


def _write_session_cookie(token=None):
    """Synchronize a same-site browser-session cookie without putting tokens in URLs."""
    cookie_name = _session_cookie_name()
    if token:
        attributes = "; Path=/; SameSite=Strict" + ("; Secure" if _secure_cookie_enabled() else "")
        cookie = f"{cookie_name}={token}{attributes}"
    else:
        attributes = "; Path=/; Max-Age=0; SameSite=Strict" + ("; Secure" if _secure_cookie_enabled() else "")
        cookie = f"{cookie_name}={attributes}"
    components.html(
        f"<script>document.cookie = {json.dumps(cookie)};</script>",
        height=0,
        width=0,
    )


def _clear_query_token():
    try:
        if SESSION_TOKEN_PARAM in st.query_params:
            del st.query_params[SESSION_TOKEN_PARAM]
    except Exception:
        pass


def _verify_password(password, user):
    return verify_password(password, user)


def _find_user_by_login(users, identifier):
    login_id = str(identifier or "").strip().lower()
    if login_id in users:
        return login_id, users[login_id]
    for username, user in users.items():
        if str(user.get("email", "")).strip().lower() == login_id:
            return username, user
    return None, None


def _valid_password(password):
    return valid_password(password)


def _send_gmail(recipient, subject, body, sender, app_password):
    """Send a plain-text notification with Gmail's authenticated SMTP service."""
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = str(subject or "")
    message.set_content(str(body or ""))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
            smtp.login(sender, app_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise RuntimeError("Gmail could not send the approval email. Check the Gmail address and app password.") from exc
    return True


def _send_exchange(recipient, subject, body):
    """Send mail through Exchange Online using Microsoft Graph application auth."""
    recipient = str(recipient or "").strip()
    tenant_id = str(get_setting("QAQC_EXCHANGE_TENANT_ID", "")).strip()
    client_id = str(get_setting("QAQC_EXCHANGE_CLIENT_ID", "")).strip()
    client_secret = str(get_setting("QAQC_EXCHANGE_CLIENT_SECRET", "")).strip()
    sender = str(get_setting("QAQC_EXCHANGE_SENDER", DEFAULT_ADMIN_EMAIL)).strip()
    if not all([recipient, tenant_id, client_id, client_secret, sender]):
        return False

    token_request = Request(
        f"https://login.microsoftonline.com/{quote(tenant_id, safe='')}/oauth2/v2.0/token",
        data=urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(token_request, timeout=20) as response:
            token_payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Exchange token request failed with HTTP {exc.code}.") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("Exchange token service could not be reached.") from exc
    access_token = str(token_payload.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError("Exchange did not return an access token.")

    mail_payload = {
        "message": {
            "subject": str(subject or ""),
            "body": {"contentType": "Text", "content": str(body or "")},
            "toRecipients": [{"emailAddress": {"address": recipient}}],
        },
        "saveToSentItems": True,
    }
    mail_request = Request(
        f"{MICROSOFT_GRAPH_ROOT}/users/{quote(sender, safe='')}/sendMail",
        data=json.dumps(mail_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(mail_request, timeout=20) as response:
            if int(getattr(response, "status", 202)) not in {200, 202}:
                raise RuntimeError("Exchange rejected the email request.")
    except HTTPError as exc:
        raise RuntimeError(f"Exchange sendMail failed with HTTP {exc.code}.") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("Exchange mail service could not be reached.") from exc
    return True


def send_email(recipient, subject, body):
    """Send notification mail through configured Gmail or Exchange credentials."""
    recipient = str(recipient or "").strip()
    gmail_address = str(get_setting("QAQC_GMAIL_ADDRESS", "")).strip()
    gmail_app_password = str(get_setting("QAQC_GMAIL_APP_PASSWORD", "")).replace(" ", "").strip()
    if recipient and gmail_address and gmail_app_password:
        return _send_gmail(recipient, subject, body, gmail_address, gmail_app_password)
    return _send_exchange(recipient, subject, body)


def _send_approval_email(user):
    recipient = str(user.get("email") or "").strip()
    if not recipient:
        return False

    display_name = str(user.get("name") or user.get("username") or "Requestor").strip()
    role = str(user.get("role") or "user").replace("_", " ").title()
    dashboard_url = str(
        get_setting("QAQC_APP_URL", "https://qualitydashboard-evomec.streamlit.app/")
        or "https://qualitydashboard-evomec.streamlit.app/"
    ).strip()
    return send_email(
        recipient,
        "QA/QC Dashboard access approved",
        f"Hello {display_name},\n\n"
        "Your request for access to the Evomec Global Services QA/QC Dashboard has been approved by an administrator.\n"
        f"Assigned role: {role}\n\n"
        f"Sign in here: {dashboard_url}\n\n"
        "Regards,\n"
        "KPAKUE FORTUNE (QA)",
    )


def init_auth():
    if "auth" not in st.session_state:
        st.session_state.auth = {
            "logged_in": False,
            "username": None,
            "name": None,
            "role": None,
            "email": None,
            "discipline": "QA/QC",
            "profile_photo": None,
        }
    elif "logged_in" not in st.session_state:
        st.session_state.logged_in = st.session_state.auth.get("logged_in", False)

    if st.session_state.get("logged_in") and not st.session_state.auth.get("logged_in"):
        st.session_state.auth.update(
            {
                "logged_in": True,
                "username": st.session_state.get("username"),
                "name": st.session_state.get("name"),
                "role": st.session_state.get("role"),
                "email": st.session_state.get("email"),
                "discipline": st.session_state.get("discipline", "QA/QC"),
                "profile_photo": st.session_state.get("profile_photo"),
            }
        )


def _set_logged_in(username, user, session_token=None):
    st.session_state.auth = {
        "logged_in": True,
        "username": username,
        "name": user["name"],
        "role": user["role"],
        "email": user["email"],
        "discipline": user.get("discipline", "QA/QC"),
        "profile_photo": user.get("profile_photo_asset") or user.get("profile_photo"),
        "auth_token": session_token or st.session_state.get("auth", {}).get("auth_token"),
    }
    st.session_state.logged_in = True
    st.session_state.username = username
    st.session_state.name = user["name"]
    st.session_state.role = user["role"]
    st.session_state.email = user["email"]
    st.session_state.discipline = user.get("discipline", "QA/QC")
    st.session_state.profile_photo = user.get("profile_photo_asset") or user.get("profile_photo")
    st.session_state.auth_token = session_token or st.session_state.auth.get("auth_token")
    st.session_state.auth_last_activity = time.time()


def _clear_local_session():
    st.session_state.auth = {
        "logged_in": False,
        "username": None,
        "name": None,
        "role": None,
        "email": None,
        "discipline": "QA/QC",
        "profile_photo": None,
        "auth_token": None,
    }
    for key in [
        "logged_in", "username", "name", "role", "email", "discipline",
        "profile_photo", "auth_token", "auth_last_activity", "auth_server_touch",
    ]:
        st.session_state.pop(key, None)
    st.session_state.logged_in = False
    _write_session_cookie()
    _clear_query_token()


def _touch_server_session(username, token, *, force=False):
    now = time.time()
    previous_touch = float(st.session_state.get("auth_server_touch", 0) or 0)
    if not force and now - previous_touch < SESSION_TOUCH_INTERVAL_SECONDS:
        return True
    try:
        touched = touch_user_session(username, _hash_session_token(str(token)), _utc_now())
    except Exception:
        return False
    if touched:
        st.session_state.auth_server_touch = now
    return touched


def _server_session_user():
    """Return the live user only when the local token matches an unexpired server session."""
    auth_state = st.session_state.get("auth") or {}
    username = auth_state.get("username")
    token = auth_state.get("auth_token") or st.session_state.get("auth_token")
    if not username or not token:
        return None
    user = _load_users().get(username)
    if not user or not session_is_active(user):
        return None
    if not hmac.compare_digest(str(user.get("session_token_hash")), _hash_session_token(str(token))):
        return None
    return user


def _restore_from_session_cookie():
    token = _browser_session_token()
    if not 32 <= len(token) <= 128:
        if token:
            _write_session_cookie()
        return False
    token_hash = _hash_session_token(token)
    users = _load_users()
    for username, user in users.items():
        saved_hash = str(user.get("session_token_hash") or "")
        if saved_hash and hmac.compare_digest(saved_hash, token_hash) and session_is_active(user):
            if not _touch_server_session(username, token, force=True):
                _write_session_cookie()
                return False
            _set_logged_in(username, user, session_token=token)
            _write_session_cookie(token)
            _inactivity_watchdog()
            record_activity(
                "restore_session", category="authentication", page="Sign in",
                details={"source": "secure_cookie"}, actor=user,
            )
            return True
    _write_session_cookie()
    return False


def _enforce_inactivity_timeout():
    if not st.session_state.auth.get("logged_in"):
        return False
    now = time.time()
    last_activity = float(st.session_state.get("auth_last_activity", now))
    if inactivity_expired(last_activity, now):
        _set_logged_out(reason="inactivity_timeout")
        st.session_state.auth_timeout_message = "You were signed out after 2 minutes of inactivity."
        return True
    st.session_state.auth_last_activity = now
    return False


@st.fragment(run_every=INACTIVITY_TIMEOUT_SECONDS)
def _inactivity_watchdog():
    """Re-check inactivity without reloading the browser or losing session state."""
    auth_state = st.session_state.get("auth") or {}
    if not auth_state.get("logged_in"):
        return
    now = time.time()
    last_activity = st.session_state.get("auth_last_activity", now)
    if inactivity_expired(last_activity, now):
        _set_logged_out(reason="inactivity_timeout")
        st.session_state.auth_timeout_message = "You were signed out after 2 minutes of inactivity."
        st.rerun()


def _set_logged_out(reason="user_sign_out"):
    actor = dict(st.session_state.get("auth") or {})
    username = actor.get("username")
    if username:
        users = _load_users()
        token = actor.get("auth_token") or st.session_state.get("auth_token")
        saved_hash = users.get(username, {}).get("session_token_hash")
        if token and saved_hash and hmac.compare_digest(saved_hash, _hash_session_token(str(token))):
            users[username].pop("session_token_hash", None)
            users[username].pop("session_expires_at", None)
            users[username].pop("session_created_at", None)
            users[username].pop("session_last_activity_at", None)
            _try_save_users(users)
        record_activity(
            "sign_out",
            category="authentication",
            page="Account",
            details={"reason": reason},
            actor=actor,
        )
    _clear_local_session()


def login():
    init_auth()
    # Tokens from older releases were placed in URLs. They are never trusted now.
    _clear_query_token()

    if st.session_state.auth["logged_in"]:
        live_user = _server_session_user()
        if not live_user:
            _clear_local_session()
            st.session_state.auth_timeout_message = "Your secure session expired or was revoked. Sign in again."
        elif not _enforce_inactivity_timeout():
            _set_logged_in(st.session_state.auth["username"], live_user)
            token = st.session_state.auth.get("auth_token")
            _touch_server_session(st.session_state.auth["username"], token)
            _write_session_cookie(token)
            _inactivity_watchdog()
            return True

    timeout_message = st.session_state.pop("auth_timeout_message", None)
    if timeout_message:
        st.warning(timeout_message)

    if _restore_from_session_cookie():
        return True

    logo_src = _image_data_uri(LOGO_FILE)
    st.markdown('<div class="auth-page">', unsafe_allow_html=True)
    hero_col, form_col = st.columns([1.05, 1], gap="large")

    with hero_col:
        logo_html = f'<img class="auth-logo" src="{logo_src}" alt="Evomec logo">' if logo_src else '<div class="auth-logo-text">EVOMEC</div>'
        st.markdown(
            f"""
<div class="auth-hero-panel">
    {logo_html}
    <div class="auth-eyebrow auth-eyebrow--pill">Secure QA/QC Access</div>
    <h1>Evomec QA/QC<br><span>Command Centre</span></h1>
    <p>A secure, centralized platform for managing project quality, standards, tools, and learning resources - accessible only to authorized personnel.</p>
    <div class="auth-feature-grid">
        <div class="auth-feature"><b>PBKDF2 Password Hashing</b><small>Industry-standard encryption for maximum security</small></div>
        <div class="auth-feature"><b>Admin Approval Gate</b><small>All access requests are reviewed by an administrator</small></div>
        <div class="auth-feature"><b>Role-Based Access</b><small>Granular permissions ensure users see only what they need</small></div>
        <div class="auth-feature"><b>Audit-Ready Records</b><small>Complete traceability and audit-ready user activity</small></div>
    </div>
    <div class="auth-access-note"><b>Authorized Access Only</b><span>Registration requests are carefully reviewed before access is granted to project records, standards, tools, and learning modules.</span></div>
</div>
""",
            unsafe_allow_html=True,
        )

    with form_col:
        st.markdown(
            """
<div class="auth-card-head">
    <div class="auth-shield">✓</div>
    <h2>Welcome Back</h2>
    <p>Sign in to access the Evomec QA/QC Command Centre</p>
</div>
""",
            unsafe_allow_html=True,
        )

        access_mode = st.radio(
            "Access mode",
            ["Sign in", "Request access"],
            horizontal=True,
            label_visibility="collapsed",
            key="auth_access_mode",
        )

        if access_mode == "Sign in":
            username = st.text_input(
                "Username or work email", key="login_username",
                placeholder="Enter your username or work email", max_chars=254,
            ).strip().lower()
            password = st.text_input(
                "Password", type="password", key="login_password",
                placeholder="Enter your password", max_chars=256,
            )

            if st.button("Sign in", type="primary", width="stretch"):
                login_identifier = username
                users = _load_users()
                username, user = _find_user_by_login(users, username)

                if user and account_is_locked(user):
                    record_activity(
                        "sign_in", category="authentication", page="Sign in",
                        status="denied", details={"reason": "account_locked"}, actor=user,
                    )
                    st.error("This account is temporarily locked after repeated failed sign-in attempts.")
                    return False

                # Unknown accounts still perform the password derivation, reducing
                # observable username-enumeration timing differences.
                password_matches = _verify_password(password, user) if user else bool(
                    _hash_password(password, "0" * 32) and False
                )
                if not user or not password_matches:
                    if user:
                        failed_attempts = int(user.get("failed_attempts", 0)) + 1
                        user["failed_attempts"] = failed_attempts
                        if failed_attempts >= MAX_FAILED_ATTEMPTS:
                            user["locked_until"] = utc_timestamp(
                                utc_now() + timedelta(minutes=ACCOUNT_LOCK_MINUTES)
                            )
                        _try_save_users(users)
                    record_activity(
                        "sign_in",
                        category="authentication",
                        page="Sign in",
                        status="failed",
                        details={"reason": "invalid_credentials"},
                        actor=user or {"username": login_identifier},
                    )
                    st.error("Invalid username or password.")
                    return False

                if user.get("status") == "restricted":
                    record_activity(
                        "sign_in", category="authentication", page="Sign in",
                        status="denied", details={"reason": "restricted_account"}, actor=user,
                    )
                    st.warning("Your account has been restricted. Contact an administrator for access.")
                    return False

                if user.get("status") != "approved":
                    record_activity(
                        "sign_in", category="authentication", page="Sign in",
                        status="denied", details={"reason": "approval_pending"}, actor=user,
                    )
                    st.warning("Your account is waiting for administrator approval.")
                    return False

                session_token = secrets.token_urlsafe(32)
                user["session_token_hash"] = _hash_session_token(session_token)
                user["session_created_at"] = _utc_now()
                user["session_expires_at"] = utc_timestamp(
                    utc_now() + timedelta(hours=SESSION_TTL_HOURS)
                )
                user["session_last_activity_at"] = _utc_now()
                user["failed_attempts"] = 0
                user["locked_until"] = None
                user["last_login"] = _utc_now()
                if password_needs_upgrade(user):
                    salt = secrets.token_hex(16)
                    user["password"] = _hash_password(password, salt)
                    user["salt"] = salt
                    user["password_iterations"] = PBKDF2_ITERATIONS
                    user["password_changed_at"] = _utc_now()
                if not _try_save_users(users):
                    st.error("Sign-in could not establish a secure server session. Try again shortly.")
                    return False
                _set_logged_in(username, user, session_token=session_token)
                _write_session_cookie(session_token)
                record_activity("sign_in", category="authentication", page="Sign in", actor=user)
                st.rerun()

            st.markdown('<div class="auth-card-foot">Secure &nbsp;•&nbsp; Private &nbsp;•&nbsp; Protected</div>', unsafe_allow_html=True)

        else:
            with st.form("registration_form"):
                name = st.text_input("Full name", max_chars=100)
                username = st.text_input("Preferred username", max_chars=32).strip().lower()
                email = st.text_input("Work email", max_chars=254)
                discipline_choice = st.selectbox(
                    "Primary discipline",
                    DISCIPLINES + ["Other / custom"],
                )
                custom_discipline = st.text_input(
                    "Custom discipline (required when Other / custom is selected)", max_chars=80,
                )
                password = st.text_input("Password", type="password", max_chars=256)
                confirm = st.text_input("Confirm password", type="password", max_chars=256)
                submitted = st.form_submit_button("Submit for approval", width="stretch")

            if submitted:
                name = " ".join(name.strip().split())
                email = email.strip().lower()
                discipline = custom_discipline.strip() if discipline_choice == "Other / custom" else discipline_choice
                users = _load_users()
                if not name or not username or not email:
                    st.error("Full name, username, and email are required.")
                elif not valid_username(username):
                    st.error("Use 3-32 lowercase letters, numbers, dots, hyphens, or underscores for the username.")
                elif not valid_email(email):
                    st.error("Enter a valid work email address.")
                elif username in users:
                    st.error("That username already exists.")
                elif any(str(item.get("email", "")).strip().lower() == email for item in users.values()):
                    st.error("An account request already exists for that email address.")
                elif not discipline:
                    st.error("Enter your custom discipline.")
                elif password != confirm:
                    st.error("Passwords do not match.")
                elif not _valid_password(password):
                    st.error(
                        f"Use {MIN_PASSWORD_LENGTH}-256 characters with uppercase, lowercase, "
                        "number, and symbol. Do not reuse a password from another service."
                    )
                else:
                    salt = secrets.token_hex(16)
                    users[username] = {
                        "username": username,
                        "email": email,
                        "name": name,
                        "role": "user",
                        "status": "pending",
                        "password": _hash_password(password, salt),
                        "salt": salt,
                        "password_iterations": PBKDF2_ITERATIONS,
                        "password_changed_at": _utc_now(),
                        "created_at": _utc_now(),
                        "approved_at": None,
                        "approved_by": None,
                        "profile_photo": None,
                        "discipline": discipline,
                        "failed_attempts": 0,
                        "locked_until": None,
                    }
                    if _try_save_users(users):
                        record_activity(
                            "request_access",
                            category="authentication",
                            page="Registration",
                            target=username,
                            actor=users[username],
                        )
                        st.success("Registration submitted. An administrator must approve access before sign in.")
                    else:
                        st.error(
                            "Registration could not be saved on this deployment. "
                            "Configure persistent storage or redeploy with a writable user store."
                        )

    st.markdown(
        """
<div class="auth-footer">
    <div><b>Your security is our priority.</b><span>All data is encrypted and access is monitored for compliance.</span></div>
    <div>© 2026 Evomec. All rights reserved.</div>
</div>
</div>
""",
        unsafe_allow_html=True,
    )

    return False


def logout():
    if st.sidebar.button("Sign out", width="stretch"):
        _set_logged_out(reason="user_sign_out")
        st.rerun()


def sign_out():
    """Clear the active session and invalidate its persisted token."""
    _set_logged_out(reason="user_sign_out")


def get_role():
    init_auth()
    return st.session_state.auth.get("role")


def current_user():
    init_auth()
    users = _load_users()
    username = st.session_state.auth.get("username")
    return users.get(username) if username else None


def require_role(roles):
    role = get_role()
    if role not in roles:
        allowed = ", ".join(str(item).title() for item in roles)
        current = str(role or "not signed in").title()
        st.error(f"This module is restricted to: {allowed}. Your current role is: {current}.")
        st.info("To approve or manage users, sign out and sign in with an admin account.")
        if st.button("Sign out and switch account", width="stretch", key="role_guard_sign_out"):
            _set_logged_out(reason="role_access_denied")
            st.rerun()
        st.stop()


def render_user_sidebar():
    return


def update_profile(name, email, discipline, uploaded_photo=None):
    user = current_user()
    if not user:
        return False

    users = _load_users()
    record = users[user["username"]]
    name = " ".join(str(name or "").strip().split())
    email = str(email or "").strip().lower()
    discipline = " ".join(str(discipline or "").strip().split())
    if not name or len(name) > 100 or not valid_email(email) or not discipline or len(discipline) > 80:
        st.error("Enter a valid name, work email, and discipline.")
        return False
    if any(
        username != record["username"] and str(item.get("email", "")).strip().lower() == email
        for username, item in users.items()
    ):
        st.error("That email address is already assigned to another account.")
        return False
    record["name"] = name
    record["email"] = email
    record["discipline"] = discipline

    if uploaded_photo is not None:
        previous_asset = record.get("profile_photo_asset")
        try:
            asset = upload_profile_photo(uploaded_photo, record["username"])
        except Exception as exc:
            st.error(f"Profile photo could not be uploaded: {exc}")
            return False
        record["profile_photo"] = None
        record["profile_photo_asset"] = asset

    if not _try_save_users(users):
        if uploaded_photo is not None:
            try:
                delete_attachment(record.get("profile_photo_asset"))
            except Exception:
                pass
        st.error("Profile changes could not be saved on this deployment.")
        return False
    st.session_state.auth["name"] = name
    st.session_state.auth["email"] = email
    st.session_state.auth["discipline"] = discipline
    st.session_state.auth["profile_photo"] = record.get("profile_photo_asset") or record.get("profile_photo")
    st.session_state.profile_photo = st.session_state.auth["profile_photo"]
    if uploaded_photo is not None and previous_asset:
        try:
            delete_attachment(previous_asset)
        except Exception:
            pass
    record_activity(
        "update_profile",
        category="account",
        page="User Profile",
        target=record["username"],
        details={"profile_photo_updated": uploaded_photo is not None, "discipline": discipline},
        actor=record,
    )
    return True


def pending_users():
    users = _load_users()
    return {key: value for key, value in users.items() if value.get("status") == "pending"}


def all_users():
    return _load_users()


def rejected_users():
    users = _load_users()
    return {key: value for key, value in users.items() if value.get("status") == "rejected"}


def approved_users():
    users = _load_users()
    return {key: value for key, value in users.items() if value.get("status") == "approved"}


def _current_admin():
    user = current_user()
    if not user or user.get("status") != "approved" or str(user.get("role", "")).lower() != "admin":
        return None
    return user


def _is_last_approved_admin(users, username):
    target = users.get(username) or {}
    if target.get("status") != "approved" or target.get("role") != "admin":
        return False
    return sum(
        1 for user in users.values()
        if user.get("status") == "approved" and user.get("role") == "admin"
    ) <= 1


def restricted_users():
    users = _load_users()
    return {key: value for key, value in users.items() if value.get("status") == "restricted"}


def approve_user(username, role="user"):
    if role not in {"user", "viewer", "admin"}:
        return False, "Invalid role."
    users = _load_users()
    admin = _current_admin()
    if not admin:
        return False, "Administrator authorization is required."
    user = users.get(username)
    if not user:
        return False, "User not found."

    user["status"] = "approved"
    user["role"] = role
    user["approved_at"] = _utc_now()
    user["approved_by"] = admin["username"] if admin else "admin"
    if not _try_save_users(users):
        return False, "Approval could not be saved on this deployment."

    try:
        email_sent = _send_approval_email(user)
    except Exception as exc:
        user["approval_email_sent_at"] = None
        user["approval_email_error"] = f"{type(exc).__name__}: {exc}"
        _try_save_users(users)
        record_activity(
            "approve_user", category="administration", page="Access Admin",
            target=username, status="partial",
            details={"assigned_role": role, "approval_email": "failed", "error": str(exc)},
            actor=admin,
        )
        return True, f"Approved, but email failed: {exc}"

    if email_sent:
        user["approval_email_sent_at"] = _utc_now()
        user["approval_email_error"] = None
        _try_save_users(users)
        record_activity(
            "approve_user", category="administration", page="Access Admin",
            target=username, details={"assigned_role": role, "approval_email": "sent"}, actor=admin,
        )
        return True, "Approved and email sent."
    user["approval_email_sent_at"] = None
    user["approval_email_error"] = "Email delivery is not configured or the requestor has no email address."
    _try_save_users(users)
    record_activity(
        "approve_user", category="administration", page="Access Admin",
        target=username, status="partial",
        details={"assigned_role": role, "approval_email": "not_sent"}, actor=admin,
    )
    return True, "Approved. Configure Gmail or Exchange credentials to send the approval email."


def change_user_role(username, role):
    if role not in {"user", "viewer", "admin"}:
        return False, "Invalid role."
    users = _load_users()
    admin = _current_admin()
    if not admin:
        return False, "Administrator authorization is required."
    user = users.get(username)
    if not user:
        return False, "User not found."
    if user.get("status") not in {"approved", "restricted"}:
        return False, "Approve the user before changing their role."
    if admin and username == admin.get("username") and role != "admin":
        return False, "You cannot remove your own active admin role."
    if role != "admin" and _is_last_approved_admin(users, username):
        return False, "The final approved administrator cannot be demoted."
    user["role"] = role
    user["role_updated_at"] = _utc_now()
    user["role_updated_by"] = admin["username"] if admin else "admin"
    user.pop("session_token_hash", None)
    user.pop("session_expires_at", None)
    if not _try_save_users(users):
        return False, "Role change could not be saved."
    record_activity(
        "change_user_role", category="administration", page="Access Admin",
        target=username, details={"new_role": role}, actor=admin,
    )
    return True, f"Role changed to {role.title()}."


def restrict_user(username):
    users = _load_users()
    admin = _current_admin()
    if not admin:
        return False, "Administrator authorization is required."
    if username not in users:
        return False, "User not found."
    if admin and username == admin.get("username"):
        return False, "You cannot restrict your own active admin account."
    if _is_last_approved_admin(users, username):
        return False, "The final approved administrator cannot be restricted."
    users[username]["status"] = "restricted"
    users[username]["restricted_at"] = _utc_now()
    users[username]["restricted_by"] = admin["username"] if admin else "admin"
    users[username].pop("session_token_hash", None)
    users[username].pop("session_expires_at", None)
    if not _try_save_users(users):
        return False, "Restriction could not be saved on this deployment."
    record_activity("restrict_user", category="administration", page="Access Admin", target=username, actor=admin)
    return True, "User restricted."


def unrestrict_user(username):
    users = _load_users()
    admin = _current_admin()
    if not admin:
        return False, "Administrator authorization is required."
    if username not in users:
        return False, "User not found."
    users[username]["status"] = "approved"
    users[username]["unrestricted_at"] = _utc_now()
    users[username]["unrestricted_by"] = admin["username"] if admin else "admin"
    if not users[username].get("approved_at"):
        users[username]["approved_at"] = _utc_now()
    if not users[username].get("approved_by"):
        users[username]["approved_by"] = admin["username"] if admin else "admin"
    if not _try_save_users(users):
        return False, "Unrestrict could not be saved on this deployment."
    record_activity("unrestrict_user", category="administration", page="Access Admin", target=username, actor=admin)
    return True, "User unrestricted."


def delete_user(username):
    users = _load_users()
    admin = _current_admin()
    if not admin:
        return False, "Administrator authorization is required."
    if username not in users:
        return False, "User not found."
    if admin and username == admin.get("username"):
        return False, "You cannot delete your own active admin account."
    if _is_last_approved_admin(users, username):
        return False, "The final approved administrator cannot be deleted."
    users.pop(username, None)
    if not _try_save_users(users):
        return False, "Delete could not be saved on this deployment."
    record_activity("delete_user", category="administration", page="Access Admin", target=username, actor=admin)
    return True, "User deleted."


def reject_user(username):
    users = _load_users()
    admin = _current_admin()
    if not admin:
        return False
    if username not in users:
        return False
    users[username]["status"] = "rejected"
    users[username]["rejected_at"] = _utc_now()
    users[username].pop("session_token_hash", None)
    users[username].pop("session_expires_at", None)
    saved = _try_save_users(users)
    if saved:
        record_activity("reject_user", category="administration", page="Access Admin", target=username, actor=admin)
    return saved
