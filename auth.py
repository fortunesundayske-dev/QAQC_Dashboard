import streamlit as st
import hashlib
import hmac

PASSWORD_SALT = "qaqc_dashboard_v1"


def hash_password(password):
    return hashlib.sha256(f"{PASSWORD_SALT}:{password}".encode()).hexdigest()

# =========================
# USERS DATABASE (replace later with DB)
# =========================
USERS = {
    "admin": {
        "name": "Admin User",
        "password": "aa5b6568e7d12f34320f4c23dab3b29b598f2960277a314c8e22e29a291ffb28",
        "role": "admin"
    },
    "user": {
        "name": "Normal User",
        "password": "82522beaaedd08c9cc7073af6e8d26d59ff83d94ad74a6eb127cefabdf7ceea7",
        "role": "user"
    },
    "viewer": {
        "name": "Viewer",
        "password": "cc04baa01651396ea98efe44422d6074bddaf3fec7c9ce2c3c8ecbd28bee09d4",
        "role": "viewer"
    }
}

# =========================
# INIT SESSION STATE
# =========================
def init_auth():
    if "auth" not in st.session_state:
        st.session_state.auth = {
            "logged_in": False,
            "username": None,
            "name": None,
            "role": None
        }


# =========================
# LOGIN UI
# =========================
def login():
    init_auth()

    if st.session_state.auth["logged_in"]:
        return True

    # ===== LOGIN PAGE UI =====
    col1, col2 = st.columns(2)

    with col1:
        st.image("assets/nlng_logo.png", width=120)

    with col2:
        st.image("assets/evomec_logo.png", width=120)

    st.title("🔐 QAQC Dashboard Login")
    st.caption("NLNG | Evomec Global Services Secure Access")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = USERS.get(username)

        if user and hmac.compare_digest(hash_password(password), user["password"]):
            st.session_state.auth["logged_in"] = True
            st.session_state.auth["username"] = username
            st.session_state.auth["name"] = user["name"]
            st.session_state.auth["role"] = user["role"]
            st.rerun()
        else:
            st.error("Invalid username or password")

    return False


# =========================
# LOGOUT
# =========================
def logout():
    if st.sidebar.button("Logout"):
        st.session_state.auth = {
            "logged_in": False,
            "username": None,
            "name": None,
            "role": None
        }
        st.rerun()


# =========================
# GET ROLE
# =========================
def get_role():
    return st.session_state.auth.get("role")


# =========================
# PROTECT PAGE
# =========================
def require_role(roles):
    role = get_role()
    if role not in roles:
        st.error("🚫 You do not have access to this module.")
        st.stop()
