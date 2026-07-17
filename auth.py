import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from database.mongo_users import get_database, load_users, save_users
from database.cloudinary_storage import upload_profile_photo
from database.settings import get_setting


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROFILE_DIR = DATA_DIR / "profile_photos"
PBKDF2_ITERATIONS = 260_000
DEFAULT_ADMIN_PASSWORD = "admin123"
LOGO_FILE = BASE_DIR / "assets" / "evomec_logo.png"
SESSION_TOKEN_PARAM = "auth_token"
INACTIVITY_TIMEOUT_SECONDS = 120
DISCIPLINES = ["Civil", "Mechanical", "Piping", "Welding", "Electrical", "Instrumentation", "NDT", "Quality Management"]


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
        return users

    salt = secrets.token_hex(16)
    admin = {
        "username": "admin",
        "email": "admin@evomec.local",
        "name": "System Administrator",
        "role": "admin",
        "status": "approved",
        "password": _hash_password(DEFAULT_ADMIN_PASSWORD, salt),
        "salt": salt,
        "created_at": _utc_now(),
        "approved_at": _utc_now(),
        "approved_by": "system",
        "profile_photo": None,
        "discipline": "Quality Management",
        "failed_attempts": 0,
        "locked_until": None,
    }
    users = {"admin": admin}
    _save_users(users)
    return users


def _load_users():
    try:
        return _ensure_auth_store()
    except Exception as exc:
        error_name = type(exc).__name__
        if error_name in {"InvalidURI", "ConfigurationError", "ValueError"}:
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
        if st.button("Retry database connection", use_container_width=True):
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
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return base64.b64encode(digest).decode("utf-8")


def _hash_session_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _query_param(name):
    value = st.query_params.get(name)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _set_query_token(token):
    if token:
        st.query_params[SESSION_TOKEN_PARAM] = token


def _clear_query_token():
    try:
        if SESSION_TOKEN_PARAM in st.query_params:
            del st.query_params[SESSION_TOKEN_PARAM]
    except Exception:
        pass


def _verify_password(password, user):
    expected = user.get("password", "")
    salt = user.get("salt", "")
    if not expected or not salt:
        return False
    candidate = _hash_password(password, salt)
    return hmac.compare_digest(candidate, expected)


def _find_user_by_login(users, identifier):
    login_id = str(identifier or "").strip().lower()
    if login_id in users:
        return login_id, users[login_id]
    for username, user in users.items():
        if str(user.get("email", "")).strip().lower() == login_id:
            return username, user
    return None, None


def _valid_password(password):
    checks = [
        len(password) >= 10,
        bool(re.search(r"[A-Z]", password)),
        bool(re.search(r"[a-z]", password)),
        bool(re.search(r"\d", password)),
        bool(re.search(r"[^A-Za-z0-9]", password)),
    ]
    return all(checks)


def send_email(recipient, subject, body):
    smtp_config = {}
    smtp_config_file = DATA_DIR / "smtp_config.json"
    if smtp_config_file.exists():
        try:
            smtp_config = json.loads(smtp_config_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            smtp_config = {}

    smtp_host = get_setting("QAQC_SMTP_HOST") or get_setting("SMTP_HOST") or smtp_config.get("SMTP_HOST")
    smtp_user = get_setting("QAQC_SMTP_USER") or get_setting("SMTP_USER") or smtp_config.get("SMTP_USER")
    smtp_password = get_setting("QAQC_SMTP_PASSWORD") or get_setting("SMTP_PASSWORD") or smtp_config.get("SMTP_PASSWORD")
    smtp_port = int(get_setting("QAQC_SMTP_PORT") or get_setting("SMTP_PORT") or smtp_config.get("SMTP_PORT", "587"))
    smtp_from = get_setting("QAQC_SMTP_FROM") or get_setting("SMTP_FROM") or smtp_config.get("SMTP_FROM")
    sender = smtp_from or smtp_user or "no-reply@qaqc.local"

    if not smtp_host or not smtp_user or not smtp_password or not recipient:
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)

    use_ssl = str(get_setting("QAQC_SMTP_SSL") or get_setting("SMTP_SSL") or smtp_config.get("SMTP_SSL", "0")) == "1" or smtp_port == 465
    use_starttls = str(get_setting("QAQC_SMTP_STARTTLS") or get_setting("SMTP_STARTTLS") or smtp_config.get("SMTP_STARTTLS", "1")) == "1"
    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(smtp_host, smtp_port, timeout=20) as smtp:
        if not use_ssl and use_starttls:
            smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)
    return True


