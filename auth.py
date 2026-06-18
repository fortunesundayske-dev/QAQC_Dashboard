import streamlit as st
import bcrypt

# =========================
# USERS DATABASE (replace later with DB)
# =========================
USERS = {
    "admin": {
        "name": "Admin User",
        "password": bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode(),
        "role": "admin"
    },
    "user": {
        "name": "Normal User",
        "password": bcrypt.hashpw("user123".encode(), bcrypt.gensalt()).decode(),
        "role": "user"
    },
    "viewer": {
        "name": "Viewer",
        "password": bcrypt.hashpw("viewer123".encode(), bcrypt.gensalt()).decode(),
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

        if user and bcrypt.checkpw(password.encode(), user["password"].encode()):
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