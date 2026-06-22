import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
USERS_FILE = DATA_DIR / "users.json"
PROFILE_DIR = DATA_DIR / "profile_photos"
PBKDF2_ITERATIONS = 260_000
DEFAULT_ADMIN_PASSWORD = "admin123"


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_auth_store():
    DATA_DIR.mkdir(exist_ok=True)
    try:
        PROFILE_DIR.mkdir(exist_ok=True)
    except OSError:
        # Some hosted deployments mount the app directory read-only.
        # Profile upload can fail gracefully later; sign-in should still work.
        pass
    if USERS_FILE.exists():
        return

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
    _save_users({"admin": admin})


def _load_users():
    _ensure_auth_store()
    with USERS_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_users(users):
    DATA_DIR.mkdir(exist_ok=True)
    with USERS_FILE.open("w", encoding="utf-8") as handle:
        json.dump(users, handle, indent=2)


def _try_save_users(users):
    try:
        _save_users(users)
        return True
    except OSError:
        return False


def _hash_password(password, salt):
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return base64.b64encode(digest).decode("utf-8")


def _verify_password(password, user):
    expected = user.get("password", "")
    salt = user.get("salt", "")
    if not expected or not salt:
        return False
    candidate = _hash_password(password, salt)
    return hmac.compare_digest(candidate, expected)


def _valid_password(password):
    checks = [
        len(password) >= 10,
        bool(re.search(r"[A-Z]", password)),
        bool(re.search(r"[a-z]", password)),
        bool(re.search(r"\d", password)),
        bool(re.search(r"[^A-Za-z0-9]", password)),
    ]
    return all(checks)


def _send_approval_email(user):
    smtp_host = os.getenv("QAQC_SMTP_HOST")
    smtp_user = os.getenv("QAQC_SMTP_USER")
    smtp_password = os.getenv("QAQC_SMTP_PASSWORD")
    sender = os.getenv("QAQC_SMTP_FROM", smtp_user or "no-reply@qaqc.local")

    if not smtp_host or not smtp_user or not smtp_password:
        return False

    msg = EmailMessage()
    msg["Subject"] = "QA/QC Dashboard access approved"
    msg["From"] = sender
    msg["To"] = user["email"]
    msg.set_content(
        f"Hello {user['name']},\n\n"
        "Your QA/QC Dashboard account has been approved. "
        "You can now sign in with your registered username.\n\n"
        "Regards,\nQA/QC Dashboard Security"
    )

    with smtplib.SMTP_SSL(smtp_host, int(os.getenv("QAQC_SMTP_PORT", "465"))) as smtp:
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)
    return True


def init_auth():
    if "auth" not in st.session_state:
        st.session_state.auth = {
            "logged_in": False,
            "username": None,
            "name": None,
            "role": None,
            "email": None,
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
            }
        )


def _set_logged_in(username, user):
    st.session_state.auth = {
        "logged_in": True,
        "username": username,
        "name": user["name"],
        "role": user["role"],
        "email": user["email"],
    }
    st.session_state.logged_in = True
    st.session_state.username = username
    st.session_state.name = user["name"]
    st.session_state.role = user["role"]
    st.session_state.email = user["email"]


def _set_logged_out():
    st.session_state.auth = {
        "logged_in": False,
        "username": None,
        "name": None,
        "role": None,
        "email": None,
    }
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.name = None
    st.session_state.role = None
    st.session_state.email = None


def login():
    init_auth()

    if st.session_state.auth["logged_in"]:
        storage_warning = st.session_state.pop("auth_storage_warning", None)
        if storage_warning:
            st.warning(storage_warning)
        return True

    st.markdown(
        """
<div class="auth-shell">
    <div class="auth-panel auth-panel--hero">
        <div class="auth-eyebrow">Secure QA/QC Access</div>
        <h1>Evomec QA/QC Command Centre</h1>
        <p>Approved access only. Registration requests are reviewed by an administrator before users can enter project records, standards, tools, and learning modules.</p>
        <div class="security-list">
            <span>PBKDF2 password hashing</span>
            <span>Admin approval gate</span>
            <span>Role-based access</span>
            <span>Audit-ready user records</span>
        </div>
    </div>
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
        username = st.text_input("Username", key="login_username").strip().lower()
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Sign in", type="primary", use_container_width=True):
            users = _load_users()
            user = users.get(username)

            if not user or not _verify_password(password, user):
                if user:
                    user["failed_attempts"] = int(user.get("failed_attempts", 0)) + 1
                    _try_save_users(users)
                st.error("Invalid username or password.")
                return False

            if user.get("status") != "approved":
                st.warning("Your account is waiting for administrator approval.")
                return False

            user["failed_attempts"] = 0
            user["last_login"] = _utc_now()
            if not _try_save_users(users):
                st.session_state.auth_storage_warning = (
                    "Signed in, but this deployment could not update the local user audit file. "
                    "Login access is active."
                )
            _set_logged_in(username, user)
            st.rerun()

        with st.expander("First local admin login"):
            st.info("Username: admin | Password: admin123. Change this password before production use.")

    else:
        with st.form("registration_form"):
            name = st.text_input("Full name")
            username = st.text_input("Preferred username").strip().lower()
            email = st.text_input("Work email")
            discipline = st.selectbox(
                "Primary discipline",
                ["Civil", "Mechanical", "Piping", "Welding", "Electrical", "Instrumentation", "NDT", "Quality Management"],
            )
            password = st.text_input("Password", type="password")
            confirm = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Submit for approval", use_container_width=True)

        if submitted:
            users = _load_users()
            if not name or not username or not email:
                st.error("Full name, username, and email are required.")
            elif username in users:
                st.error("That username already exists.")
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

    return False


def logout():
    if st.sidebar.button("Sign out", use_container_width=True):
        _set_logged_out()
        st.rerun()


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
        st.error("You do not have access to this module.")
        st.stop()


def render_user_sidebar():
    user = current_user()
    if not user:
        return

    photo = user.get("profile_photo")
    if photo and Path(photo).exists():
        st.sidebar.image(photo, width=86)
    else:
        initials = "".join(part[:1] for part in user["name"].split()[:2]).upper() or "U"
        st.sidebar.markdown(f'<div class="profile-avatar">{initials}</div>', unsafe_allow_html=True)

    st.sidebar.markdown(f"**{user['name']}**")
    st.sidebar.caption(f"{user['role'].title()} | {user.get('discipline', 'QA/QC')}")
    logout()


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
        suffix = Path(uploaded_photo.name).suffix.lower() or ".png"
        filename = f"{record['username']}{suffix}"
        photo_path = PROFILE_DIR / filename
        try:
            PROFILE_DIR.mkdir(exist_ok=True)
            photo_path.write_bytes(uploaded_photo.getbuffer())
        except OSError:
            st.error("Profile photo could not be saved on this deployment.")
            return False
        record["profile_photo"] = str(photo_path)

    if not _try_save_users(users):
        st.error("Profile changes could not be saved on this deployment.")
        return False
    st.session_state.auth["name"] = name
    st.session_state.auth["email"] = email
    return True


def pending_users():
    users = _load_users()
    return {key: value for key, value in users.items() if value.get("status") == "pending"}


def approved_users():
    users = _load_users()
    return {key: value for key, value in users.items() if value.get("status") == "approved"}


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


def reject_user(username):
    users = _load_users()
    if username not in users:
        return False
    users[username]["status"] = "rejected"
    users[username]["rejected_at"] = _utc_now()
    return _try_save_users(users)