def _send_approval_email(user):
    return send_email(
        user["email"],
        "QA/QC Dashboard access approved",
        f"Hello {user['name']},\n\n"
        "Your QA/QC Dashboard account has been approved. "
        "You can now sign in with your registered username or work email.\n\n"
        "Regards,\nQA/QC Dashboard Security",
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
        "profile_photo": user.get("profile_photo"),
        "auth_token": session_token or st.session_state.get("auth", {}).get("auth_token"),
    }
    st.session_state.logged_in = True
    st.session_state.username = username
    st.session_state.name = user["name"]
    st.session_state.role = user["role"]
    st.session_state.email = user["email"]
    st.session_state.discipline = user.get("discipline", "QA/QC")
    st.session_state.profile_photo = user.get("profile_photo")
    st.session_state.auth_token = session_token or st.session_state.auth.get("auth_token")
    st.session_state.auth_last_activity = time.time()
    _set_query_token(st.session_state.auth_token)


def _enforce_inactivity_timeout():
    if not st.session_state.auth.get("logged_in"):
        return False
    now = time.time()
    last_activity = float(st.session_state.get("auth_last_activity", now))
    if now - last_activity >= INACTIVITY_TIMEOUT_SECONDS:
        _set_logged_out()
        st.session_state.auth_timeout_message = "You were signed out after 2 minutes of inactivity."
        return True
    st.session_state.auth_last_activity = now
    components.html(
        f"<script>setTimeout(function(){{window.parent.location.reload();}}, {INACTIVITY_TIMEOUT_SECONDS * 1000});</script>",
        height=0,
        width=0,
    )
    return False


def _restore_from_query_token():
    token = _query_param(SESSION_TOKEN_PARAM)
    if not token:
        return False
    token_hash = _hash_session_token(token)
    users = _load_users()
    for username, user in users.items():
        saved_hash = user.get("session_token_hash")
        if saved_hash and hmac.compare_digest(saved_hash, token_hash) and user.get("status") == "approved":
            _set_logged_in(username, user, session_token=token)
            return True
    _clear_query_token()
    return False


def _set_logged_out():
    username = st.session_state.get("auth", {}).get("username")
    if username:
        users = _load_users()
        if username in users and users[username].get("session_token_hash"):
            users[username].pop("session_token_hash", None)
            _try_save_users(users)
    st.session_state.auth = {
        "logged_in": False,
        "username": None,
        "name": None,
        "role": None,
        "email": None,
        "auth_token": None,
    }
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.name = None
    st.session_state.role = None
    st.session_state.email = None
    st.session_state.auth_token = None
    _clear_query_token()


def login():
    init_auth()

    if st.session_state.auth["logged_in"] and not _enforce_inactivity_timeout():
        storage_warning = st.session_state.pop("auth_storage_warning", None)
        if storage_warning:
            st.warning(storage_warning)
        return True

    timeout_message = st.session_state.pop("auth_timeout_message", None)
    if timeout_message:
        st.warning(timeout_message)

    if _restore_from_query_token():
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
            username = st.text_input("Username or work email", key="login_username", placeholder="Enter your username or work email").strip().lower()
            password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
            remember = st.checkbox("Remember me", key="login_remember")
            st.markdown('<div class="auth-forgot">Forgot password?</div>', unsafe_allow_html=True)

            if st.button("Sign in", type="primary", use_container_width=True):
                users = _load_users()
                username, user = _find_user_by_login(users, username)

                if not user or not _verify_password(password, user):
                    if user:
                        user["failed_attempts"] = int(user.get("failed_attempts", 0)) + 1
                        _try_save_users(users)
                    st.error("Invalid username or password.")
                    return False

                if user.get("status") == "restricted":
                    st.warning("Your account has been restricted. Contact an administrator for access.")
                    return False

                if user.get("status") != "approved":
                    st.warning("Your account is waiting for administrator approval.")
                    return False

                session_token = secrets.token_urlsafe(32)
                user["session_token_hash"] = _hash_session_token(session_token)
                user["failed_attempts"] = 0
                user["last_login"] = _utc_now()
                if not _try_save_users(users):
                    st.session_state.auth_storage_warning = (
                        "Signed in, but this deployment could not update the local user audit file. "
                        "Login access is active."
                    )
                _set_logged_in(username, user, session_token=session_token)
                st.rerun()

            if remember:
                pass

            st.markdown('<div class="auth-card-foot">Secure &nbsp;•&nbsp; Private &nbsp;•&nbsp; Protected</div>', unsafe_allow_html=True)

        else:
            with st.form("registration_form"):
                name = st.text_input("Full name")
                username = st.text_input("Preferred username").strip().lower()
                email = st.text_input("Work email")
                discipline_choice = st.selectbox(
                    "Primary discipline",
                    DISCIPLINES + ["Other / custom"],
                )
                custom_discipline = st.text_input("Custom discipline (required when Other / custom is selected)")
                password = st.text_input("Password", type="password")
                confirm = st.text_input("Confirm password", type="password")
                submitted = st.form_submit_button("Submit for approval", use_container_width=True)

            if submitted:
                discipline = custom_discipline.strip() if discipline_choice == "Other / custom" else discipline_choice
                users = _load_users()
                if not name or not username or not email:
                    st.error("Full name, username, and email are required.")
                elif username in users:
                    st.error("That username already exists.")
                elif not discipline:
                    st.error("Enter your custom discipline.")
                elif password != confirm:
                    st.error("Passwords do not match.")
                elif not _valid_password(password):
                    st.error("Use at least 10 characters with uppercase, lowercase, number, and symbol.")
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
                        "created_at": _utc_now(),
                        "approved_at": None,
                        "approved_by": None,
                        "profile_photo": None,
                        "discipline": discipline,
                        "failed_attempts": 0,
                        "locked_until": None,
                    }
                    if _try_save_users(users):
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
    if st.sidebar.button("Sign out", use_container_width=True):
        _set_logged_out()
        st.rerun()


def sign_out():
    """Clear the active session and invalidate its persisted token."""
    _set_logged_out()


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
        if st.button("Sign out and switch account", use_container_width=True, key="role_guard_sign_out"):
            _set_logged_out()
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
    record["name"] = name
    record["email"] = email
    record["discipline"] = discipline

    if uploaded_photo is not None:
        try:
            asset = upload_profile_photo(uploaded_photo, record["username"])
        except Exception as exc:
            st.error(f"Profile photo could not be uploaded: {exc}")
            return False
        record["profile_photo"] = asset["url"]
        record["profile_photo_asset"] = asset

    if not _try_save_users(users):
        st.error("Profile changes could not be saved on this deployment.")
        return False
    st.session_state.auth["name"] = name
    st.session_state.auth["email"] = email
    st.session_state.auth["discipline"] = discipline
    st.session_state.auth["profile_photo"] = record.get("profile_photo")
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


def restricted_users():
    users = _load_users()
    return {key: value for key, value in users.items() if value.get("status") == "restricted"}


def approve_user(username, role="user"):
    users = _load_users()
    user = users.get(username)
    admin = current_user()
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
        return True, f"Approved, but email failed: {exc}"

    if email_sent:
        return True, "Approved and email sent."
    return True, "Approved. Configure SMTP environment variables to send approval email."


def change_user_role(username, role):
    if role not in {"user", "viewer", "admin"}:
        return False, "Invalid role."
    users = _load_users()
    admin = current_user()
    user = users.get(username)
    if not user:
        return False, "User not found."
    if user.get("status") not in {"approved", "restricted"}:
        return False, "Approve the user before changing their role."
    if admin and username == admin.get("username") and role != "admin":
        return False, "You cannot remove your own active admin role."
    user["role"] = role
    user["role_updated_at"] = _utc_now()
    user["role_updated_by"] = admin["username"] if admin else "admin"
    if not _try_save_users(users):
        return False, "Role change could not be saved."
    return True, f"Role changed to {role.title()}."


def restrict_user(username):
    users = _load_users()
    admin = current_user()
    if username not in users:
        return False, "User not found."
    if admin and username == admin.get("username"):
        return False, "You cannot restrict your own active admin account."
    users[username]["status"] = "restricted"
    users[username]["restricted_at"] = _utc_now()
    users[username]["restricted_by"] = admin["username"] if admin else "admin"
    users[username].pop("session_token_hash", None)
    if not _try_save_users(users):
        return False, "Restriction could not be saved on this deployment."
    return True, "User restricted."


def unrestrict_user(username):
    users = _load_users()
    admin = current_user()
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
    return True, "User unrestricted."


def delete_user(username):
    users = _load_users()
    admin = current_user()
    if username not in users:
        return False, "User not found."
    if admin and username == admin.get("username"):
        return False, "You cannot delete your own active admin account."
    users.pop(username, None)
    if not _try_save_users(users):
        return False, "Delete could not be saved on this deployment."
    return True, "User deleted."


def reject_user(username):
    users = _load_users()
    if username not in users:
        return False
    users[username]["status"] = "rejected"
    users[username]["rejected_at"] = _utc_now()
    return _try_save_users(users)
